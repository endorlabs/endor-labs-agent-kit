#!/usr/bin/env python3
"""Run opt-in local runtime QA against generated Endor Agent Kit plugins."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Sequence

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if SRC_ROOT.is_dir():
    sys.path.insert(0, str(SRC_ROOT))

try:
    from endor_agent_kit.agent_output_lint import lint_agent_output
    from endor_agent_kit.knowledge_pack import (
        default_task_profile_for_agent,
        render_task_profile_prompt,
    )
    from endor_agent_kit.structured_output_contracts import (
        json_schema_for_agent,
        required_fields_for,
    )
    from endor_agent_kit.publication.plugin_package_common import (
        PLUGIN_NAME,
        package_version,
    )
except ModuleNotFoundError:  # pragma: no cover - generated mirror may omit src/
    lint_agent_output = None
    default_task_profile_for_agent = None
    render_task_profile_prompt = None
    json_schema_for_agent = None
    required_fields_for = None
    PLUGIN_NAME = "endor-labs-agent-kit"
    package_version = None


SUPPORTED_HOSTS = ("claude", "codex", "antigravity", "gemini", "cursor")
DEFAULT_HOSTS = SUPPORTED_HOSTS
DEFAULT_AGENTS = (
    "sca-remediation",
    "ai-sast-triage",
    "endor-troubleshooter",
    "probe-droid",
)
LEGACY_CODEX_PLUGIN_NAMES = ("endor-agent-kit-security-agents",)
CODEX_PLUGIN_CACHE_PATH_RE = re.compile(
    r"(?P<path>/[^\s'\"`<>]*?\.codex/plugins/cache/"
    r"(?P<marketplace>[^/\s'\"`<>]+)/"
    r"(?P<plugin>[^/\s'\"`<>]+)/"
    r"(?P<version>[^/\s'\"`<>]+))"
)


@dataclass(frozen=True)
class RuntimeQaResult:
    host: str
    agent: str
    task_profile: str
    workspace: str
    status: str
    reason: str
    returncode: int | None
    duration_seconds: float
    command: list[str]
    prompt_log: str
    output_schema_log: str
    stdout_log: str
    stderr_log: str


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.allow_live_endor_read:
        print("ERROR: --allow-live-endor-read is required for runtime QA prompts that may query Endor tenant data.")
        return 2

    workspaces = [path.expanduser().resolve() for path in args.workspace]
    missing = [path for path in workspaces if not path.is_dir()]
    if missing:
        for path in missing:
            print(f"ERROR: workspace does not exist or is not a directory: {path}")
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    log_dir = create_log_dir(args.log_root)
    overrides = parse_command_overrides(args.command_override)
    task_profiles = parse_task_profile_overrides(args.task_profile)
    hosts = tuple(dict.fromkeys(args.host or DEFAULT_HOSTS))
    agents = tuple(dict.fromkeys(args.agent or DEFAULT_AGENTS))

    results: list[RuntimeQaResult] = []
    for workspace in workspaces:
        for host in hosts:
            for agent in agents:
                result = run_case(
                    host=host,
                    agent=agent,
                    workspace=workspace,
                    namespace=args.namespace,
                    task_profile=task_profiles.get(agent) or default_runtime_task_profile(agent),
                    log_dir=log_dir,
                    repo_root=repo_root,
                    timeout=args.timeout,
                    command_overrides=overrides,
                    codex_sandbox=args.codex_sandbox,
                    claude_permission_mode=args.claude_permission_mode,
                    env=os.environ.copy(),
                )
                results.append(result)
                print(f"{result.host}/{result.agent}/{Path(result.workspace).name}: {result.status} {result.reason}".rstrip())

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "namespace": args.namespace,
        "allow_live_endor_read": args.allow_live_endor_read,
        "log_dir": str(log_dir),
        "hosts": list(hosts),
        "agents": list(agents),
        "task_profiles": {
            agent: task_profiles.get(agent) or default_runtime_task_profile(agent)
            for agent in agents
        },
        "codex_sandbox": args.codex_sandbox,
        "claude_permission_mode": args.claude_permission_mode,
        "workspaces": [str(path) for path in workspaces],
        "results": [asdict(result) for result in results],
    }
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"runtime QA logs: {log_dir}")

    return 1 if any(result.status in {"failed", "timeout"} for result in results) else 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, action="append", type=Path, help="Repository/workspace to test. Repeat for multiple projects.")
    parser.add_argument("--namespace", required=True, help="Explicit Endor namespace for live read prompts.")
    parser.add_argument("--allow-live-endor-read", action="store_true", help="Confirm that runtime prompts may perform read-only Endor tenant lookups.")
    parser.add_argument("--host", action="append", choices=SUPPORTED_HOSTS, help="Host to test. Repeatable. Defaults to all supported/blocked hosts.")
    parser.add_argument("--agent", action="append", help="Agent id to test. Repeatable. Defaults to core runtime QA agents.")
    parser.add_argument(
        "--task-profile",
        action="append",
        default=[],
        metavar="AGENT=PROFILE",
        help="Select an agent task profile for runtime QA. Repeatable. Defaults come from the Endor Knowledge Pack.",
    )
    parser.add_argument("--timeout", type=int, default=600, help="Per-case timeout in seconds.")
    parser.add_argument("--log-root", type=Path, default=Path("/tmp"), help="Parent directory for runtime QA logs.")
    parser.add_argument(
        "--codex-sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="read-only",
        help=(
            "Sandbox mode for Codex runtime QA. Default is read-only; live Endor "
            "reads may require danger-full-access because Codex sandboxes can block DNS/network."
        ),
    )
    parser.add_argument(
        "--claude-permission-mode",
        choices=("acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan"),
        default="default",
        help="Permission mode for Claude runtime QA. Default mode returns reliably in noninteractive plugin-agent runs.",
    )
    parser.add_argument(
        "--command-override",
        action="append",
        default=[],
        metavar="HOST=/path/to/command",
        help="Override a host CLI command for testing or local wrappers. Repeatable.",
    )
    return parser.parse_args(argv)


def create_log_dir(log_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = log_root.expanduser().resolve() / f"endor-agent-kit-runtime-qa-{stamp}"
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}-{counter}")
        counter += 1
    candidate.mkdir(parents=True)
    return candidate


def parse_command_overrides(values: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --command-override {value!r}; expected HOST=/path/to/command")
        host, command = value.split("=", 1)
        if host not in SUPPORTED_HOSTS:
            raise SystemExit(f"Invalid command override host {host!r}; expected one of {', '.join(SUPPORTED_HOSTS)}")
        overrides[host] = command
    return overrides


def parse_task_profile_overrides(values: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --task-profile {value!r}; expected AGENT=PROFILE")
        agent, profile = value.split("=", 1)
        if not agent.strip() or not profile.strip():
            raise SystemExit(f"Invalid --task-profile {value!r}; expected AGENT=PROFILE")
        overrides[agent.strip()] = profile.strip()
    return overrides


def run_case(
    *,
    host: str,
    agent: str,
    workspace: Path,
    namespace: str,
    task_profile: str,
    log_dir: Path,
    repo_root: Path,
    timeout: int,
    command_overrides: dict[str, str],
    codex_sandbox: str,
    claude_permission_mode: str,
    env: dict[str, str],
) -> RuntimeQaResult:
    case_dir = log_dir / safe_name(f"{host}-{agent}-{workspace.name}")
    case_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(
        host=host,
        agent=agent,
        workspace=workspace,
        namespace=namespace,
        task_profile=task_profile,
    )
    prompt_log = case_dir / "prompt.txt"
    output_schema_log = case_dir / "output-schema.json"
    stdout_log = case_dir / "stdout.txt"
    stderr_log = case_dir / "stderr.txt"
    command_log = case_dir / "command.json"
    prompt_log.write_text(prompt, encoding="utf-8")
    output_schema = structured_output_schema(agent)
    if output_schema is not None:
        output_schema_log.write_text(
            json.dumps(output_schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    command_or_block = build_command(
        host=host,
        agent=agent,
        prompt=prompt,
        workspace=workspace,
        repo_root=repo_root,
        output_schema=output_schema_log if output_schema is not None else None,
        command_overrides=command_overrides,
        codex_sandbox=codex_sandbox,
        claude_permission_mode=claude_permission_mode,
        env=env,
    )
    if isinstance(command_or_block, BlockedCommand):
        command_log.write_text(json.dumps({"blocked": command_or_block.reason}, indent=2) + "\n", encoding="utf-8")
        stdout_log.write_text("", encoding="utf-8")
        stderr_log.write_text(command_or_block.reason + "\n", encoding="utf-8")
        return RuntimeQaResult(
            host=host,
            agent=agent,
            task_profile=task_profile,
            workspace=str(workspace),
            status="blocked",
            reason=command_or_block.reason,
            returncode=None,
            duration_seconds=0.0,
            command=[],
            prompt_log=str(prompt_log),
            output_schema_log=str(output_schema_log) if output_schema is not None else "",
            stdout_log=str(stdout_log),
            stderr_log=str(stderr_log),
        )

    command = command_or_block
    command_log.write_text(json.dumps({"command": command}, indent=2) + "\n", encoding="utf-8")
    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        stdout_log.write_text(_timeout_stream_text(exc.stdout), encoding="utf-8")
        stderr_log.write_text(
            _timeout_stream_text(exc.stderr) + f"\nTIMEOUT after {timeout}s\n",
            encoding="utf-8",
        )
        return RuntimeQaResult(
            host=host,
            agent=agent,
            task_profile=task_profile,
            workspace=str(workspace),
            status="timeout",
            reason=f"timed out after {timeout}s",
            returncode=None,
            duration_seconds=round(duration, 3),
            command=command,
            prompt_log=str(prompt_log),
            output_schema_log=str(output_schema_log) if output_schema is not None else "",
            stdout_log=str(stdout_log),
            stderr_log=str(stderr_log),
        )

    duration = time.monotonic() - start
    stderr_text = completed.stderr
    status = "passed" if completed.returncode == 0 else "failed"
    reason = "" if completed.returncode == 0 else f"exit {completed.returncode}"
    stale_cache_errors = detect_stale_codex_cache_paths(completed.stdout + "\n" + stderr_text)
    if stale_cache_errors:
        status = "failed"
        reason = f"stale Codex plugin cache detected ({len(stale_cache_errors)} paths)"
        suffix = "\n" if stderr_text and not stderr_text.endswith("\n") else ""
        stderr_text = (
            f"{stderr_text}{suffix}\nSTALE HOST PACKAGE CACHE:\n"
            + "\n".join(f"ERROR: {error}" for error in stale_cache_errors)
            + "\n"
        )
    elif completed.returncode == 0 and lint_agent_output is not None:
        lint_errors = lint_agent_output(agent, completed.stdout, task_profile=task_profile)
        if lint_errors:
            status = "failed"
            reason = f"output lint failed ({len(lint_errors)} errors)"
            suffix = "\n" if stderr_text and not stderr_text.endswith("\n") else ""
            stderr_text = (
                f"{stderr_text}{suffix}\nOUTPUT LINT ERRORS:\n"
                + "\n".join(f"ERROR: {error}" for error in lint_errors)
                + "\n"
            )
    stdout_log.write_text(completed.stdout, encoding="utf-8")
    stderr_log.write_text(stderr_text, encoding="utf-8")
    return RuntimeQaResult(
        host=host,
        agent=agent,
        task_profile=task_profile,
        workspace=str(workspace),
        status=status,
        reason=reason,
        returncode=completed.returncode,
        duration_seconds=round(duration, 3),
        command=command,
        prompt_log=str(prompt_log),
        output_schema_log=str(output_schema_log) if output_schema is not None else "",
        stdout_log=str(stdout_log),
        stderr_log=str(stderr_log),
    )


@dataclass(frozen=True)
class BlockedCommand:
    reason: str


def build_command(
    *,
    host: str,
    agent: str,
    prompt: str,
    workspace: Path,
    repo_root: Path,
    output_schema: Path | None,
    command_overrides: dict[str, str],
    codex_sandbox: str,
    claude_permission_mode: str,
    env: dict[str, str],
) -> list[str] | BlockedCommand:
    executable = command_overrides.get(host)
    if executable is not None:
        if not Path(executable).exists() and shutil.which(executable) is None:
            return BlockedCommand(f"{host} command override not found: {executable}")
    else:
        executable = shutil.which(default_executable(host)) or ""
        if not executable:
            return BlockedCommand(f"{default_executable(host)} CLI not found on PATH")

    if host == "claude":
        plugin_dir = repo_root / "plugins" / "claude" / "endor-labs-agent-kit"
        return [
            executable,
            "-p",
            "--permission-mode",
            claude_permission_mode,
            "--plugin-dir",
            str(plugin_dir),
            "--agent",
            agent,
            prompt,
            "--add-dir",
            str(workspace),
        ]

    if host == "codex":
        command = [
            executable,
            "exec",
            "-C",
            str(workspace),
            "--sandbox",
            codex_sandbox,
            "--color",
            "never",
        ]
        if output_schema is not None:
            command.extend(["--output-schema", str(output_schema)])
        command.append(prompt)
        return command

    if host == "antigravity":
        return [executable, "run", "--workspace", str(workspace), prompt]

    if host == "gemini":
        if not (env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY")):
            return BlockedCommand("Gemini CLI found but GEMINI_API_KEY or GOOGLE_API_KEY is not set")
        return [executable, "-p", prompt]

    if host == "cursor":
        runner = repo_root / "cursor-sdk" / "run_cursor_agent.py"
        if not runner.is_file():
            return BlockedCommand("Cursor SDK runner is not generated")
        if not env.get("CURSOR_API_KEY"):
            return BlockedCommand("Cursor runtime QA requires CURSOR_API_KEY for Cursor SDK authentication")
        return [
            sys.executable,
            str(runner),
            cursor_agent_name(agent),
            prompt,
            "--mode",
            "local",
            "--workspace",
            str(workspace),
        ]

    return BlockedCommand(f"unsupported host: {host}")


def default_executable(host: str) -> str:
    return {
        "claude": "claude",
        "codex": "codex",
        "antigravity": "antigravity",
        "gemini": "gemini",
        "cursor": "cursor",
    }[host]


def build_prompt(
    *,
    host: str,
    agent: str,
    workspace: Path,
    namespace: str,
    task_profile: str | None = None,
) -> str:
    selected_profile = task_profile or default_runtime_task_profile(agent)
    invocation = agent_invocation(host, agent, selected_profile)
    lines = [
        "Endor Agent Kit runtime QA run.",
        f"Workspace: {workspace}",
        f"Namespace: {namespace}",
        f"Task profile: {selected_profile}",
        "Live Endor tenant reads are explicitly allowed for this QA run, but writes, scans, PRs, comments, and source edits are not approved.",
        "Use current live evidence when host tools and credentials allow it. If required Endor evidence is unavailable, do not guess; return precise data_gaps and evidence_queries.",
        "Do not read or print Endor config file contents. Do not use remembered namespace, project UUID, repo URL, finding counts, UIA, or CIA evidence.",
        "Do not consult memory, continuity notes, or prior runtime logs for evidence unless the selected profile explicitly requires setup or troubleshooting context.",
        "",
    ]
    profile_prompt = runtime_task_profile_prompt(agent, selected_profile)
    if profile_prompt:
        lines.extend([profile_prompt, ""])
    output_contract = runtime_output_contract(agent)
    if output_contract:
        lines.extend([output_contract, ""])
    lines.append(invocation)
    return "\n".join(lines)


def default_runtime_task_profile(agent: str) -> str:
    if default_task_profile_for_agent is None:
        return "evidence-check"
    return default_task_profile_for_agent(agent)


def runtime_task_profile_prompt(agent: str, profile: str) -> str:
    if render_task_profile_prompt is None:
        return ""
    return render_task_profile_prompt(agent, profile, compact=True)


def structured_output_schema(agent: str) -> dict | None:
    if json_schema_for_agent is None:
        return None
    try:
        return json_schema_for_agent(agent)
    except ValueError:
        return None


def runtime_output_contract(agent: str) -> str:
    if required_fields_for is None:
        return ""
    required = required_fields_for(agent)
    if not required:
        return ""
    contract = (
        "Provider-neutral structured output contract: return exactly one parseable JSON object "
        "with these required top-level fields in this order: "
        + ", ".join(f"`{field}`" for field in required)
        + ". Do not omit required fields; use empty arrays or null objects only with precise `data_gaps`."
    )
    if "evidence_queries" in required:
        contract += (
            " For `evidence_queries`, every row must include `name`, `resource`, `source`, `status`, "
            "`query_template_id`, `filter_summary`, `field_mask_summary`, `result_count`, and `reason`. "
            "`source` must be a category such as `endorctl_api`, `endor_mcp`, `local_repository`, "
            "`source_provider`, or `user_input`, never a raw command; put selectors and fields in the summary columns."
        )
    return contract


def agent_invocation(host: str, agent: str, task_profile: str | None = None) -> str:
    selected_profile = task_profile or default_runtime_task_profile(agent)
    task = qa_task(agent, selected_profile)
    if host == "claude":
        return f"Run this read-only QA task: {task}"
    if host == "codex":
        codex_name = agent if agent.startswith("endor-") else f"endor-{agent}"
        return (
            "For noninteractive Codex QA, do not spawn or fork subagents. "
            f"Execute the installed {codex_name}-agent instructions directly if available, "
            f"otherwise use the {agent} skill, for this read-only QA task: {task}"
        )
    if host == "antigravity":
        return f"Invoke @{agent} for this read-only QA task: {task}"
    if host == "gemini":
        return f"Use @{agent} or the {agent} skill for this read-only QA task: {task}"
    if host == "cursor":
        return f"Use {cursor_agent_name(agent)} for this read-only QA task: {task}"
    return task


def qa_task(agent: str, task_profile: str | None = None) -> str:
    profile = task_profile or default_runtime_task_profile(agent)
    tasks = {
        ("sca-remediation", "resolve-scope"): "resolve this repository to an Endor project and stop. Return one JSON object with project_resolution, evidence_queries, and data_gaps; do not query Finding or VersionUpgrade unless scope is already provided.",
        ("sca-remediation", "evidence-check"): "resolve this repository, query only scoped Finding availability and VersionUpgrade/UIA availability, and stop. Do not select a remediation.",
        ("sca-remediation", "selection-plan"): "resolve this repository, follow the Evidence Query Plan to narrow through VersionUpgrade/UIA before any selected-candidate Finding detail, inspect only the selected package's local manifest/source usage, then return one remediation gate JSON object. Do not edit files.",
        ("remediation-planner", "selection-plan"): "preview verified remediation options by ranking scoped VersionUpgrade/UIA evidence before any selected-option Finding detail. Refuse unproven SCA counts from local docs and return data_gaps for missing evidence.",
        ("ai-sast-triage", "evidence-check"): "resolve AI SAST finding availability and source context for this repository. For complete main-context AI SAST availability, use the full method enum `SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST` plus a project-scoped `--list-all` query. Do not generate diffs, create policies, or edit files.",
        ("endor-troubleshooter", "diagnose"): "diagnose one narrow Endor issue lane with read-only evidence. Do not run scans, mutate integrations, or print config secrets.",
        ("probe-droid", "evidence-check"): "assess bounded onboarding coverage evidence for this repository or supplied inventory. Do not run scans or edit GitHub/Endor state.",
    }
    return tasks.get(
        (agent, profile),
        "run the selected compact agent task profile and report only verified evidence, evidence_queries, and data_gaps.",
    )


def cursor_agent_name(agent: str) -> str:
    if agent == "endor-agent-kit-setup":
        return "endor-agent-kit-setup-agent"
    if agent.startswith("endor-"):
        return f"{agent}-agent"
    return f"endor-{agent}-agent"


def detect_stale_codex_cache_paths(text: str) -> list[str]:
    """Return stale Endor Agent Kit Codex plugin-cache paths mentioned by a host."""

    expected_version = current_plugin_version()
    errors: list[str] = []
    seen: set[str] = set()
    for match in CODEX_PLUGIN_CACHE_PATH_RE.finditer(text):
        path = match.group("path")
        if path in seen:
            continue
        seen.add(path)
        plugin = match.group("plugin")
        version = match.group("version")
        if plugin == PLUGIN_NAME and version == expected_version:
            continue
        if plugin == PLUGIN_NAME:
            errors.append(
                f"{path} references {plugin}@{version}; expected {PLUGIN_NAME}@{expected_version}"
            )
            continue
        if plugin in LEGACY_CODEX_PLUGIN_NAMES or ("endor" in plugin and "agent" in plugin):
            errors.append(
                f"{path} references legacy Endor Agent Kit package {plugin}@{version}; "
                f"expected {PLUGIN_NAME}@{expected_version}"
            )
    return errors


def current_plugin_version() -> str:
    if package_version is None:
        return "0.2.0"
    return package_version()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "case"


def _timeout_stream_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


if __name__ == "__main__":
    raise SystemExit(main())

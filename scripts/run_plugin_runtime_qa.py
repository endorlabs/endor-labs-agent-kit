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


SUPPORTED_HOSTS = ("claude", "codex", "antigravity", "gemini", "cursor")
DEFAULT_HOSTS = SUPPORTED_HOSTS
DEFAULT_AGENTS = (
    "sca-remediation",
    "ai-sast-triage",
    "endor-troubleshooter",
    "probe-droid",
)


@dataclass(frozen=True)
class RuntimeQaResult:
    host: str
    agent: str
    workspace: str
    status: str
    reason: str
    returncode: int | None
    duration_seconds: float
    command: list[str]
    prompt_log: str
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
                    log_dir=log_dir,
                    repo_root=repo_root,
                    timeout=args.timeout,
                    command_overrides=overrides,
                    codex_sandbox=args.codex_sandbox,
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
        "codex_sandbox": args.codex_sandbox,
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


def run_case(
    *,
    host: str,
    agent: str,
    workspace: Path,
    namespace: str,
    log_dir: Path,
    repo_root: Path,
    timeout: int,
    command_overrides: dict[str, str],
    codex_sandbox: str,
    env: dict[str, str],
) -> RuntimeQaResult:
    case_dir = log_dir / safe_name(f"{host}-{agent}-{workspace.name}")
    case_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(host=host, agent=agent, workspace=workspace, namespace=namespace)
    prompt_log = case_dir / "prompt.txt"
    stdout_log = case_dir / "stdout.txt"
    stderr_log = case_dir / "stderr.txt"
    command_log = case_dir / "command.json"
    prompt_log.write_text(prompt, encoding="utf-8")

    command_or_block = build_command(
        host=host,
        agent=agent,
        prompt=prompt,
        workspace=workspace,
        repo_root=repo_root,
        command_overrides=command_overrides,
        codex_sandbox=codex_sandbox,
        env=env,
    )
    if isinstance(command_or_block, BlockedCommand):
        command_log.write_text(json.dumps({"blocked": command_or_block.reason}, indent=2) + "\n", encoding="utf-8")
        stdout_log.write_text("", encoding="utf-8")
        stderr_log.write_text(command_or_block.reason + "\n", encoding="utf-8")
        return RuntimeQaResult(
            host=host,
            agent=agent,
            workspace=str(workspace),
            status="blocked",
            reason=command_or_block.reason,
            returncode=None,
            duration_seconds=0.0,
            command=[],
            prompt_log=str(prompt_log),
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
        stdout_log.write_text((exc.stdout or ""), encoding="utf-8")
        stderr_log.write_text((exc.stderr or "") + f"\nTIMEOUT after {timeout}s\n", encoding="utf-8")
        return RuntimeQaResult(
            host=host,
            agent=agent,
            workspace=str(workspace),
            status="timeout",
            reason=f"timed out after {timeout}s",
            returncode=None,
            duration_seconds=round(duration, 3),
            command=command,
            prompt_log=str(prompt_log),
            stdout_log=str(stdout_log),
            stderr_log=str(stderr_log),
        )

    duration = time.monotonic() - start
    stdout_log.write_text(completed.stdout, encoding="utf-8")
    stderr_log.write_text(completed.stderr, encoding="utf-8")
    return RuntimeQaResult(
        host=host,
        agent=agent,
        workspace=str(workspace),
        status="passed" if completed.returncode == 0 else "failed",
        reason="" if completed.returncode == 0 else f"exit {completed.returncode}",
        returncode=completed.returncode,
        duration_seconds=round(duration, 3),
        command=command,
        prompt_log=str(prompt_log),
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
    command_overrides: dict[str, str],
    codex_sandbox: str,
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
            "plan",
            "--plugin-dir",
            str(plugin_dir),
            "--agent",
            agent,
            prompt,
            "--add-dir",
            str(workspace),
        ]

    if host == "codex":
        return [
            executable,
            "exec",
            "-C",
            str(workspace),
            "--sandbox",
            codex_sandbox,
            "--color",
            "never",
            prompt,
        ]

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


def build_prompt(*, host: str, agent: str, workspace: Path, namespace: str) -> str:
    invocation = agent_invocation(host, agent)
    return "\n".join([
        "Endor Agent Kit runtime QA run.",
        f"Workspace: {workspace}",
        f"Namespace: {namespace}",
        "Live Endor tenant reads are explicitly allowed for this QA run, but writes, scans, PRs, comments, and source edits are not approved.",
        "Use current live evidence when host tools and credentials allow it. If required Endor evidence is unavailable, do not guess; return precise data_gaps and evidence_queries.",
        "Do not read or print Endor config file contents. Do not use remembered namespace, project UUID, repo URL, finding counts, UIA, or CIA evidence.",
        "",
        invocation,
    ])


def agent_invocation(host: str, agent: str) -> str:
    task = qa_task(agent)
    if host == "claude":
        return f"Run this read-only QA task: {task}"
    if host == "codex":
        codex_name = agent if agent.startswith("endor-") else f"endor-{agent}"
        return f"Use the {codex_name}-agent custom agent if available, otherwise use the {agent} skill, for this read-only QA task: {task}"
    if host == "antigravity":
        return f"Invoke @{agent} for this read-only QA task: {task}"
    if host == "gemini":
        return f"Use @{agent} or the {agent} skill for this read-only QA task: {task}"
    if host == "cursor":
        return f"Use {cursor_agent_name(agent)} for this read-only QA task: {task}"
    return task


def qa_task(agent: str) -> str:
    tasks = {
        "sca-remediation": "resolve the Endor project for this repository and return exactly one parseable remediation gate JSON object, with project_resolution, selected_remediation, uia_evidence, risk_decision, validation, change_requests, evidence_queries, and data_gaps. Do not edit files. If Finding or VersionUpgrade/UIA evidence is unavailable, include non-empty data_gaps.",
        "remediation-planner": "preview remediation options from verified Endor evidence only and return exactly one parseable JSON object. Refuse unproven SCA counts from local docs and report missing Finding or UIA evidence in data_gaps.",
        "ai-sast-triage": "triage available AI SAST findings for this repository. Do not edit files or create policies. If findings cannot be queried, return evidence_queries and data_gaps.",
        "endor-troubleshooter": "check Endor readiness and diagnose missing setup without running scans or printing config secrets.",
        "probe-droid": "assess onboarding evidence for the repository or organization using read-only GitHub and Endor evidence. Do not run scans.",
    }
    return tasks.get(agent, "run the generated read-only evidence check and report verified evidence, evidence_queries, and data_gaps.")


def cursor_agent_name(agent: str) -> str:
    if agent == "endor-agent-kit-setup":
        return "endor-agent-kit-setup-agent"
    if agent.startswith("endor-"):
        return f"{agent}-agent"
    return f"endor-{agent}-agent"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "case"


if __name__ == "__main__":
    raise SystemExit(main())

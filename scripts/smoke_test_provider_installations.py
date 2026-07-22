#!/usr/bin/env python3
"""Exercise every generated provider package in disposable install roots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


CLAUDE_HOOK_EVENTS = ("PostToolUse", "UserPromptSubmit")
CURSOR_HOOK_EVENTS = ("afterFileEdit", "beforeShellExecution", "beforeSubmitPrompt")
CLAUDE_MARKETPLACE_SOURCE = "./plugins/claude/endor-labs-agent-kit"


def canonical_agent_ids(root: Path) -> tuple[str, ...]:
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    agents = catalog.get("agents")
    if not isinstance(agents, list):
        raise ValueError("catalog.json has no agents array")
    ids = tuple(sorted(str(agent.get("id")) for agent in agents if isinstance(agent, dict)))
    if len(ids) != 11 or len(set(ids)) != 11:
        raise ValueError(f"expected exactly 11 canonical agents, found {len(set(ids))}")
    return ids


def smoke_test(
    root: Path,
    *,
    claude_command: str | None = None,
) -> dict[str, object]:
    root = root.resolve()
    canonical = canonical_agent_ids(root)
    with tempfile.TemporaryDirectory(prefix="endor-agent-install-smoke-") as temporary:
        home = Path(temporary)
        results: dict[str, object] = {}

        claude = home / "claude" / "plugins" / "endor-labs-agent-kit"
        shutil.copytree(root / "plugins/claude/endor-labs-agent-kit", claude)
        _require_names(claude / "agents", canonical, suffix=".md")
        claude_evidence = _claude_package_evidence(root, claude, canonical)
        if claude_command is not None:
            _validate_claude_plugin(claude_command, claude)
            claude_evidence["cli_validation"] = "passed"
        else:
            claude_evidence["cli_validation"] = "not_run"
        results["claude"] = claude_evidence

        codex_home = home / "codex"
        codex_skills = home / "codex-user-skills"
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py"),
                "--install",
                "--yes",
                "--codex-home",
                str(codex_home),
                "--skills-home",
                str(codex_skills),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise ValueError("Codex disposable installer failed")
        _require_names(
            codex_home / "agents",
            tuple(f"endor-{agent_id}-agent" for agent_id in canonical),
            suffix=".toml",
        )
        _require_directories(codex_skills, canonical)
        results["codex"] = {"canonical_agents": len(canonical), "status": "passed"}

        cursor = home / "cursor"
        shutil.copytree(root / "agents", cursor / "agents")
        shutil.copytree(root / "skills", cursor / "skills")
        _require_names(
            cursor / "agents",
            tuple(f"endor-{agent_id}-agent" for agent_id in canonical),
            suffix=".md",
        )
        _require_directories(cursor / "skills", canonical)
        results["cursor"] = {"canonical_agents": len(canonical), "status": "passed"}

        for provider in ("gemini", "antigravity"):
            package = home / provider / "endor-labs-agent-kit"
            shutil.copytree(root / "plugins" / provider / "endor-labs-agent-kit", package)
            _require_names(package / "agents", canonical, suffix=".md")
            _require_directories(package / "skills", canonical)
            results[provider] = {"canonical_agents": len(canonical), "status": "passed"}

    return {
        "schema_version": "1",
        "canonical_agent_count": len(canonical),
        "providers": results,
    }


def _require_names(directory: Path, expected: tuple[str, ...], *, suffix: str) -> None:
    missing = [name for name in expected if not (directory / f"{name}{suffix}").is_file()]
    if missing:
        raise ValueError(f"{directory}: missing {missing}")


def _require_directories(directory: Path, expected: tuple[str, ...]) -> None:
    missing = [name for name in expected if not (directory / name).is_dir()]
    if missing:
        raise ValueError(f"{directory}: missing {missing}")


def _claude_package_evidence(
    root: Path,
    package: Path,
    canonical: tuple[str, ...],
) -> dict[str, object]:
    marketplace = _load_json_object(root / ".claude-plugin" / "marketplace.json")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise ValueError("Claude marketplace has no plugins array")
    entry = next(
        (
            item
            for item in plugins
            if isinstance(item, dict) and item.get("name") == "endor-labs-agent-kit"
        ),
        None,
    )
    if entry is None:
        raise ValueError("Claude marketplace is missing endor-labs-agent-kit")
    marketplace_source = entry.get("source")
    if marketplace_source != CLAUDE_MARKETPLACE_SOURCE:
        raise ValueError(
            "Claude marketplace must resolve endor-labs-agent-kit to the "
            "host-specific nested package"
        )

    skills_root = package / "skills"
    skills = sorted(item.name for item in skills_root.iterdir() if item.is_dir())
    if skills != ["endor-agent-kit-setup"]:
        raise ValueError(
            "Claude package must expose only the setup skill; workflow skills "
            "would compete with plugin agents"
        )

    hooks = _load_json_object(package / "hooks" / "hooks.json")
    hook_map = hooks.get("hooks")
    if not isinstance(hook_map, dict):
        raise ValueError("Claude hooks file has no hooks object")
    hook_events = sorted(str(name) for name in hook_map)
    if hook_events != list(CLAUDE_HOOK_EVENTS):
        raise ValueError(f"Claude package has invalid hook events {hook_events}")

    cursor_hooks = _load_json_object(root / "hooks" / "hooks.json")
    cursor_hook_map = cursor_hooks.get("hooks")
    if not isinstance(cursor_hook_map, dict):
        raise ValueError("Cursor hooks file has no hooks object")
    cursor_hook_events = sorted(str(name) for name in cursor_hook_map)
    if cursor_hook_events != list(CURSOR_HOOK_EVENTS):
        raise ValueError(f"root Cursor package has invalid hook events {cursor_hook_events}")

    manifest = _load_json_object(package / ".claude-plugin" / "plugin.json")
    plugin_wide_mcp = "mcpServers" in manifest or (package / ".mcp.json").exists()
    if plugin_wide_mcp:
        raise ValueError("Claude package must not declare plugin-wide MCP")

    return {
        "canonical_agents": len(canonical),
        "hook_events": hook_events,
        "marketplace_source": marketplace_source,
        "plugin_wide_mcp": plugin_wide_mcp,
        "skills": skills,
        "status": "passed",
    }


def _load_json_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def _validate_claude_plugin(claude_command: str, package: Path) -> None:
    completed = subprocess.run(
        [claude_command, "plugin", "validate", str(package)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return
    detail = (completed.stderr or completed.stdout).strip()
    suffix = f": {detail}" if detail else ""
    raise ValueError(f"Claude plugin validation failed{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--claude-command",
        default="claude",
        help="Claude Code executable used for host plugin validation when available",
    )
    parser.add_argument(
        "--require-claude-cli-validation",
        action="store_true",
        help="fail when the Claude Code executable is unavailable",
    )
    args = parser.parse_args()
    try:
        claude_command = shutil.which(args.claude_command)
        if args.require_claude_cli_validation and claude_command is None:
            raise ValueError(
                f"Claude Code executable {args.claude_command!r} is unavailable"
            )
        result = smoke_test(args.root, claude_command=claude_command)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

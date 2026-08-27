#!/usr/bin/env python3
"""Validate isolated Claude and Cursor packages in an ai-plugins mirror."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Mapping


CLAUDE_PACKAGE_ROOT = Path("plugins/claude/endor-labs-agent-kit")
CLAUDE_ROOT_MANIFEST = Path(".claude-plugin/plugin.json")
CLAUDE_ROOT_HOOKS = Path("hooks/hooks.json")
CURSOR_MARKETPLACE = Path(".cursor-plugin/marketplace.json")
CURSOR_PACKAGE_ROOT = Path("plugins/cursor/endor-labs-agent-kit")
CURSOR_PACKAGE_MANIFEST = CURSOR_PACKAGE_ROOT / ".cursor-plugin/plugin.json"
VSCODE_PACKAGE_ROOT = Path("plugins/vscode/endor-labs-agent-kit")
STALE_CURSOR_ROOT_MANIFEST = Path(".cursor-plugin/plugin.json")
STALE_CURSOR_RUNTIME_ROOT = Path("cursor/endor-labs-agent-kit")
COMPONENT_FIELDS = ("agents", "skills", "hooks", "mcpServers")
CURSOR_MARKETPLACE_PLUGIN_FIELDS = frozenset({"name", "source", "description"})
FORBIDDEN_EXPOSED_TEXT = (
    "matt-staging",
    "/Users/",
    "\\Users\\",
)


def _load_json_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _referenced_hook_commands(value: object) -> tuple[str, ...]:
    commands: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "command" and isinstance(child, str):
                commands.append(child)
            else:
                commands.extend(_referenced_hook_commands(child))
    elif isinstance(value, list):
        for child in value:
            commands.extend(_referenced_hook_commands(child))
    return tuple(commands)


def _marketplace_plugin_entry(marketplace: Mapping[str, object]) -> dict[str, object] | None:
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        return None
    plugin = plugins[0]
    return plugin if isinstance(plugin, dict) else None


def _scan_forbidden_text(paths: list[Path], errors: list[str]) -> None:
    for path in paths:
        files = (
            sorted(child for child in path.rglob("*") if child.is_file())
            if path.is_dir()
            else [path]
        )
        for child in files:
            text = child.read_text(encoding="utf-8", errors="replace")
            for forbidden in FORBIDDEN_EXPOSED_TEXT:
                if forbidden in text:
                    errors.append(
                        f"exposed marketplace path contains forbidden text {forbidden}: {child}"
                    )


def validate_marketplace_host_boundaries(root: Path) -> list[str]:
    """Return packaging errors for the generated multi-host marketplace mirror."""

    errors: list[str] = []
    cursor_root = root / CURSOR_PACKAGE_ROOT
    try:
        claude_manifest = _load_json_object(root / CLAUDE_ROOT_MANIFEST)
        canonical_claude_manifest = _load_json_object(
            root / CLAUDE_PACKAGE_ROOT / ".claude-plugin/plugin.json"
        )
        claude_hooks = _load_json_object(root / CLAUDE_ROOT_HOOKS)
        canonical_claude_hooks = _load_json_object(
            root / CLAUDE_PACKAGE_ROOT / "hooks/hooks.json"
        )
        cursor_marketplace = _load_json_object(root / CURSOR_MARKETPLACE)
        cursor_manifest = _load_json_object(root / CURSOR_PACKAGE_MANIFEST)
        cursor_hooks = _load_json_object(cursor_root / "hooks/hooks.json")
        _load_json_object(cursor_root / "mcp.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"missing or invalid marketplace package boundary: {exc}"]

    if claude_manifest.get("name") != "ai-plugins":
        errors.append("root Claude manifest name must remain ai-plugins")
    if claude_manifest.get("displayName") != "Endor Labs Agent Kit":
        errors.append("root Claude manifest displayName must be Endor Labs Agent Kit")
    if "version" in claude_manifest:
        errors.append("root Claude manifest must omit version so source SHA drives updates")
    if canonical_claude_manifest.get("name") != "endor-labs-agent-kit":
        errors.append("canonical nested Claude package has the wrong name")
    for field in COMPONENT_FIELDS:
        if field in claude_manifest:
            errors.append(
                f"root Claude manifest must use conventional {field} auto-discovery"
            )

    canonical_agents = root / CLAUDE_PACKAGE_ROOT / "agents"
    if not _tree_snapshot(canonical_agents):
        errors.append("canonical nested Claude package has no agents")
    if _tree_snapshot(root / "agents") != _tree_snapshot(canonical_agents):
        errors.append("root agents must be byte-identical to canonical Claude agents")
    if claude_hooks != canonical_claude_hooks:
        errors.append("root hooks must exactly match the canonical Claude hook graph")
    if _tree_snapshot(root / "hooks") != _tree_snapshot(
        root / CLAUDE_PACKAGE_ROOT / "hooks"
    ):
        errors.append("root hooks must be byte-identical to canonical Claude hooks")
    if _tree_snapshot(root / "runtime") != _tree_snapshot(
        root / CLAUDE_PACKAGE_ROOT / "runtime"
    ):
        errors.append("root runtime must be byte-identical to canonical Claude runtime")
    if _tree_snapshot(root / "skills") != _tree_snapshot(
        root / CLAUDE_PACKAGE_ROOT / "skills"
    ):
        errors.append("root skills must contain only the canonical Claude setup skill")
    if (root / ".mcp.json").exists():
        errors.append("root .mcp.json would be auto-loaded by Claude and must be absent")

    if (root / STALE_CURSOR_ROOT_MANIFEST).exists():
        errors.append("root Cursor plugin.json must be absent in the multi-plugin mirror")
    if (root / STALE_CURSOR_RUNTIME_ROOT).exists():
        errors.append("legacy cursor/endor-labs-agent-kit runtime must be absent")
    cursor_entry = _marketplace_plugin_entry(cursor_marketplace)
    expected_cursor_source = f"./{CURSOR_PACKAGE_ROOT.as_posix()}"
    if cursor_entry is None:
        errors.append("Cursor marketplace must contain exactly one plugin entry")
    else:
        unsupported_fields = sorted(
            set(cursor_entry) - CURSOR_MARKETPLACE_PLUGIN_FIELDS
        )
        if unsupported_fields:
            errors.append(
                "Cursor marketplace plugin entry has unsupported fields: "
                + ", ".join(unsupported_fields)
            )
        if cursor_entry.get("name") != "endorlabs":
            errors.append("Cursor marketplace plugin id must remain endorlabs")
        if cursor_entry.get("source") != expected_cursor_source:
            errors.append(
                f"Cursor marketplace source must be {expected_cursor_source}"
            )
    if cursor_manifest.get("name") != "endorlabs":
        errors.append("nested Cursor manifest name must remain endorlabs")
    for field in COMPONENT_FIELDS:
        if field in cursor_manifest:
            errors.append(
                f"nested Cursor manifest must use conventional {field} auto-discovery"
            )

    required_cursor_paths = (
        cursor_root / "agents",
        cursor_root / "skills",
        cursor_root / "hooks/hooks.json",
        cursor_root / "runtime/summarize_endor_artifact.py",
        cursor_root / "mcp.json",
        cursor_root / "assets/logo.png",
    )
    for path in required_cursor_paths:
        if not path.exists():
            errors.append(f"Cursor package is missing conventional component path: {path}")
    if (cursor_root / ".mcp.json").exists():
        errors.append("Cursor package must use template-compatible mcp.json, not .mcp.json")

    claude_agents = sorted((root / "agents").glob("*.md"))
    cursor_agents = sorted((cursor_root / "agents").glob("*.md"))
    if not cursor_agents:
        errors.append("Cursor package has no agents")
    for agent_path in claude_agents:
        if not re.search(
            r"^model:\s*sonnet\s*$",
            agent_path.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ):
            errors.append(f"exposed Claude agent is not pinned to sonnet: {agent_path}")
    for agent_path in cursor_agents:
        if not re.search(
            r"^model:\s*composer-2\.5\[fast=false\]\s*$",
            agent_path.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ):
            errors.append(
                f"exposed Cursor agent is not pinned to composer-2.5 standard: {agent_path}"
            )

    for command in _referenced_hook_commands(claude_hooks):
        match = re.search(r'\$\{CLAUDE_PLUGIN_ROOT\}/([^" ]+)', command)
        if match and not (root / match.group(1)).is_file():
            errors.append(
                f"Claude hook references missing command: {root / match.group(1)}"
            )
    for command in _referenced_hook_commands(cursor_hooks):
        match = re.search(r"(?:^|\s)(\./[^\s\"]+)", command)
        if match and not (cursor_root / match.group(1)).is_file():
            errors.append(
                f"Cursor hook references missing command: {cursor_root / match.group(1)}"
            )

    _validate_vscode_package(root, errors)

    exposed_paths = [
        root / "agents",
        root / "skills",
        cursor_root / "agents",
        cursor_root / "skills",
    ]
    vscode_root = root / VSCODE_PACKAGE_ROOT
    if vscode_root.is_dir():
        exposed_paths.extend([
            vscode_root / "skills",
            vscode_root / "com.github.copilot" / "agents",
        ])
    _scan_forbidden_text([path for path in exposed_paths if path.exists()], errors)
    return errors


def _validate_vscode_package(root: Path, errors: list[str]) -> None:
    """Validate the VS Code / Copilot Agent Plugins 1.0 bundle.

    The VS Code slice is a cross-Copilot Agent Plugin (``plugin.json`` at its root,
    portable ``skills/`` + ``mcp.json``, and Copilot components under
    ``com.github.copilot/``). It is not a Claude/Cursor-style plugin marketplace
    manifest, so it is exempt from those boundary checks; its plugin manifest,
    component structure, and MCP key convention are validated instead.
    """

    package = root / VSCODE_PACKAGE_ROOT
    if not package.is_dir():
        return

    for relative in (
        "plugin.json",
        "mcp.json",
        "skills",
        "com.github.copilot/agents",
        "runtime/summarize_endor_artifact.py",
        "assets/logo.png",
    ):
        if not (package / relative).exists():
            errors.append(f"VS Code package is missing conventional component path: {package / relative}")

    agents_dir = package / "com.github.copilot" / "agents"
    if agents_dir.is_dir() and not sorted(agents_dir.glob("*.agent.md")):
        errors.append("VS Code package has no custom agents")

    manifest_path = package / "plugin.json"
    if manifest_path.is_file():
        try:
            manifest = _load_json_object(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"VS Code plugin manifest is invalid: {exc}")
            manifest = {}
        if manifest.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
            errors.append(f"{manifest_path}: plugin.json $schema must be the Agent Plugins 1.0 plugin schema")
        if manifest.get("name") != "endor-labs-agent-kit":
            errors.append(f"{manifest_path}: plugin.json name must be endor-labs-agent-kit")

    mcp_path = package / "mcp.json"
    try:
        mcp = _load_json_object(mcp_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"VS Code MCP config is missing or invalid: {exc}")
        return
    if "servers" in mcp:
        errors.append(f"{mcp_path}: Agent Plugin mcp.json must use the top-level 'mcpServers' key, not 'servers'")
    servers = mcp.get("mcpServers")
    if not isinstance(servers, dict) or "endor-cli-tools" not in servers:
        errors.append(f"{mcp_path}: mcp.json must declare the endor-cli-tools server under 'mcpServers'")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    errors = validate_marketplace_host_boundaries(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(
        "OK: Claude and Cursor marketplace packages are conventional and isolated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

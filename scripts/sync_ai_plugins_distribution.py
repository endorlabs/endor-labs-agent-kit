#!/usr/bin/env python3
"""Sync generated Agent Kit distribution files into an ai-plugins checkout."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


SYNC_DIRECTORIES = (
    "plugins",
    ".cursor-plugin",
    "agents",
    "cursor-sdk",
    "assets",
)

SYNC_FILES = (
    ("CHANGELOG.md", "CHANGELOG.md"),
    ("GEMINI.md", "GEMINI.md"),
    (".claude-plugin/marketplace.json", ".claude-plugin/marketplace.json"),
    (".agents/plugins/marketplace.json", ".agents/plugins/marketplace.json"),
    ("scripts/check_repository_hygiene.py", "scripts/check_repository_hygiene.py"),
    (
        "scripts/build_codex_directory_submission.py",
        "scripts/build_codex_directory_submission.py",
    ),
    ("scripts/validate_mirror_provenance.py", "scripts/validate_mirror_provenance.py"),
    (
        "scripts/validate_marketplace_host_boundaries.py",
        "scripts/validate_marketplace_host_boundaries.py",
    ),
    (
        "source/distribution/ai-plugins-workflows/build-codex-directory-submission.yml",
        ".github/workflows/build-codex-directory-submission.yml",
    ),
)

STALE_GENERATED_FILES = (
    "gemini-extension.json",
    "scripts/validate_claude_official_root.py",
)

README_VERSION_PATTERN = re.compile(
    r"Current generated Agent Kit package version: `[^`]+`",
)

SOURCE_ONLY_ROOT_SKILLS = frozenset({
    "create-endor-labs-agent",
})

CLAUDE_PACKAGE_ROOT = Path("plugins/claude/endor-labs-agent-kit")
CLAUDE_OFFICIAL_ROOT_MANIFEST = Path(".claude-plugin/plugin.json")
CLAUDE_SETUP_SKILL = "endor-agent-kit-setup"
CURSOR_PACKAGE_ROOT = Path("plugins/cursor/endor-labs-agent-kit")
CURSOR_MARKETPLACE = Path(".cursor-plugin/marketplace.json")
CURSOR_ROOT_MANIFEST = Path(".cursor-plugin/plugin.json")
STALE_CURSOR_RUNTIME_ROOT = Path("cursor/endor-labs-agent-kit")
ROOT_MCP_CONFIG = Path(".mcp.json")


def generated_root_skills(source_root: Path) -> tuple[str, ...]:
    """Return generated root skill directory names to mirror into ai-plugins."""

    skills_root = source_root / "skills"
    if not skills_root.is_dir():
        raise FileNotFoundError(f"{skills_root}: missing generated skills directory")

    return tuple(
        child.name
        for child in sorted(skills_root.iterdir())
        if child.is_dir() and child.name not in SOURCE_ONLY_ROOT_SKILLS
    )


def sync_distribution(
    source_root: str | Path,
    target_root: str | Path,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Copy generated distribution surfaces from Agent Kit into ai-plugins."""

    source = Path(source_root).resolve()
    target = Path(target_root).resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"{source}: source repo not found")
    if not target.is_dir():
        raise FileNotFoundError(f"{target}: target repo not found")

    operations: list[str] = []

    for relative in SYNC_DIRECTORIES:
        _sync_tree(source / relative, target / relative, dry_run=dry_run, operations=operations)

    for source_relative, target_relative in SYNC_FILES:
        _sync_file(
            source / source_relative,
            target / target_relative,
            dry_run=dry_run,
            operations=operations,
        )

    _write_cursor_marketplace_overlay(
        source,
        target,
        dry_run=dry_run,
        operations=operations,
    )
    _write_claude_official_root_overlay(
        source,
        target,
        dry_run=dry_run,
        operations=operations,
    )
    _sync_readme_package_version(source, target, dry_run=dry_run, operations=operations)

    for relative in STALE_GENERATED_FILES:
        _remove_file(target / relative, dry_run=dry_run, operations=operations)

    return operations


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_cursor_marketplace_overlay(
    source: Path,
    target: Path,
    *,
    dry_run: bool,
    operations: list[str],
) -> None:
    """Generate a self-contained Cursor plugin away from Claude's root defaults."""

    package_root = target / CURSOR_PACKAGE_ROOT
    package_skills = package_root / "skills"
    source_skill_names = generated_root_skills(source)

    operations.append(f"generate self-contained Cursor package at {package_root}")
    if not dry_run:
        if package_root.exists():
            shutil.rmtree(package_root)
        package_skills.mkdir(parents=True, exist_ok=True)

    _sync_tree(
        source / "agents",
        package_root / "agents",
        dry_run=dry_run,
        operations=operations,
    )

    for skill_name in source_skill_names:
        _sync_tree(
            source / "skills" / skill_name,
            package_skills / skill_name,
            dry_run=dry_run,
            operations=operations,
        )
    _sync_tree(
        source / "hooks",
        package_root / "hooks",
        dry_run=dry_run,
        operations=operations,
    )
    _sync_tree(
        source / "runtime",
        package_root / "runtime",
        dry_run=dry_run,
        operations=operations,
    )
    _sync_tree(
        source / "assets",
        package_root / "assets",
        dry_run=dry_run,
        operations=operations,
    )
    _sync_file(
        source / ROOT_MCP_CONFIG,
        package_root / "mcp.json",
        dry_run=dry_run,
        operations=operations,
    )

    cursor_manifest = _load_json_object(source / ".cursor-plugin" / "plugin.json")
    for component_field in ("agents", "skills", "hooks", "mcpServers"):
        cursor_manifest.pop(component_field, None)
    manifest_path = package_root / ".cursor-plugin" / "plugin.json"
    operations.append(f"generate conventional Cursor manifest at {manifest_path}")

    marketplace = _load_json_object(source / CURSOR_MARKETPLACE)
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        raise ValueError(f"{source / CURSOR_MARKETPLACE}: expected exactly one plugin")
    plugin_entry = plugins[0]
    if not isinstance(plugin_entry, dict) or plugin_entry.get("name") != "endorlabs":
        raise ValueError(
            f"{source / CURSOR_MARKETPLACE}: expected stable Cursor plugin id endorlabs"
        )
    plugin_entry["source"] = f"./{CURSOR_PACKAGE_ROOT.as_posix()}"
    marketplace_path = target / CURSOR_MARKETPLACE
    operations.append(f"generate {marketplace_path} with nested Cursor source")
    operations.append(f"remove root Cursor manifest {target / CURSOR_ROOT_MANIFEST}")
    operations.append(f"remove stale Cursor runtime {target / STALE_CURSOR_RUNTIME_ROOT}")
    if not dry_run:
        _write_json(manifest_path, cursor_manifest)
        _write_json(marketplace_path, marketplace)
        _remove_file(target / CURSOR_ROOT_MANIFEST, dry_run=False, operations=[])
        _remove_tree(
            target / STALE_CURSOR_RUNTIME_ROOT,
            dry_run=False,
            operations=[],
        )


def _write_claude_official_root_overlay(
    source: Path,
    target: Path,
    *,
    dry_run: bool,
    operations: list[str],
) -> None:
    """Generate the Claude official compatibility package at the mirror root."""

    package_root = source / CLAUDE_PACKAGE_ROOT
    package_manifest = _load_json_object(
        package_root / ".claude-plugin" / "plugin.json"
    )
    if package_manifest.get("name") != "endor-labs-agent-kit":
        raise ValueError(
            f"{package_root}: canonical Claude package name must be endor-labs-agent-kit"
        )

    agents = sorted((package_root / "agents").glob("*.md"))
    if not agents:
        raise FileNotFoundError(f"{package_root / 'agents'}: no Claude agents found")
    setup_skill = package_root / "skills" / CLAUDE_SETUP_SKILL / "SKILL.md"
    if not setup_skill.is_file():
        raise FileNotFoundError(f"{setup_skill}: setup skill not found")

    metadata_keys = (
        "author",
        "description",
        "displayName",
        "homepage",
        "keywords",
        "repository",
    )
    manifest = {
        key: package_manifest[key]
        for key in metadata_keys
        if key in package_manifest
    }
    manifest.update(
        {
            "name": "ai-plugins",
            "displayName": "Endor Labs Agent Kit",
        }
    )
    manifest.pop("version", None)

    manifest_path = target / CLAUDE_OFFICIAL_ROOT_MANIFEST
    operations.append(f"generate {manifest_path}")
    operations.append(f"replace {target / 'agents'} with canonical Claude agents")
    operations.append(f"replace {target / 'skills'} with Claude setup-only skills")
    operations.append(f"replace {target / 'hooks'} with canonical Claude hooks")
    operations.append(f"replace {target / 'runtime'} with canonical Claude runtime")
    operations.append(f"remove root MCP auto-discovery file {target / ROOT_MCP_CONFIG}")
    if dry_run:
        return

    _write_json(manifest_path, manifest)
    _sync_tree(
        package_root / "agents",
        target / "agents",
        dry_run=False,
        operations=[],
    )
    _sync_tree(
        package_root / "skills",
        target / "skills",
        dry_run=False,
        operations=[],
    )
    _sync_tree(
        package_root / "hooks",
        target / "hooks",
        dry_run=False,
        operations=[],
    )
    _sync_tree(
        package_root / "runtime",
        target / "runtime",
        dry_run=False,
        operations=[],
    )
    _remove_file(target / ROOT_MCP_CONFIG, dry_run=False, operations=[])
    _remove_file(
        target / ".claude-plugin" / "claude-official-root-hooks.json",
        dry_run=False,
        operations=[],
    )


def _source_package_version(source: Path) -> str:
    pyproject = source / "pyproject.toml"
    if not pyproject.is_file():
        raise FileNotFoundError(f"{pyproject}: missing source package metadata")
    match = re.search(
        r'^version = "([^"]+)"$',
        pyproject.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if not match:
        raise ValueError(f"{pyproject}: missing project.version")
    return match.group(1)


def _sync_readme_package_version(
    source: Path,
    target: Path,
    *,
    dry_run: bool,
    operations: list[str],
) -> None:
    readme = target / "README.md"
    version = _source_package_version(source)
    operations.append(f"update {readme} package version -> {version}")
    if dry_run:
        return
    if not readme.is_file():
        operations.append(f"skip missing {readme}")
        return

    text = readme.read_text(encoding="utf-8")
    replacement = f"Current generated Agent Kit package version: `{version}`"
    updated, count = README_VERSION_PATTERN.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{readme}: missing package version marker")
    readme.write_text(updated, encoding="utf-8")


def _sync_tree(source: Path, target: Path, *, dry_run: bool, operations: list[str]) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"{source}: generated directory not found")
    operations.append(f"sync {source} -> {target}")
    if dry_run:
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _remove_tree(target: Path, *, dry_run: bool, operations: list[str]) -> None:
    if not target.exists():
        return
    operations.append(f"remove stale {target}")
    if not dry_run:
        shutil.rmtree(target)


def _remove_file(target: Path, *, dry_run: bool, operations: list[str]) -> None:
    if not target.exists():
        return
    operations.append(f"remove stale {target}")
    if not dry_run:
        target.unlink()


def _sync_file(source: Path, target: Path, *, dry_run: bool, operations: list[str]) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"{source}: generated file not found")
    operations.append(f"copy {source} -> {target}")
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=Path("."), type=Path, help="Agent Kit source checkout")
    parser.add_argument("--target", required=True, type=Path, help="ai-plugins checkout")
    parser.add_argument("--dry-run", action="store_true", help="Print planned operations without copying")
    args = parser.parse_args(argv)

    try:
        operations = sync_distribution(args.source, args.target, dry_run=args.dry_run)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    for operation in operations:
        print(operation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

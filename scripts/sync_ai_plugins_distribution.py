#!/usr/bin/env python3
"""Sync generated Agent Kit distribution files into an ai-plugins checkout."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SYNC_DIRECTORIES = (
    "plugins",
    ".cursor-plugin",
    "agents",
    "cursor-sdk",
    "hooks",
)

SYNC_FILES = (
    (".mcp.json", ".mcp.json"),
    ("CHANGELOG.md", "CHANGELOG.md"),
    ("GEMINI.md", "GEMINI.md"),
    (".claude-plugin/marketplace.json", ".claude-plugin/marketplace.json"),
    (".agents/plugins/marketplace.json", ".agents/plugins/marketplace.json"),
    ("assets/logo.svg", "assets/logo.svg"),
)

STALE_GENERATED_FILES = (
    "gemini-extension.json",
)

SOURCE_ONLY_ROOT_SKILLS = frozenset({
    "create-endor-labs-agent",
})


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

    source_skill_names = generated_root_skills(source)
    target_skills_root = target / "skills"
    if dry_run:
        operations.append(f"ensure {target_skills_root}")
    else:
        target_skills_root.mkdir(parents=True, exist_ok=True)

    for child in sorted(target_skills_root.iterdir()) if target_skills_root.exists() else ():
        if child.is_dir() and child.name not in source_skill_names:
            _remove_tree(child, dry_run=dry_run, operations=operations)

    for skill_name in source_skill_names:
        _sync_tree(
            source / "skills" / skill_name,
            target_skills_root / skill_name,
            dry_run=dry_run,
            operations=operations,
        )

    for source_relative, target_relative in SYNC_FILES:
        _sync_file(
            source / source_relative,
            target / target_relative,
            dry_run=dry_run,
            operations=operations,
        )

    for relative in STALE_GENERATED_FILES:
        _remove_file(target / relative, dry_run=dry_run, operations=operations)

    return operations


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

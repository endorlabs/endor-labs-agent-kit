#!/usr/bin/env python3
"""Install, update, inspect, or uninstall Endor Agent Kit Codex agents and skills."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

MANAGED_AGENT_MARKER = "# endor_agent_kit_managed = true"
MANAGED_SKILL_MARKERS = (
    "endor_agent_kit_managed=true",
    "Generated from Endor Agent Kit recipe",
    "Generated for the Endor Labs Agent Kit Codex plugin",
)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(child.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(child.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def codex_home(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def bundled_agents(plugin_root: Path) -> list[Path]:
    return sorted((plugin_root / "agents").glob("*.toml"))


def bundled_skills(plugin_root: Path) -> list[Path]:
    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(path for path in skills_root.iterdir() if (path / "SKILL.md").is_file())


def is_managed_agent(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return MANAGED_AGENT_MARKER in path.read_text(encoding="utf-8").splitlines()[:12]
    except UnicodeDecodeError:
        return False


def is_managed_skill(path: Path) -> bool:
    skill = path / "SKILL.md"
    if not skill.is_file():
        return False
    try:
        text = skill.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return any(marker in text for marker in MANAGED_SKILL_MARKERS)


def item_status(kind: str, source: Path, target: Path) -> str:
    if not target.exists():
        return "missing"
    if kind == "agent":
        if not target.is_file():
            return "blocked-non-file"
        if file_digest(source) == file_digest(target):
            return "current"
        if is_managed_agent(target):
            return "managed-stale-or-edited"
        return "blocked-unmanaged"
    if not target.is_dir():
        return "blocked-non-dir"
    if tree_digest(source) == tree_digest(target):
        return "current"
    if is_managed_skill(target):
        return "managed-stale-or-edited"
    return "blocked-unmanaged"


def backup_path_for(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = path.with_name(f"{path.name}.bak-{stamp}")
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.bak-{stamp}-{counter}")
        counter += 1
    return candidate


def backup(path: Path) -> Path:
    backup_path = backup_path_for(path)
    if path.is_dir():
        shutil.copytree(path, backup_path)
    elif path.is_file():
        shutil.copy2(path, backup_path)
    else:
        raise RuntimeError(f"cannot back up unsupported path: {path}")
    return backup_path


def remove_existing(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_item(kind: str, source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == "agent":
        shutil.copy2(source, target)
    else:
        shutil.copytree(source, target)


def bundled_items(plugin_root: Path, home: Path, *, agents_only: bool, skills_only: bool) -> list[tuple[str, Path, Path]]:
    items: list[tuple[str, Path, Path]] = []
    if not skills_only:
        agents_root = home / "agents"
        items.extend(
            ("agent", source, agents_root / source.name)
            for source in bundled_agents(plugin_root)
        )
    if not agents_only:
        skills_root = home / "skills"
        items.extend(
            ("skill", source, skills_root / source.name)
            for source in bundled_skills(plugin_root)
        )
    return items


def describe_block(kind: str, target: Path, status: str) -> str:
    if status == "blocked-non-file":
        return "blocked-non-file"
    if status == "blocked-non-dir":
        return "blocked-non-dir"
    return f"blocked unmanaged {kind}: {target}"


def run(args: argparse.Namespace) -> int:
    plugin_root = Path(__file__).resolve().parents[1]
    home = codex_home(args.codex_home)
    items = bundled_items(
        plugin_root,
        home,
        agents_only=args.agents_only,
        skills_only=args.skills_only,
    )
    if not items:
        print("ERROR: no bundled Codex agents or skills found for selected scope")
        return 1

    exit_code = 0
    for kind, source, target in items:
        status = item_status(kind, source, target)
        print(f"{kind}:{source.name}: {status}")

        if args.status:
            continue

        if args.uninstall:
            if status == "missing":
                continue
            if status.startswith("blocked"):
                print(f"  refusing to remove {describe_block(kind, target, status)}")
                exit_code = 1
                continue
            if args.yes:
                backup_path = backup(target)
                print(f"  backed up existing managed {kind} to {backup_path}")
                remove_existing(target)
                print(f"  removed {target}")
            else:
                print(f"  would back up and remove {target}; rerun with --yes after approval")
            continue

        if args.install:
            if status == "current":
                continue
            if status.startswith("blocked"):
                print(f"  refusing to overwrite {describe_block(kind, target, status)}")
                exit_code = 1
                continue
            if args.yes:
                if target.exists():
                    backup_path = backup(target)
                    print(f"  backed up existing managed {kind} to {backup_path}")
                    remove_existing(target)
                copy_item(kind, source, target)
                print(f"  installed {target}")
            else:
                print(f"  would install/update {target}; rerun with --yes after approval")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_codex_agents.py")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--status", action="store_true", help="Report installed agent and skill status")
    action.add_argument("--install", action="store_true", help="Install or update bundled agents and skills")
    action.add_argument("--uninstall", action="store_true", help="Remove managed installed agents and skills")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--agents-only", action="store_true", help="Limit action to bundled Codex custom agents")
    scope.add_argument("--skills-only", action="store_true", help="Limit action to bundled Codex skills")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--yes", action="store_true", help="Apply install/update/uninstall actions")
    args = parser.parse_args(argv)
    if not (args.status or args.install or args.uninstall):
        args.status = True
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

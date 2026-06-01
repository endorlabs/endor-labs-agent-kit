#!/usr/bin/env python3
"""Install, update, inspect, or uninstall Endor Agent Kit Codex agents."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

MANAGED_MARKER = "# endor_agent_kit_managed = true"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def codex_home(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def bundled_agents(plugin_root: Path) -> list[Path]:
    return sorted((plugin_root / "agents").glob("*.toml"))


def is_managed(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return MANAGED_MARKER in path.read_text(encoding="utf-8").splitlines()[:12]
    except UnicodeDecodeError:
        return False


def status(source: Path, target: Path) -> str:
    if not target.exists():
        return "missing"
    if not target.is_file():
        return "blocked-non-file"
    if sha256(source) == sha256(target):
        return "current"
    if is_managed(target):
        return "managed-stale-or-edited"
    return "blocked-unmanaged"


def backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_suffix(path.suffix + f".bak-{stamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def run(args: argparse.Namespace) -> int:
    plugin_root = Path(__file__).resolve().parents[1]
    target_root = codex_home(args.codex_home) / "agents"
    sources = bundled_agents(plugin_root)
    if not sources:
        print("ERROR: no bundled agents found")
        return 1

    exit_code = 0
    for source in sources:
        target = target_root / source.name
        item_status = status(source, target)
        print(f"{source.name}: {item_status}")

        if args.status:
            continue

        if args.uninstall:
            if item_status == "missing":
                continue
            if not is_managed(target):
                print(f"  refusing to remove unmanaged file: {target}")
                exit_code = 1
                continue
            if args.yes:
                target.unlink()
                print(f"  removed {target}")
            else:
                print(f"  would remove {target}; rerun with --yes after approval")
            continue

        if args.install:
            if item_status == "current":
                continue
            if item_status == "blocked-non-file":
                print(f"  refusing to replace non-file path: {target}")
                exit_code = 1
                continue
            if item_status == "blocked-unmanaged":
                print(f"  refusing to overwrite unmanaged file: {target}")
                exit_code = 1
                continue
            if args.yes:
                target_root.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    backup_path = backup(target)
                    print(f"  backed up existing managed file to {backup_path}")
                shutil.copy2(source, target)
                print(f"  installed {target}")
            else:
                print(f"  would install/update {target}; rerun with --yes after approval")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_codex_agents.py")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--status", action="store_true", help="Report installed agent status")
    action.add_argument("--install", action="store_true", help="Install or update bundled agents")
    action.add_argument("--uninstall", action="store_true", help="Remove managed installed agents")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--yes", action="store_true", help="Apply install/update/uninstall actions")
    args = parser.parse_args(argv)
    if not (args.status or args.install or args.uninstall):
        args.status = True
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

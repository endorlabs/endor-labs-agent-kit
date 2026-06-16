#!/usr/bin/env python3
"""Install, update, inspect, or uninstall Endor Agent Kit Codex agents and skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone

CURRENT_PLUGIN_NAME = "endor-labs-agent-kit"
CURRENT_PLUGIN_VERSION = "2.1.0"
ENDOR_PLUGIN_CACHE_NAMES = {
    CURRENT_PLUGIN_NAME,
    "endor-agent-kit-security-agents",
}
LEGACY_CODEX_PLUGIN_IDS = {
    "endor-agent-kit-security-agents@endor-agent-kit-local",
}
PLUGIN_TABLE_RE = re.compile(r'^\[plugins\."(?P<name>[^"]+)"\]\s*$')
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


def codex_skills_home(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    return Path("~/.agents/skills").expanduser()


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


def backup_root_for(kind: str, path: Path) -> Path:
    if kind == "skill":
        return path.parent.parent / "skill-backups" / "endor-agent-kit"
    return path.parent


def backup_path_for(path: Path, *, backup_root: Path | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = backup_root or path.parent
    base = root / f"{path.name}.bak-{stamp}"
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = root / f"{path.name}.bak-{stamp}-{counter}"
        counter += 1
    return candidate


def backup(path: Path, *, backup_root: Path | None = None) -> Path:
    backup_path = backup_path_for(path, backup_root=backup_root)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
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


def bundled_items(plugin_root: Path, home: Path, skills_home: Path, *, agents_only: bool, skills_only: bool) -> list[tuple[str, Path, Path]]:
    items: list[tuple[str, Path, Path]] = []
    if not skills_only:
        agents_root = home / "agents"
        items.extend(
            ("agent", source, agents_root / source.name)
            for source in bundled_agents(plugin_root)
        )
    if not agents_only:
        items.extend(
            ("skill", source, skills_home / source.name)
            for source in bundled_skills(plugin_root)
        )
    return items


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def manifest_text(manifest: dict) -> str:
    interface = manifest.get("interface")
    interface = interface if isinstance(interface, dict) else {}
    values = [
        manifest.get("name"),
        manifest.get("description"),
        manifest.get("homepage"),
        manifest.get("repository"),
        interface.get("displayName"),
        interface.get("shortDescription"),
        interface.get("longDescription"),
    ]
    return " ".join(str(value) for value in values if value).lower()


def is_endor_agent_kit_manifest(manifest: dict) -> bool:
    name = str(manifest.get("name") or "")
    if name in ENDOR_PLUGIN_CACHE_NAMES:
        return True
    text = manifest_text(manifest)
    return "endor" in text and "agent kit" in text


def relative_display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def tree_or_file_matches(source: Path, cached: Path) -> bool:
    if source.is_dir():
        return cached.is_dir() and tree_digest(source) == tree_digest(cached)
    if source.is_file():
        return cached.is_file() and file_digest(source) == file_digest(cached)
    return not cached.exists()


def plugin_cache_status(plugin_root: Path, cache_root: Path, manifest: dict) -> str:
    name = str(manifest.get("name") or "unknown")
    version = str(manifest.get("version") or "unknown")
    if name != CURRENT_PLUGIN_NAME:
        return (
            f"stale-legacy-cache package={name} version={version} "
            f"expected={CURRENT_PLUGIN_NAME}@{CURRENT_PLUGIN_VERSION}"
        )
    if version != CURRENT_PLUGIN_VERSION:
        return (
            f"stale-version-cache package={name} version={version} "
            f"expected={CURRENT_PLUGIN_VERSION}"
        )

    mismatches = []
    for relative in ("skills", "agents", ".codex-plugin/plugin.json"):
        source = plugin_root / relative
        cached = cache_root / relative
        if not tree_or_file_matches(source, cached):
            mismatches.append(relative)
    if mismatches:
        return "stale-content-cache mismatched=" + ",".join(mismatches)
    return f"current package={name} version={version}"


def report_plugin_cache_status(plugin_root: Path, home: Path) -> None:
    records = plugin_cache_records(plugin_root, home)
    reported = False
    for cache_root, status in records:
        print(f"plugin-cache:{relative_display(cache_root, home)}: {status}")
        if status.startswith("stale"):
            print(
                "  warning: Codex may load stale Endor Agent Kit instructions from "
                f"{cache_root}. Remove/reinstall that plugin package or clear the "
                "host cache, then start a fresh Codex thread. To move this cache "
                "out of the active cache after approval, rerun this installer with "
                "`--purge-stale-plugin-cache --yes`."
            )
        reported = True
    if not reported:
        print("plugin-cache: none")


def plugin_cache_records(plugin_root: Path, home: Path) -> list[tuple[Path, str]]:
    cache_base = home / "plugins" / "cache"
    records: list[tuple[Path, str]] = []
    for manifest_path in sorted(cache_base.glob("**/.codex-plugin/plugin.json")):
        manifest = read_json(manifest_path)
        if not is_endor_agent_kit_manifest(manifest):
            continue
        cache_root = manifest_path.parents[1]
        records.append((cache_root, plugin_cache_status(plugin_root, cache_root, manifest)))
    return records


def plugin_config_sections(config_path: Path) -> list[tuple[str, int, int, str]]:
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError):
        return []
    sections: list[tuple[str, int, int, str]] = []
    for index, line in enumerate(lines):
        match = PLUGIN_TABLE_RE.match(line.strip())
        if match is None:
            continue
        end = len(lines)
        for cursor in range(index + 1, len(lines)):
            if lines[cursor].lstrip().startswith("["):
                end = cursor
                break
        enabled = "unknown"
        for entry in lines[index + 1:end]:
            stripped = entry.strip()
            if stripped.startswith("enabled") and "=" in stripped:
                enabled = stripped.split("=", 1)[1].strip()
                break
        sections.append((match.group("name"), index, end, enabled))
    return sections


def stale_plugin_config_records(home: Path) -> list[tuple[Path, str, str]]:
    config_path = home / "config.toml"
    if not config_path.is_file():
        return []
    records: list[tuple[Path, str, str]] = []
    for plugin_id, _start, _end, enabled in plugin_config_sections(config_path):
        if plugin_id in LEGACY_CODEX_PLUGIN_IDS:
            records.append((
                config_path,
                plugin_id,
                f"stale-legacy-config enabled={enabled}",
            ))
    return records


def report_plugin_config_status(home: Path) -> None:
    records = stale_plugin_config_records(home)
    if not records:
        print("plugin-config: none")
        return
    for config_path, plugin_id, status in records:
        print(f"plugin-config:{relative_display(config_path, home)}:{plugin_id}: {status}")
        print(
            "  warning: Codex may try to load this removed legacy Endor Agent Kit "
            "plugin on every run. To remove the stale config entry after approval, "
            "rerun this installer with `--purge-stale-plugin-cache --yes`."
        )


def purge_stale_plugin_config(home: Path, *, yes: bool) -> None:
    config_path = home / "config.toml"
    sections = [
        (plugin_id, start, end)
        for plugin_id, start, end, _enabled in plugin_config_sections(config_path)
        if plugin_id in LEGACY_CODEX_PLUGIN_IDS
    ]
    if not sections:
        print("plugin-config: no stale Endor Agent Kit config entries")
        return
    plugin_ids = ", ".join(plugin_id for plugin_id, _start, _end in sections)
    if not yes:
        print(
            f"plugin-config:{relative_display(config_path, home)}: "
            f"would remove stale legacy entries {plugin_ids}; rerun with --yes after approval"
        )
        return
    backup_path = backup(config_path)
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    keep = [True] * len(lines)
    for _plugin_id, start, end in sections:
        for index in range(start, end):
            keep[index] = False
    config_path.write_text(
        "".join(line for line, include in zip(lines, keep) if include),
        encoding="utf-8",
    )
    print(f"plugin-config:{relative_display(config_path, home)}: removed stale legacy entries {plugin_ids}")
    print(f"  backed up Codex config to {backup_path}")


def cache_backup_path(home: Path, cache_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        relative = cache_root.relative_to(home / "plugins" / "cache")
    except ValueError:
        relative = Path(cache_root.name)
    name = "-".join(relative.parts) + f".bak-{stamp}"
    base = home / "plugins" / "cache-backups" / name
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = base.with_name(f"{base.name}-{counter}")
        counter += 1
    return candidate


def purge_stale_plugin_cache(plugin_root: Path, home: Path, *, yes: bool) -> int:
    stale = [
        (cache_root, status)
        for cache_root, status in plugin_cache_records(plugin_root, home)
        if status.startswith("stale")
    ]
    stale_config = stale_plugin_config_records(home)
    if not stale and not stale_config:
        print("plugin-cache: no stale Endor Agent Kit caches")
        print("plugin-config: no stale Endor Agent Kit config entries")
        return 0
    if not stale:
        print("plugin-cache: no stale Endor Agent Kit caches")
    else:
        for cache_root, status in stale:
            target = cache_backup_path(home, cache_root)
            print(f"plugin-cache:{relative_display(cache_root, home)}: {status}")
            if yes:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(cache_root), str(target))
                print(f"  moved stale plugin cache to {target}")
            else:
                print(f"  would move stale plugin cache to {target}; rerun with --yes after approval")
    purge_stale_plugin_config(home, yes=yes)
    return 0


def describe_block(kind: str, target: Path, status: str) -> str:
    if status == "blocked-non-file":
        return "blocked-non-file"
    if status == "blocked-non-dir":
        return "blocked-non-dir"
    return f"blocked unmanaged {kind}: {target}"


def run(args: argparse.Namespace) -> int:
    plugin_root = Path(__file__).resolve().parents[1]
    home = codex_home(args.codex_home)
    skills_home = codex_skills_home(args.skills_home)
    if args.purge_stale_plugin_cache:
        return purge_stale_plugin_cache(plugin_root, home, yes=args.yes)
    items = bundled_items(
        plugin_root,
        home,
        skills_home,
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
                backup_path = backup(target, backup_root=backup_root_for(kind, target))
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
                    backup_path = backup(target, backup_root=backup_root_for(kind, target))
                    print(f"  backed up existing managed {kind} to {backup_path}")
                    remove_existing(target)
                copy_item(kind, source, target)
                print(f"  installed {target}")
            else:
                print(f"  would install/update {target}; rerun with --yes after approval")
    if args.status and not args.agents_only and not args.skills_only:
        report_plugin_cache_status(plugin_root, home)
        report_plugin_config_status(home)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_codex_agents.py")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--status", action="store_true", help="Report installed agent and skill status")
    action.add_argument("--install", action="store_true", help="Install or update bundled agents and skills")
    action.add_argument("--uninstall", action="store_true", help="Remove managed installed agents and skills")
    action.add_argument("--purge-stale-plugin-cache", action="store_true", help="Move stale Endor Agent Kit plugin-cache directories and remove stale plugin config entries")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--agents-only", action="store_true", help="Limit action to bundled Codex custom agents")
    scope.add_argument("--skills-only", action="store_true", help="Limit action to bundled Codex skills")
    parser.add_argument("--codex-home", help="Override CODEX_HOME")
    parser.add_argument("--skills-home", help="Override Codex user skills directory")
    parser.add_argument("--yes", action="store_true", help="Apply install/update/uninstall actions")
    args = parser.parse_args(argv)
    if not (args.status or args.install or args.uninstall or args.purge_stale_plugin_cache):
        args.status = True
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

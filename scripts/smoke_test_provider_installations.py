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


def canonical_agent_ids(root: Path) -> tuple[str, ...]:
    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    agents = catalog.get("agents")
    if not isinstance(agents, list):
        raise ValueError("catalog.json has no agents array")
    ids = tuple(sorted(str(agent.get("id")) for agent in agents if isinstance(agent, dict)))
    if len(ids) != 11 or len(set(ids)) != 11:
        raise ValueError(f"expected exactly 11 canonical agents, found {len(set(ids))}")
    return ids


def smoke_test(root: Path) -> dict[str, object]:
    root = root.resolve()
    canonical = canonical_agent_ids(root)
    with tempfile.TemporaryDirectory(prefix="endor-agent-install-smoke-") as temporary:
        home = Path(temporary)
        results: dict[str, object] = {}

        claude = home / "claude" / "plugins" / "endor-labs-agent-kit"
        shutil.copytree(root / "plugins/claude/endor-labs-agent-kit", claude)
        _require_names(claude / "agents", canonical, suffix=".md")
        results["claude"] = {"canonical_agents": len(canonical), "status": "passed"}

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        result = smoke_test(args.root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

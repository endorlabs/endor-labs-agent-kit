"""Helpers for validating local Claude Code agent installs."""

from __future__ import annotations

import hashlib
from pathlib import Path


def check_claude_code_install(
    agent_id: str,
    repo: str | Path,
    *,
    catalog_root: str | Path = ".",
) -> list[str]:
    """Check whether a repo-level Claude Code agent install matches the catalog."""

    errors: list[str] = []
    source = _catalog_agent_artifact(Path(catalog_root), agent_id)
    target = Path(repo) / ".claude" / "agents" / f"{agent_id}.md"

    if source is None:
        errors.append(f"catalog: could not find claude-code artifact for {agent_id!r}")
        return errors
    if not target.is_file():
        errors.append(f"install: missing {target}")
        return errors

    source_hash = _sha256(source)
    target_hash = _sha256(target)
    if source_hash != target_hash:
        errors.append(
            f"install: {target} is stale for {agent_id!r}; "
            f"catalog sha256={source_hash}, installed sha256={target_hash}"
        )
    return errors


def _catalog_agent_artifact(catalog_root: Path, agent_id: str) -> Path | None:
    root = catalog_root / "claude-code" / agent_id
    candidates = [
        root / f"{agent_id}.md",
        root / "enterprise-edition" / f"{agent_id}.md",
        root / "developer-edition" / f"{agent_id}.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

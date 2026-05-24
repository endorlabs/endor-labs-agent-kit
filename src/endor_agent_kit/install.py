"""Helpers for validating local host artifact installs."""

from __future__ import annotations

import hashlib
from pathlib import Path

from endor_agent_kit.catalog_manifest import CatalogManifest, MANIFEST_PATH
from endor_agent_kit.compilers.claude_code import HOST as CLAUDE_CODE_HOST
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST


def check_claude_code_install(
    agent_id: str,
    repo: str | Path,
    *,
    catalog_root: str | Path = ".",
) -> list[str]:
    """Check whether a repo-level Claude Code agent install matches the catalog."""

    target = Path(repo) / ".claude" / "agents" / f"{agent_id}.md"
    return _check_primary_artifact_install(
        agent_id,
        CLAUDE_CODE_HOST,
        f"{agent_id}.md",
        target,
        catalog_root=catalog_root,
    )


def check_codex_install(
    agent_id: str,
    codex_home: str | Path,
    *,
    catalog_root: str | Path = ".",
) -> list[str]:
    """Check whether a Codex skill install matches the catalog."""

    target = Path(codex_home) / "skills" / agent_id / "SKILL.md"
    return _check_primary_artifact_install(
        agent_id,
        CODEX_HOST,
        "SKILL.md",
        target,
        catalog_root=catalog_root,
    )


def _check_primary_artifact_install(
    agent_id: str,
    host: str,
    artifact_name: str,
    target: Path,
    *,
    catalog_root: str | Path,
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = CatalogManifest.load(catalog_root)
    except FileNotFoundError:
        errors.append(f"catalog: missing {Path(catalog_root) / MANIFEST_PATH}")
        return errors
    except ValueError as exc:
        errors.append(f"catalog: {exc}")
        return errors

    expected = manifest.primary_artifact(agent_id, host, artifact_name)
    if expected is None:
        errors.append(
            f"catalog: could not find {host} primary artifact "
            f"{artifact_name!r} for {agent_id!r}"
        )
        return errors
    if not target.is_file():
        errors.append(f"install: missing {target}")
        return errors

    target_hash = _sha256(target)
    if expected.sha256 != target_hash:
        errors.append(
            f"install: {target} is stale for {agent_id!r}; "
            f"catalog sha256={expected.sha256}, installed sha256={target_hash}"
        )
    return errors


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

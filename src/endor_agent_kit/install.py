"""Helpers for validating local host artifact installs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from endor_agent_kit.catalog_schema import CatalogArtifact, CatalogBundle
from endor_agent_kit.catalog_manifest import CatalogManifest, MANIFEST_PATH
from endor_agent_kit.compilers.claude_code import HOST as CLAUDE_CODE_HOST
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST


@dataclass(frozen=True)
class ExpectedInstallArtifact:
    """One catalog artifact mapped to its installed Host path."""

    artifact: CatalogArtifact
    target: Path


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

    return _check_bundle_artifact_install(
        agent_id,
        CODEX_HOST,
        Path(codex_home) / "skills" / agent_id,
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


def _check_bundle_artifact_install(
    agent_id: str,
    host: str,
    target_root: Path,
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

    bundles = sorted(manifest.find_bundles(agent_id, host), key=lambda bundle: bundle.path)
    if not bundles:
        errors.append(f"catalog: could not find {host} artifact bundle for {agent_id!r}")
        return errors
    bundle = bundles[0]
    expected = _installed_bundle_artifacts(bundle, target_root)
    if not expected:
        errors.append(f"catalog: {host} artifact bundle for {agent_id!r} has no artifacts")
        return errors
    return _compare_expected_artifacts(agent_id, expected)


def _installed_bundle_artifacts(
    bundle: CatalogBundle,
    target_root: Path,
) -> tuple[ExpectedInstallArtifact, ...]:
    return tuple(
        ExpectedInstallArtifact(
            artifact=artifact,
            target=target_root / _artifact_relative_path(bundle, artifact),
        )
        for artifact in bundle.artifacts
    )


def _artifact_relative_path(bundle: CatalogBundle, artifact: CatalogArtifact) -> Path:
    artifact_path = Path(artifact.path)
    try:
        return artifact_path.relative_to(Path(bundle.path))
    except ValueError:
        return Path(artifact.name)


def _compare_expected_artifacts(
    agent_id: str,
    expected_artifacts: tuple[ExpectedInstallArtifact, ...],
) -> list[str]:
    errors: list[str] = []
    for expected in expected_artifacts:
        target = expected.target
        if not target.is_file():
            errors.append(f"install: missing {target}")
            continue
        target_hash = _sha256(target)
        if expected.artifact.sha256 != target_hash:
            errors.append(
                f"install: {target} is stale for {agent_id!r}; "
                f"catalog sha256={expected.artifact.sha256}, installed sha256={target_hash}"
            )
    return errors


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

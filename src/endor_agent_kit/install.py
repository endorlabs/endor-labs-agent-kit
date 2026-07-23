"""Helpers for validating local host artifact installs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from endor_agent_kit.catalog_schema import CatalogArtifact, CatalogBundle
from endor_agent_kit.catalog_manifest import CatalogManifest, MANIFEST_PATH
from endor_agent_kit.compilers.claude_code import HOST as CLAUDE_CODE_HOST
from endor_agent_kit.compilers.claude_managed_agents import HOST as CLAUDE_MANAGED_AGENTS_HOST
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST
from endor_agent_kit.compilers.portable import HOST as PORTABLE_HOST


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

    errors: list[str] = []
    try:
        manifest = CatalogManifest.load(catalog_root)
    except FileNotFoundError:
        return [f"catalog: missing {Path(catalog_root) / MANIFEST_PATH}"]
    except ValueError as exc:
        return [f"catalog: {exc}"]

    bundles = sorted(
        manifest.find_bundles(agent_id, CLAUDE_CODE_HOST),
        key=_primary_bundle_priority,
    )
    if not bundles:
        return [
            f"catalog: could not find {CLAUDE_CODE_HOST} primary artifact "
            f"{f'{agent_id}.md'!r} for {agent_id!r}"
        ]
    bundle = bundles[0]
    primary = bundle.artifact_named(f"{agent_id}.md")
    if primary is None:
        return [
            f"catalog: could not find {CLAUDE_CODE_HOST} primary artifact "
            f"{f'{agent_id}.md'!r} for {agent_id!r}"
        ]
    target_root = Path(repo) / ".claude" / "agents"
    expected = [ExpectedInstallArtifact(artifact=primary, target=target_root / primary.name)]
    expected.extend(
        ExpectedInstallArtifact(artifact=artifact, target=target_root / artifact.name)
        for artifact in bundle.artifacts
        if artifact.profile_id is not None
    )
    errors.extend(_compare_expected_artifacts(agent_id, tuple(expected)))
    return errors


def check_codex_install(
    agent_id: str,
    skills_home: str | Path,
    *,
    catalog_root: str | Path = ".",
) -> list[str]:
    """Check whether a Codex skill install matches the catalog."""

    try:
        manifest = CatalogManifest.load(catalog_root)
    except FileNotFoundError:
        return [f"catalog: missing {Path(catalog_root) / MANIFEST_PATH}"]
    except ValueError as exc:
        return [f"catalog: {exc}"]

    target_root = Path(skills_home) / agent_id
    plugin_artifacts = _installed_codex_plugin_skill_artifacts(
        manifest,
        agent_id,
        target_root,
    )
    if plugin_artifacts:
        return _compare_expected_artifacts(agent_id, plugin_artifacts)

    return _check_bundle_artifact_install(
        agent_id,
        CODEX_HOST,
        target_root,
        catalog_root=catalog_root,
    )


def check_claude_managed_agents_install(
    agent_id: str,
    managed_agent_dir: str | Path,
    *,
    catalog_root: str | Path = ".",
) -> list[str]:
    """Check whether a Claude Managed Agents bundle matches the catalog."""

    return _check_bundle_artifact_install(
        agent_id,
        CLAUDE_MANAGED_AGENTS_HOST,
        Path(managed_agent_dir),
        catalog_root=catalog_root,
    )


def check_portable_install(
    agent_id: str,
    portable_dir: str | Path,
    *,
    catalog_root: str | Path = ".",
) -> list[str]:
    """Check whether a copied portable bundle matches the catalog."""

    return _check_bundle_artifact_install(
        agent_id,
        PORTABLE_HOST,
        Path(portable_dir),
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


def _installed_codex_plugin_skill_artifacts(
    manifest: CatalogManifest,
    agent_id: str,
    target_root: Path,
) -> tuple[ExpectedInstallArtifact, ...]:
    packages = sorted(
        manifest.plugin_packages,
        key=lambda item: (item.name, item.path),
    )
    for package in packages:
        if (
            package.host != CODEX_HOST
            or package.distribution_channel != "repository"
            or agent_id not in package.included_agents
        ):
            continue
        skill_root = Path(package.path) / "bundled-skills" / agent_id
        expected = tuple(
            ExpectedInstallArtifact(
                artifact=artifact,
                target=target_root / Path(artifact.path).relative_to(skill_root),
            )
            for artifact in package.artifacts
            if Path(artifact.path).is_relative_to(skill_root)
        )
        if expected:
            return expected
    return ()


def _primary_bundle_priority(bundle: CatalogBundle) -> tuple[int, str]:
    priority = {
        "enterprise-edition": 0,
        "developer-edition": 1,
    }.get(bundle.bundle_id, 2)
    return (priority, bundle.path)


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

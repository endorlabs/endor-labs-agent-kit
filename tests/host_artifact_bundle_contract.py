"""Reusable assertions for published Host Artifact Bundle smoke tests."""

from __future__ import annotations

from pathlib import Path

MCP_SETUP_TOKENS = (
    "mcpServers:",
    "endor-cli-tools",
    "endorctl ai-tools mcp-server",
)

PUBLISHED_EVIDENCE_HOSTS = (
    "claude-code",
    "claude-managed-agents",
    "codex",
    "gemini",
    "portable",
)


def compiled_evidence_artifact_paths(
    agent_id: str,
    *,
    evidence_plan_ids: tuple[str, ...],
    profile_contract_ids: tuple[str, ...],
) -> set[str]:
    """Return the exact cross-host paths emitted for compiled evidence support."""

    paths: set[str] = set()
    for host in PUBLISHED_EVIDENCE_HOSTS:
        paths.add(
            f"{host}/{agent_id}/runtime/summarize_endor_artifact.py"
        )
        paths.update(
            f"{host}/{agent_id}/evidence-plans/{plan_id}.json"
            for plan_id in evidence_plan_ids
        )
        paths.update(
            f"{host}/{agent_id}/profile-contracts/{profile_id}.json"
            for profile_id in profile_contract_ids
        )
    return paths


def assert_host_bundle_files(bundle_dir: Path, relative_paths: set[str]) -> None:
    """Assert the expected bundle files exist under one published host directory."""

    for relative_path in relative_paths:
        assert (bundle_dir / relative_path).is_file(), relative_path


def assert_no_nested_edition_dirs(bundle_dir: Path) -> None:
    """Assert a flattened published bundle did not keep compiler edition directories."""

    assert not (bundle_dir / "developer-edition").exists()
    assert not (bundle_dir / "enterprise-edition").exists()


def assert_mcp_free_generated_artifact(content: str) -> None:
    """Assert an MCP-free generated artifact does not carry MCP setup text."""

    for token in MCP_SETUP_TOKENS:
        assert token not in content


def assert_codex_skill_bundle(
    bundle_dir: Path,
    *,
    expected_files: set[str],
    skill_markers: tuple[str, ...],
) -> None:
    """Assert a Codex skill bundle has the expected files and prompt markers."""

    assert_host_bundle_files(bundle_dir, expected_files)
    skill = (bundle_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "## Codex Host Contract" in skill
    for marker in skill_markers:
        assert marker in skill

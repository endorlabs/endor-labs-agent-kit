"""Reusable assertions for published Host Artifact Bundle smoke tests."""

from __future__ import annotations

from pathlib import Path

MCP_SETUP_TOKENS = (
    "mcpServers:",
    "endor-cli-tools",
    "endorctl ai-tools mcp-server",
)


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

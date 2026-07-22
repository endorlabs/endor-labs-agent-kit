from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from conftest import repo_root
from endor_agent_kit.publication.model_recommendations import (
    AGENT_MODEL_TIERS,
    ALLOWED_SELECTION_MODES,
    COMPLEX_REMEDIATION_AGENT_IDS,
    HOST_MODEL_RECOMMENDATIONS,
    model_recommendations_payload,
    model_requirements_lines,
)
from endor_agent_kit.publisher import publish_recipe


def _canonical_agent_ids() -> set[str]:
    return {
        path.parent.name
        for path in (repo_root() / "source" / "agents").glob("*/recipe.yaml")
    }


def _copy_agent(tmp_path: Path, agent_id: str = "dependency-reviewer") -> Path:
    source = repo_root() / "source" / "agents" / agent_id
    destination = tmp_path / agent_id
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("dist"))
    return destination / "recipe.yaml"


def test_model_recommendations_cover_supported_hosts_and_never_block_overrides():
    recommendations = {
        recommendation.host: recommendation
        for recommendation in HOST_MODEL_RECOMMENDATIONS
    }

    assert set(recommendations) == {
        "antigravity",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "cursor",
        "cursor-sdk",
        "gemini",
        "portable",
    }
    assert recommendations["claude-code"].recommended_model == "sonnet"
    assert recommendations["codex"].recommended_model == "gpt-5.6-luna"
    assert recommendations["codex"].standard_effort == "medium"
    assert recommendations["codex"].complex_remediation_effort == "high"
    assert recommendations["gemini"].recommended_model == "gemini-3.6-flash"
    assert recommendations["antigravity"].recommended_model == "Gemini 3.6 Flash (Low)"
    assert recommendations["antigravity"].standard_effort == "low"
    assert recommendations["antigravity"].complex_remediation_effort == "low"
    assert recommendations["cursor"].recommended_model == "composer-2.5"
    assert recommendations["claude-code"].selection_mode == "pinned"
    assert recommendations["codex"].selection_mode == "pinned"
    assert recommendations["gemini"].selection_mode == "pinned"
    assert recommendations["antigravity"].selection_mode == "host_pinned"
    assert recommendations["cursor"].selection_mode == "pinned"
    assert recommendations["cursor-sdk"].selection_mode == "pinned"
    assert recommendations["portable"].selection_mode == "runtime_selected"
    assert {
        recommendation.selection_mode for recommendation in recommendations.values()
    } <= ALLOWED_SELECTION_MODES
    assert all(recommendation.customer_override for recommendation in recommendations.values())


def test_model_recommendation_profiles_partition_all_eleven_agents():
    agent_ids = _canonical_agent_ids()
    payload = model_recommendations_payload(agent_ids)
    tiers = payload["agent_tiers"]
    standard = set(tiers["standard"]["agent_ids"])
    complex_remediation = set(tiers["complex_remediation"]["agent_ids"])

    assert len(agent_ids) == 11
    assert set(AGENT_MODEL_TIERS) == agent_ids
    assert complex_remediation == COMPLEX_REMEDIATION_AGENT_IDS
    assert standard | complex_remediation == agent_ids
    assert not standard & complex_remediation
    assert tiers["unclassified"]["agent_ids"] == []
    assert payload["policy"] == "recommendation_only"
    assert payload["acceptance"] == {
        "status": "target_for_release_qa",
        "source_commit": None,
        "acceptance_digest": None,
    }
    assert payload["customer_override_precedence"][0] == "explicit_customer_override"


def test_model_requirements_render_supported_and_recommended_columns():
    documentation = "\n".join(model_requirements_lines(_canonical_agent_ids()))

    assert "### Supported" in documentation
    assert "### Recommended" in documentation
    assert "not installation requirements" in documentation
    assert "never restrict a customer's model picker" in documentation
    assert "| Codex | `gpt-5.6-luna` | `medium` | `high` | `pinned` |" in documentation
    assert "| Antigravity CLI | `Gemini 3.6 Flash (Low)` | `low` | `low` |" in documentation
    assert "`host_pinned`" in documentation
    assert "`ai-sast-remediation, sca-remediation`" in documentation


@pytest.mark.publication
def test_publication_writes_machine_and_host_model_recommendations(tmp_path):
    recipe = _copy_agent(tmp_path)
    destination = tmp_path / "catalog"

    written = publish_recipe(recipe, destination, include_plugins=True)

    written_paths = {path.relative_to(destination).as_posix() for path in written}
    assert "model-recommendations.json" in written_paths
    assert "docs/model-recommendations.md" in written_paths
    contract = json.loads(
        (destination / "model-recommendations.json").read_text(encoding="utf-8")
    )
    assert contract["policy"] == "recommendation_only"
    assert contract["agent_tiers"]["standard"]["agent_ids"] == [
        "dependency-reviewer"
    ]
    assert "Recommended Model Configurations" in (
        destination / "README.md"
    ).read_text(encoding="utf-8")
    assert "Recommended model: `sonnet`" in (
        destination
        / "claude-code"
        / "dependency-reviewer"
        / "enterprise-edition"
        / "README.md"
    ).read_text(encoding="utf-8")
    assert "Recommended model: `gpt-5.6-luna`" in (
        destination / "codex" / "dependency-reviewer" / "README.md"
    ).read_text(encoding="utf-8")
    assert "Recommended model: `gemini-3.6-flash`" in (
        destination
        / "plugins"
        / "gemini"
        / "endor-labs-agent-kit"
        / "README.md"
    ).read_text(encoding="utf-8")
    assert "Recommended model: `Gemini 3.6 Flash (Low)`" in (
        destination
        / "plugins"
        / "antigravity"
        / "endor-labs-agent-kit"
        / "README.md"
    ).read_text(encoding="utf-8")
    assert "Recommended model: `composer-2.5`" in (
        destination / "cursor-sdk" / "README.md"
    ).read_text(encoding="utf-8")

    claude_agent = (
        destination
        / "claude-code"
        / "dependency-reviewer"
        / "enterprise-edition"
        / "dependency-reviewer.md"
    ).read_text(encoding="utf-8")
    codex_agent = next(
        (
            destination / "plugins" / "codex" / "endor-labs-agent-kit" / "agents"
        ).glob("*dependency-reviewer*.toml")
    ).read_text(encoding="utf-8")
    gemini_agent = (
        destination
        / "plugins"
        / "gemini"
        / "endor-labs-agent-kit"
        / "agents"
        / "dependency-reviewer.md"
    ).read_text(encoding="utf-8")
    cursor_agent = next(
        (destination / "agents").glob("*dependency-reviewer*.md")
    ).read_text(encoding="utf-8")
    cursor_sdk_runner = (
        destination / "cursor-sdk" / "run_cursor_agent.py"
    ).read_text(encoding="utf-8")

    assert "model: sonnet" in claude_agent.split("---", 2)[1]
    assert 'model = "gpt-5.6-luna"' in codex_agent
    assert 'model_reasoning_effort = "medium"' in codex_agent
    assert "model: gemini-3.6-flash" in gemini_agent.split("---", 2)[1]
    assert "model: composer-2.5[fast=false]" in cursor_agent.split("---", 2)[1]
    assert 'DEFAULT_MODEL = os.environ.get("CURSOR_MODEL", "composer-2.5")' in cursor_sdk_runner
    assert 'ModelParameterValue(id="fast", value="false")' in cursor_sdk_runner

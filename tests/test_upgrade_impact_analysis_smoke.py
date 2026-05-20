from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code, compile_claude_managed_agents, compile_raw

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "upgrade-impact-analysis"
    dst = tmp_path / "upgrade-impact-analysis"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_upgrade_impact_analysis_compiled_artifacts_carry_expected_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)

    developer = (
        recipe.parent / "dist" / "claude-code" / "developer-edition" / "upgrade-impact-analysis.md"
    ).read_text()
    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "upgrade-impact-analysis.md"
    ).read_text()

    for body in (developer, enterprise):
        assert "Endor Labs Upgrade Impact Analysis" in body
        assert "current_version" in body
        assert "target_version" in body
        assert "UPGRADE_NOW | UPGRADE_WITH_CAUTION | DEFER | INSUFFICIENT_DATA" in body
        assert "LOWER | SAME | HIGHER | UNKNOWN" in body
        assert "check_dependency_for_risks" in body
        assert "check_dependency_for_vulnerabilities" in body
        assert "get_endor_vulnerability" in body
        assert "data_gaps" in body
        assert "Never fabricate" in body

    assert "disallowedTools: Bash" in developer.split("---", 2)[1]
    assert "disallowedTools: Bash" not in enterprise.split("---", 2)[1]
    assert "Endor Platform VersionUpgrade UIA" in enterprise
    assert "--resource VersionUpgrade" in enterprise
    assert "spec.upgrade_info.is_best==true" in enterprise
    assert "spec.upgrade_info.worth_it==true" in enterprise
    assert "spec.finding_fixing_upgrades" in enterprise
    assert "--field-mask \"spec.upgrade_info\"" in enterprise
    assert "cia_results" in enterprise
    assert "direct_dependency_manifest_files" in enterprise
    assert "is_endor_patch" in enterprise
    assert "project_uuid" in enterprise
    assert "Do not make Endor project UUID knowledge a prerequisite" in enterprise
    assert "repository URL, owner/repo, or Endor project name" in enterprise
    assert "QuerySimilarPackages" in enterprise


def test_upgrade_impact_analysis_managed_agents_artifacts_carry_expected_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_managed_agents(recipe)

    developer = yaml.safe_load(
        (recipe.parent / "dist" / "claude-managed-agents" / "developer-edition" / "agent.yaml").read_text()
    )
    enterprise = yaml.safe_load(
        (recipe.parent / "dist" / "claude-managed-agents" / "enterprise-edition" / "agent.yaml").read_text()
    )

    assert developer["model"] == "claude-sonnet-4-6"
    assert developer["metadata"]["endor_agent_kit_recipe_id"] == "upgrade-impact-analysis"
    assert developer["tools"] == [
        {
            "type": "mcp_toolset",
            "mcp_server_name": "endor",
            "default_config": {"permission_policy": {"type": "always_ask"}},
        }
    ]
    assert "Managed Agents Developer Edition" in developer["system"]
    assert "Do not use Bash" in developer["system"]

    enterprise_tools = {tool["type"]: tool for tool in enterprise["tools"]}
    assert "mcp_toolset" in enterprise_tools
    assert enterprise_tools["agent_toolset_20260401"]["default_config"]["enabled"] is False
    assert enterprise_tools["agent_toolset_20260401"]["configs"][0]["name"] == "bash"
    assert "Managed Agents Enterprise Edition" in enterprise["system"]
    assert "endorctl api list" in enterprise["system"]
    assert "--resource VersionUpgrade" in enterprise["system"]
    assert "finding_fixing_upgrades" in enterprise["system"]
    assert "cia_results" in enterprise["system"]
    assert "project_uuid" in enterprise["system"]
    assert "Do not make Endor project UUID knowledge a prerequisite" in enterprise["system"]
    assert "repository URL, owner/repo, or Endor project name" in enterprise["system"]


def test_upgrade_impact_analysis_setup_doc_uses_agent_name(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_raw(recipe)

    setup = (recipe.parent / "dist" / "raw" / "endorctl-setup.md").read_text()
    assert "The Enterprise Edition Endor Labs Upgrade Impact Analysis uses" in setup
    assert "Dependency Decision Helper uses" not in setup


def test_upgrade_impact_analysis_eval_cases_cover_recommendations_and_deltas():
    evals = yaml.safe_load(
        (repo_root() / "source" / "agents" / "upgrade-impact-analysis" / "evals" / "cases.yaml").read_text()
    )

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "project-best-upgrade",
        "vulnerable-current-clean-target",
        "target-introduces-risk",
        "critical-current-fixed-target",
        "insufficient-data",
    }
    recommendations = {case["expected"]["upgrade_recommendation"] for case in evals["cases"]}
    assert recommendations == {"UPGRADE_NOW", "DEFER", "INSUFFICIENT_DATA"}
    deltas = {case["expected"]["risk_delta"] for case in evals["cases"]}
    assert deltas == {"LOWER", "HIGHER", "UNKNOWN"}

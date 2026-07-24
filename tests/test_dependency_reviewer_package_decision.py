from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code
from endor_agent_kit.knowledge_pack import load_knowledge_pack

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "dependency-reviewer"
    dst = tmp_path / "dependency-reviewer"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_dependency_reviewer_package_decision_compiled_artifacts_carry_load_bearing_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)

    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-reviewer-package-decision.md"
    ).read_text()

    assert (recipe.parent / "dist" / "claude-code" / "developer-edition").is_dir()
    assert "Dependency Reviewer" in enterprise
    assert "mcpServers:" in enterprise
    assert "endor-cli-tools:" in enterprise
    assert "alwaysLoad: true" in enterprise
    assert "check_dependency_for_risks" in enterprise
    assert "check_dependency_for_vulnerabilities" in enterprise
    assert "get_endor_vulnerability" in enterprise
    assert "Never fabricate" in enterprise
    assert "data_gaps" in enterprise
    assert "malware or a tenant firewall malware block" in enterprise
    assert "CISA KEV" in enterprise
    assert "`NOT_RECOMMENDED` for `package-decision` or `UNKNOWN` for a risk profile" in enterprise
    assert "`profile`, `verdict`, `conditions`, `alternatives`" in enterprise
    assert "Keep tenant/project lookups out of scope unless the request needs them" in enterprise
    assert "retry that lookup\nwith `--traverse`" in enterprise
    assert "## Repository Inspection Rules" not in enterprise
    assert "## Risk Postures" not in enterprise


def test_eval_cases_cover_v0_outcomes():
    evals = yaml.safe_load((repo_root() / "source" / "agents" / "dependency-reviewer" / "evals" / "cases.yaml").read_text())

    cases = [case for case in evals["cases"] if case["input"]["task_profile"] == "package-decision"]
    assert {case["id"] for case in cases} == {"package-decision-safe", "package-decision-blocked"}
    assert {case["expected"]["verdict"] for case in cases} == {"SAFE", "BLOCKED"}


def test_package_profiles_prefer_exact_mcp_risk_without_broad_finding_fallback():
    workflow = load_knowledge_pack().workflow_for("dependency-reviewer")
    assert workflow is not None
    by_profile = {
        profile_id: [
            recipe
            for recipe in workflow.evidence_query_recipes
            if recipe.profile_id == profile_id
        ]
        for profile_id in ("package-decision", "package-risk")
    }

    for profile_id, recipes in by_profile.items():
        templates = "\n".join(recipe.template for recipe in recipes)
        resources = {recipe.resource for recipe in recipes}
        assert "check_dependency_for_risks" in templates
        assert "Finding" not in resources
        assert "endorctl agent api" not in templates or "PackageVersion" in resources

    decision_ids = {recipe.id for recipe in by_profile["package-decision"]}
    assert "decision-package-risk-exact" in decision_ids
    assert "decision-selected-package-findings" not in decision_ids

    decision_plan = next(
        plan
        for plan in workflow.evidence_query_plans
        if plan.profile_id == "package-decision"
    )
    plan_text = "\n".join(
        (*decision_plan.query_order, *decision_plan.avoid, *decision_plan.stop_after)
    )
    assert "at most two" in plan_text
    assert "broad Finding" in plan_text
    assert "exact PackageVersion" in plan_text

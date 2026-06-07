from __future__ import annotations

from conftest import repo_root


def test_ci_workflow_uses_source_agent_recipes():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    assert "source/agents/*/recipe.yaml" in workflow
    assert "portable" in workflow
    assert "for recipe in agents/*/recipe.yaml" not in workflow
    assert "publish agents/*/recipe.yaml" not in workflow
    removed_plugin_path = "github-" + "co" + "pilot-plugin"
    assert removed_plugin_path not in workflow


def test_ci_workflow_runs_guardrail_conformance_check():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    # The guardrail conformance gate must stay wired into CI; this test fails if
    # the step is removed or renamed so it cannot quietly disappear.
    assert "endor-agent-kit check-guardrails --catalog-root ." in workflow


def test_ci_workflow_runs_endor_context_freshness_check():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    assert "endor-agent-kit verify-endor-context --upstream" in workflow

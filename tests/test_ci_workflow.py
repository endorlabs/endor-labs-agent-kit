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


def test_ci_workflow_runs_registry_check_against_pinned_spec():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    assert "python scripts/generate_endor_api_registry.py --check --spec source/endor-context/openapiv2.swagger.json" in workflow


def test_ci_workflow_runs_endor_context_freshness_check():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    # Offline payload validation stays blocking; the upstream freshness check
    # stays wired in but reports drift as a non-blocking warning because
    # upstream Endor releases are not failures of the commit under test.
    assert "endor-agent-kit verify-endor-context\n" in workflow
    assert "endor-agent-kit verify-endor-context --upstream" in workflow
    assert "Endor context drift" in workflow


def test_refresh_endor_context_workflow_reports_manual_freshness():
    workflow = (
        repo_root() / ".github" / "workflows" / "refresh-endor-context.yml"
    ).read_text()

    # The scheduled refresh lane must keep re-pinning provenance from upstream
    # and verifying it, but company policy requires humans to open refresh PRs.
    assert "schedule" in workflow
    assert "endor-agent-kit refresh-endor-context" in workflow
    assert "endor-agent-kit verify-endor-context --upstream" in workflow
    assert "python scripts/generate_endor_api_registry.py --check --spec source/endor-context/openapiv2.swagger.json" in workflow
    assert "source/endor-context/openapiv2.swagger.json" in workflow
    assert "Manual Endor context refresh needed" in workflow
    assert "contents: read" in workflow
    assert "pull-requests: write" not in workflow
    assert "gh pr create" not in workflow
    assert "git push" not in workflow
    assert "endor-context-refresh" not in workflow

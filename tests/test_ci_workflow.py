from __future__ import annotations

from conftest import repo_root


def test_ci_workflow_uses_source_agent_recipes():
    workflow = (repo_root() / ".github" / "workflows" / "agent-kit-ci.yml").read_text()

    assert "source/agents/*/recipe.yaml" in workflow
    assert "for recipe in agents/*/recipe.yaml" not in workflow
    assert "publish agents/*/recipe.yaml" not in workflow
    removed_plugin_path = "github-" + "co" + "pilot-plugin"
    assert removed_plugin_path not in workflow

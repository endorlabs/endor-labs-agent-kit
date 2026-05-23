from __future__ import annotations

from conftest import repo_root


def test_create_endor_labs_agent_skill_is_available_and_actionable():
    skill = repo_root() / "skills" / "create-endor-labs-agent" / "SKILL.md"

    content = skill.read_text()

    assert "name: create-endor-labs-agent" in content
    assert "Create Endor Labs Agent" in content
    assert "source/agents/<agent-id>/recipe.yaml" in content
    assert "source/agents/<agent-id>/instructions.md" in content
    assert "source/agents/<agent-id>/evals/cases.yaml" in content
    assert "source/agents/<agent-id>/architecture.svg" in content
    assert "Generic agent blueprint" in content
    assert "default to MCP-free `endorctl_api`" in content
    assert "must not depend on proprietary source" in content
    assert "endor-agent-kit validate source/agents/<agent-id>/recipe.yaml" in content
    assert "endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune" in content
    assert "Read`, `Glob`, `Grep`, and\n`LS`" in content


def test_generated_readme_points_contributors_to_create_agent_skill():
    readme = (repo_root() / "README.md").read_text()

    assert "## Contribute An Agent" in readme
    assert "### Create Agents With The Skill" in readme
    assert "Use the Create Endor Labs Agent skill to make your own Endor Labs agent." in readme
    assert "skills/create-endor-labs-agent/SKILL.md" in readme
    assert "Use the create Endor Labs agent skill to make an agent" in readme
    assert "generic sanitized agent blueprint" in readme
    assert "source/agents/<agent>/architecture.svg" in readme

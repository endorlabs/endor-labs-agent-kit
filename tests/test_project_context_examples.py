from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.publisher import publish_recipe

from conftest import repo_root


def _copy_agent(tmp_path: Path, agent_id: str) -> Path:
    src = repo_root() / "source" / "agents" / agent_id
    dst = tmp_path / agent_id
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_upgrade_impact_managed_readme_uses_project_selector_not_uuid(tmp_path):
    recipe = _copy_agent(tmp_path, "upgrade-impact-analysis")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    readme = (
        dest
        / "claude-managed-agents"
        / "upgrade-impact-analysis"
        / "enterprise-edition"
        / "README.md"
    ).read_text()

    assert "repository <owner>/<repo> package lodash" in readme
    assert "<project_uuid>" not in readme
    assert "project UUID" in readme
    assert "![Endor Labs Upgrade Impact Analysis architecture](architecture.svg)" in readme
    assert (
        dest
        / "claude-managed-agents"
        / "upgrade-impact-analysis"
        / "enterprise-edition"
        / "architecture.svg"
    ).is_file()


def test_remediation_planner_uses_repository_context_not_required_uuid(tmp_path):
    recipe = _copy_agent(tmp_path, "remediation-planner")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    data = yaml.safe_load(recipe.read_text())
    project_uuid = next(field for field in data["inputs"] if field["name"] == "project_uuid")
    readme = (
        dest / "claude-code" / "remediation-planner" / "enterprise-edition" / "README.md"
    ).read_text()
    prompt = (
        dest / "claude-code" / "remediation-planner" / "enterprise-edition" / "remediation-planner.md"
    ).read_text()

    assert project_uuid["required"] is False
    assert "@agent-remediation-planner preview remediation options for this repository" in readme
    assert "<project_uuid>" not in readme
    assert "Do not require the user to know an Endor project UUID" in prompt
    assert "Only ask for a project UUID when human-readable selectors cannot" in prompt
    assert "![Remediation Planner architecture](architecture.svg)" in readme
    assert (
        dest / "claude-code" / "remediation-planner" / "enterprise-edition" / "architecture.svg"
    ).is_file()

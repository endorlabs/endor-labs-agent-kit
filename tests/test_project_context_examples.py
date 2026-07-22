from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from endor_agent_kit.publisher import publish_recipe

from conftest import repo_root


def _copy_agent(tmp_path: Path, agent_id: str) -> Path:
    src = repo_root() / "source" / "agents" / agent_id
    dst = tmp_path / agent_id
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


@pytest.mark.publication
def test_upgrade_impact_managed_readme_uses_project_selector_not_uuid(tmp_path):
    recipe = _copy_agent(tmp_path, "oss-upgrade-investigator")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    readme = (
        dest
        / "claude-managed-agents"
        / "oss-upgrade-investigator"
        / "README.md"
    ).read_text()

    assert "repository <owner>/<repo> package lodash" in readme
    assert "<project_uuid>" not in readme
    assert "project UUID" in readme
    assert "![OSS Upgrade Investigator architecture](architecture.svg)" in readme
    assert (
        dest
        / "claude-managed-agents"
        / "oss-upgrade-investigator"
        / "architecture.svg"
    ).is_file()


@pytest.mark.publication
def test_remediation_planning_uses_repository_context_not_required_uuid(tmp_path):
    recipe = _copy_agent(tmp_path, "remediation-planning")
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    data = yaml.safe_load(recipe.read_text())
    project_uuid = next(field for field in data["inputs"] if field["name"] == "project_uuid")
    agent_dir = dest / "claude-code" / "remediation-planning"
    readme = (agent_dir / "README.md").read_text()
    prompt = (agent_dir / "remediation-planning.md").read_text()

    assert project_uuid["required"] is False
    assert "@agent-remediation-planning preview remediation options for this repository" in readme
    assert "<project_uuid>" not in readme
    assert "Do not require the user to know an Endor project UUID" in prompt
    assert "Only ask for a project UUID when human-readable selectors cannot" in prompt
    assert "Default project-scoped Endor lookups to `context.type==CONTEXT_TYPE_MAIN`" in prompt
    assert "![Remediation Planning architecture](architecture.svg)" in readme
    assert (agent_dir / "architecture.svg").is_file()
    assert not (agent_dir / "enterprise-edition").exists()

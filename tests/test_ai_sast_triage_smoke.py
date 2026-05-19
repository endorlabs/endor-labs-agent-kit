from __future__ import annotations

import shutil
from pathlib import Path

from endor_agent_kit.publisher import publish_recipe

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "ai-sast-triage"
    dst = tmp_path / "ai-sast-triage"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_ai_sast_triage_does_not_require_project_uuid_for_normal_use(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    root_readme = (dest / "README.md").read_text()
    agent_readme = (
        dest / "claude-code" / "ai-sast-triage" / "enterprise-edition" / "README.md"
    ).read_text()
    prompt = (
        dest / "claude-code" / "ai-sast-triage" / "enterprise-edition" / "ai-sast-triage.md"
    ).read_text()

    assert "@agent-ai-sast-triage triage AI SAST findings for this repository" in root_readme
    assert "Do not open a PR until I approve the patch" in agent_readme
    assert "<project_uuid>" not in agent_readme
    assert "<project_uuid>" not in prompt
    assert "Do not require the user to know an Endor project UUID" in prompt
    assert "read the current repository root and `origin` remote URL" in prompt
    assert "ask the user to choose one" in prompt
    assert (dest / "claude-code" / "ai-sast-triage" / "enterprise-edition" / "architecture.svg").is_file()
    assert "![AI SAST Triage architecture](architecture.svg)" in agent_readme
    assert "PR/MR creation is host-mediated" in agent_readme

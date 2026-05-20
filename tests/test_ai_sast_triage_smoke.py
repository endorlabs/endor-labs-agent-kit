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
    agent_dir = dest / "claude-code" / "ai-sast-triage"
    agent_readme = (agent_dir / "README.md").read_text()
    prompt = (agent_dir / "ai-sast-triage.md").read_text()

    assert "@agent-ai-sast-triage triage AI SAST findings for this repository" in root_readme
    assert "Do not open a PR until I approve the patch" in agent_readme
    assert "<project_uuid>" not in agent_readme
    assert "<project_uuid>" not in prompt
    assert "Do not require the user to know an Endor project UUID" in prompt
    assert "mcpServers:" not in prompt
    assert "ai-tools" not in prompt
    assert "Do not require or start an Endor MCP server" in prompt
    assert "read the current repository root and `origin` remote URL" in prompt
    assert "ask the user to choose one" in prompt
    assert "Project scoping is mandatory" in prompt
    assert "Exploit Reproduction" in prompt
    assert "Remediation Guidance" in prompt
    assert "Use Exploit Reproduction for prioritization and validation planning" in prompt
    assert "Redact concrete exploit strings from PR/MR bodies" in prompt
    assert "Treat Remediation Guidance as advisory evidence, not an authority" in prompt
    assert "remediation_guidance_used" in prompt
    assert "exploit_reproduction_used" in prompt
    assert "safe local validation" in prompt
    assert "<!-- endor-agent-kit:ai-sast-context " in prompt
    assert "Do not claim that an Endor exception policy was created" in prompt
    assert "## Action Contracts" in prompt
    assert "open-change-request" in prompt
    assert "write-exception-policy" in prompt
    assert "availability: `available`" in prompt
    assert "`rule` containing the full Rego source" in prompt
    assert "Never use a `rego` field" in prompt
    assert '`"$uuid=PROJECT_UUID"`' in prompt
    assert "do not guess alternate live write shapes" in prompt
    assert (agent_dir / "architecture.svg").is_file()
    assert (agent_dir / "actions.yaml").is_file()
    assert not (agent_dir / "enterprise-edition").exists()
    assert "![AI SAST Triage architecture](architecture.svg)" in agent_readme
    assert "PR/MR creation is host-mediated" in agent_readme
    assert "Setup Checklist" in agent_readme
    assert "gh auth status" in agent_readme
    assert "does not need an Endor MCP server" in agent_readme
    assert "AppSec approvers: @alice, @bob, @endor-labs/appsec" in agent_readme
    assert "Understand Finding Evidence" in agent_readme
    assert "uses it as" in agent_readme
    assert "APPSEC APPROVED: accept risk" in agent_readme
    assert "QA Smoke Test" in agent_readme
    assert "CLAUDE_CONFIG_DIR" in agent_readme
    assert "AppSec approver list" in agent_readme
    assert "approval.verify" in prompt
    assert "standalone PR/MR approval workflow" in prompt
    assert "Never let the developer requesting an exception self-approve it" in prompt
    assert "GitHub App/GitLab webhook" not in agent_readme

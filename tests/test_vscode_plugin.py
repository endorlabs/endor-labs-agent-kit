from __future__ import annotations

import json

import pytest
import yaml

from conftest import GeneratedCatalog

VSCODE_PACKAGE = "plugins/vscode/endor-labs-agent-kit"
MUTATING_AGENTS = {"ai-sast-remediation", "sca-remediation"}


def _package(catalog: GeneratedCatalog):
    return catalog.root / VSCODE_PACKAGE


@pytest.mark.publication
def test_vscode_package_has_workspace_overlay_layout(generated_catalog: GeneratedCatalog):
    package = _package(generated_catalog)

    assert (package / ".github" / "copilot-instructions.md").is_file()
    assert (package / ".vscode" / "mcp.json").is_file()
    assert (package / "runtime" / "summarize_endor_artifact.py").is_file()
    assert (package / "assets" / "logo.png").is_file()
    assert (package / "README.md").is_file()
    # Copy-into-workspace overlay: no plugin-marketplace manifest, no hooks.
    assert not (package / "plugin.json").exists()
    assert not (package / ".github" / "plugin.json").exists()
    assert not (package / "hooks").exists()

    agents = sorted(p.stem.removesuffix(".agent") for p in (package / ".github" / "agents").glob("*.agent.md"))
    assert len(agents) == 11
    skills = sorted(p.name for p in (package / ".github" / "skills").iterdir() if p.is_dir())
    assert len(skills) == 12
    assert "endor-agent-kit-setup" in skills


@pytest.mark.publication
def test_vscode_mcp_uses_servers_key_not_mcp_servers(generated_catalog: GeneratedCatalog):
    mcp = json.loads((_package(generated_catalog) / ".vscode" / "mcp.json").read_text(encoding="utf-8"))

    assert "servers" in mcp
    assert "mcpServers" not in mcp
    server = mcp["servers"]["endor-cli-tools"]
    assert server["type"] == "stdio"
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "endorctl", "ai-tools", "mcp-server"]


@pytest.mark.publication
def test_vscode_skill_names_match_their_directories(generated_catalog: GeneratedCatalog):
    for skill in sorted((_package(generated_catalog) / ".github" / "skills").glob("*/SKILL.md")):
        frontmatter = yaml.safe_load(skill.read_text(encoding="utf-8").split("---", 2)[1])
        assert frontmatter["name"] == skill.parent.name


@pytest.mark.publication
def test_vscode_agents_scope_edit_tools_to_mutating_workflows(generated_catalog: GeneratedCatalog):
    for agent in sorted((_package(generated_catalog) / ".github" / "agents").glob("*.agent.md")):
        agent_id = agent.name.removesuffix(".agent.md")
        text = agent.read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---", 2)[1])

        assert frontmatter["target"] == "vscode"
        assert "model" not in frontmatter
        assert "mcpServers" not in frontmatter
        assert "endor_agent_kit_managed=true" in text
        assert "## VS Code Host Contract" in text

        tools = set(frontmatter.get("tools") or [])
        # Read-only workflows still run endorctl via the shell tool.
        assert "runCommands" in tools
        if agent_id in MUTATING_AGENTS:
            assert {"editFiles", "changes"} <= tools
            assert "separate approval gates" in text
        else:
            assert "editFiles" not in tools
            assert "changes" not in tools
            assert "Keep the workflow read-only" in text


@pytest.mark.publication
def test_vscode_copilot_instructions_and_setup_carry_mcp_caveat(generated_catalog: GeneratedCatalog):
    package = _package(generated_catalog)
    instructions = (package / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    # copilot-instructions.md is globally applied and needs no frontmatter.
    assert not instructions.lstrip().startswith("---")
    assert "Do not assume Endor MCP is configured" in instructions
    assert "endor-agent-kit-setup" in instructions

    setup = (package / ".github" / "skills" / "endor-agent-kit-setup" / "SKILL.md").read_text(encoding="utf-8")
    assert "Do not add plugin-wide MCP automatically" in setup
    assert "VS Code custom agents are host-managed" in setup

from __future__ import annotations

import json

import pytest
import yaml

from conftest import GeneratedCatalog

VSCODE_PACKAGE = "plugins/vscode/endor-labs-agent-kit"
MUTATING_AGENTS = {"ai-sast-remediation", "sca-remediation"}
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"


def _package(catalog: GeneratedCatalog):
    return catalog.root / VSCODE_PACKAGE


@pytest.mark.publication
def test_vscode_package_has_agent_plugin_layout(generated_catalog: GeneratedCatalog):
    package = _package(generated_catalog)

    assert (package / "plugin.json").is_file()
    assert (package / "mcp.json").is_file()
    assert (package / "runtime" / "summarize_endor_artifact.py").is_file()
    assert (package / "assets" / "logo.png").is_file()
    assert (package / "README.md").is_file()
    assert (package / "com.github.copilot" / "rules" / "endor-labs-agent-kit.md").is_file()
    # Agent Plugin, not a .vsix extension and not a .github overlay.
    assert not (package / "package.json").exists()
    assert not (package / "extension.js").exists()
    assert not (package / ".vscodeignore").exists()
    assert not (package / ".github").exists()
    assert not (package / ".vscode").exists()

    agents = sorted(p.stem.removesuffix(".agent") for p in (package / "com.github.copilot" / "agents").glob("*.agent.md"))
    assert len(agents) == 11
    skills = sorted(p.name for p in (package / "skills").iterdir() if p.is_dir())
    assert len(skills) == 12
    assert "endor-agent-kit-setup" in skills


@pytest.mark.publication
def test_vscode_plugin_manifest_is_agent_plugins_1_0(generated_catalog: GeneratedCatalog):
    manifest = json.loads((_package(generated_catalog) / "plugin.json").read_text(encoding="utf-8"))

    assert manifest["$schema"] == PLUGIN_SCHEMA
    assert manifest["name"] == "endor-labs-agent-kit"
    assert manifest["version"]
    # Root additionalProperties:false — no extension-only keys leak in.
    assert "icon" not in manifest
    assert "main" not in manifest
    assert "contributes" not in manifest
    assert "engines" not in manifest


@pytest.mark.publication
def test_vscode_mcp_uses_mcp_servers_key(generated_catalog: GeneratedCatalog):
    mcp = json.loads((_package(generated_catalog) / "mcp.json").read_text(encoding="utf-8"))

    assert mcp["$schema"] == MCP_SCHEMA
    assert "servers" not in mcp
    server = mcp["mcpServers"]["endor-cli-tools"]
    assert server["type"] == "stdio"
    assert server["command"] == "npx"
    assert server["args"] == ["-y", "endorctl", "ai-tools", "mcp-server"]


@pytest.mark.publication
def test_vscode_skill_names_match_their_directories(generated_catalog: GeneratedCatalog):
    for skill in sorted((_package(generated_catalog) / "skills").glob("*/SKILL.md")):
        frontmatter = yaml.safe_load(skill.read_text(encoding="utf-8").split("---", 2)[1])
        assert frontmatter["name"] == skill.parent.name


@pytest.mark.publication
def test_vscode_agents_scope_edit_tools_to_mutating_workflows(generated_catalog: GeneratedCatalog):
    agents_dir = _package(generated_catalog) / "com.github.copilot" / "agents"
    for agent in sorted(agents_dir.glob("*.agent.md")):
        agent_id = agent.name.removesuffix(".agent.md")
        text = agent.read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(text.split("---", 2)[1])

        assert "model" not in frontmatter
        assert "mcpServers" not in frontmatter
        assert "endor_agent_kit_managed=true" in text
        assert "## VS Code Host Contract" in text

        tools = set(frontmatter.get("tools") or [])
        assert "runCommands" in tools
        if agent_id in MUTATING_AGENTS:
            assert {"editFiles", "changes"} <= tools
            assert "separate approval gates" in text
        else:
            assert "editFiles" not in tools
            assert "changes" not in tools
            assert "Keep the workflow read-only" in text


@pytest.mark.publication
def test_vscode_rules_and_setup_carry_mcp_caveat(generated_catalog: GeneratedCatalog):
    package = _package(generated_catalog)
    rules = (package / "com.github.copilot" / "rules" / "endor-labs-agent-kit.md").read_text(encoding="utf-8")
    assert "Do not assume Endor MCP is configured" in rules
    assert "endor-agent-kit-setup" in rules

    setup = (package / "skills" / "endor-agent-kit-setup" / "SKILL.md").read_text(encoding="utf-8")
    assert "Do not add plugin-wide MCP automatically" in setup
    assert "Copilot custom agents are host-managed" in setup

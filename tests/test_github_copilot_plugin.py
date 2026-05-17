from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from endor_agent_kit.cli import main
from endor_agent_kit.compilers import compile_github_copilot_plugin

from conftest import repo_root


def _copy_agent(tmp_path: Path, agent_id: str = "vulnerability-explainer") -> Path:
    src = repo_root() / "agents" / agent_id
    dst = tmp_path / agent_id
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_github_copilot_plugin_compiler_emits_vulnerability_explainer_packages(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_github_copilot_plugin(recipe)

    output_paths = {path.relative_to(recipe.parent).as_posix() for path in outputs}
    assert output_paths == {
        "dist/github-copilot-plugin/developer-edition/plugin.json",
        "dist/github-copilot-plugin/developer-edition/agents/vulnerability-explainer.agent.md",
        "dist/github-copilot-plugin/developer-edition/README.md",
        "dist/github-copilot-plugin/enterprise-edition/plugin.json",
        "dist/github-copilot-plugin/enterprise-edition/agents/vulnerability-explainer.agent.md",
        "dist/github-copilot-plugin/enterprise-edition/README.md",
    }

    developer_root = recipe.parent / "dist" / "github-copilot-plugin" / "developer-edition"
    enterprise_root = recipe.parent / "dist" / "github-copilot-plugin" / "enterprise-edition"
    developer_manifest = json.loads((developer_root / "plugin.json").read_text())
    enterprise_manifest = json.loads((enterprise_root / "plugin.json").read_text())

    assert developer_manifest["name"] == "endor-labs-vulnerability-explainer-developer"
    assert enterprise_manifest["name"] == "endor-labs-vulnerability-explainer-enterprise"
    assert developer_manifest["agents"] == "agents/"
    assert enterprise_manifest["agents"] == "agents/"

    developer = (developer_root / "agents" / "vulnerability-explainer.agent.md").read_text()
    enterprise = (enterprise_root / "agents" / "vulnerability-explainer.agent.md").read_text()

    developer_header = _frontmatter(developer)
    enterprise_header = _frontmatter(enterprise)

    for body, header in ((developer, developer_header), (enterprise, enterprise_header)):
        assert header["name"] == "Endor Labs Vulnerability Explainer"
        assert header["target"] == "github-copilot"
        assert header["disable-model-invocation"] is True
        assert header["user-invocable"] is True
        assert header["tools"] == ["endor-cli-tools/get_endor_vulnerability"]
        server = header["mcp-servers"]["endor-cli-tools"]
        assert server["type"] == "stdio"
        assert server["command"] == "npx"
        assert server["args"] == ["-y", "endorctl", "ai-tools", "mcp-server"]
        assert server["tools"] == ["get_endor_vulnerability"]
        assert header["metadata"]["endor_agent_id"] == "vulnerability-explainer"
        assert "Endor Labs Vulnerability Explainer" in body
        assert "Never fabricate" in body
        assert "CRITICAL_ACTION_REQUIRED" in body
        assert "data_gaps" in body
        assert "endorctl api list" not in body
        assert "execute" not in header["tools"]

    assert "env" not in developer_header["mcp-servers"]["endor-cli-tools"]
    assert enterprise_header["mcp-servers"]["endor-cli-tools"]["env"] == {
        "ENDOR_GITHUB_ACTION_TOKEN_ENABLE": "true",
        "ENDOR_NAMESPACE": "$COPILOT_MCP_ENDOR_NAMESPACE",
        "ENDOR_API": "${COPILOT_MCP_ENDOR_API:-https://api.endorlabs.com}",
    }
    assert "Developer Edition. MCP-only" in developer
    assert "Enterprise Edition. MCP-only" in enterprise


def test_github_copilot_plugin_enterprise_enables_execute_only_for_endorctl_agents(tmp_path):
    recipe = _copy_agent(tmp_path, "dependency-decision-helper")

    compile_github_copilot_plugin(recipe)

    plugin_root = recipe.parent / "dist" / "github-copilot-plugin"
    developer_body = (
        plugin_root / "developer-edition" / "agents" / "dependency-decision-helper.agent.md"
    ).read_text()
    enterprise_body = (
        plugin_root / "enterprise-edition" / "agents" / "dependency-decision-helper.agent.md"
    ).read_text()
    developer = _frontmatter(developer_body)
    enterprise = _frontmatter(enterprise_body)

    assert "execute" not in developer["tools"]
    assert enterprise["tools"] == [
        "endor-cli-tools/check_dependency_for_risks",
        "endor-cli-tools/check_dependency_for_vulnerabilities",
        "endor-cli-tools/get_endor_vulnerability",
        "execute",
    ]
    assert "PackageVersion UUID Lookup" in enterprise_body
    assert "endorctl api list" in enterprise_body
    assert enterprise["mcp-servers"]["endor-cli-tools"]["env"]["ENDOR_GITHUB_ACTION_TOKEN_ENABLE"] == "true"


def test_github_copilot_plugin_honors_enterprise_only_host_editions(tmp_path):
    recipe = _copy_agent(tmp_path, "tenant-findings")

    outputs = compile_github_copilot_plugin(recipe)

    output_paths = {path.relative_to(recipe.parent).as_posix() for path in outputs}
    assert output_paths == {
        "dist/github-copilot-plugin/enterprise-edition/plugin.json",
        "dist/github-copilot-plugin/enterprise-edition/agents/tenant-findings.agent.md",
        "dist/github-copilot-plugin/enterprise-edition/README.md",
    }
    assert not (recipe.parent / "dist" / "github-copilot-plugin" / "developer-edition").exists()
    body = (
        recipe.parent
        / "dist"
        / "github-copilot-plugin"
        / "enterprise-edition"
        / "agents"
        / "tenant-findings.agent.md"
    ).read_text()
    header = _frontmatter(body)
    assert header["metadata"]["endor_agent_id"] == "tenant-findings"
    assert header["tools"] == ["endor-cli-tools/get_resource", "execute"]
    assert "FINDING_TAGS_REACHABLE_FUNCTION" in body


def test_cli_compiles_github_copilot_plugin_edition(tmp_path, capsys):
    recipe = _copy_agent(tmp_path)

    status = main([
        "compile",
        str(recipe),
        "--target",
        "github-copilot-plugin",
        "--edition",
        "developer-edition",
    ])
    output = capsys.readouterr().out

    assert status == 0
    assert "github-copilot-plugin/developer-edition/plugin.json" in output
    assert "github-copilot-plugin/developer-edition/agents/vulnerability-explainer.agent.md" in output
    assert not (recipe.parent / "dist" / "github-copilot-plugin" / "enterprise-edition").exists()


def _frontmatter(agent_markdown: str) -> dict:
    header = agent_markdown.split("---", 2)[1]
    return yaml.safe_load(header)

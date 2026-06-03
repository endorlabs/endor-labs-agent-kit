from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import yaml

from endor_agent_kit.cli import main
from endor_agent_kit.compilers import (
    compile_claude_code,
    compile_claude_managed_agents,
    compile_codex,
    compile_gemini,
    compile_raw,
)
from endor_agent_kit.compilers.claude_code import _disallowed_tools
from endor_agent_kit.recipe import HostCapabilities, EndorAgentRecipe

from conftest import repo_root


ENTERPRISE_EDITION_SHA256 = "2c1a5a843ecfdae2a3319859c9efa841db4f71dabc0b79761671e36ad75e96c5"


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "dependency-decision-helper"
    dst = tmp_path / "dependency-decision-helper"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def _minimal_recipe(*, read_files: bool) -> EndorAgentRecipe:
    return EndorAgentRecipe(
        recipe_schema_version=1,
        id="read-only-fixture",
        name="Read Only Fixture",
        version="1.0.0",
        description="Fixture",
        safety_class="read_only",
        supported_transports=("mcp",),
        host_capabilities_required=HostCapabilities(read_files=read_files),
        inputs=(),
        outputs=(),
        evals="evals/cases.yaml",
        compatible_hosts=("claude-code",),
        mutations=(),
        required_endor_mcp_tools=("get_resource",),
        instructions_path="instructions.md",
        model="sonnet",
    )


def test_claude_code_compiler_emits_selected_customer_artifact(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_claude_code(recipe)

    assert [path.name for path in outputs] == [
        "dependency-decision-helper.md",
    ]
    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-decision-helper.md"
    ).read_text()

    enterprise_header = enterprise.split("---", 2)[1]
    assert "\ntools:" not in enterprise_header
    assert not (recipe.parent / "dist" / "claude-code" / "developer-edition").exists()
    assert "mcpServers:" in enterprise_header
    assert "endor-cli-tools:" in enterprise_header
    assert "alwaysLoad: true" in enterprise_header
    assert "disallowedTools: Bash" not in enterprise_header
    assert "model: sonnet" in enterprise_header
    assert "endorctl api list" in enterprise
    assert "data_gaps" in enterprise


def test_claude_code_disallowed_tools_allow_read_only_file_access():
    disallowed = set(_disallowed_tools(_minimal_recipe(read_files=True)))

    assert not {"Read", "Glob", "Grep", "LS"} & disallowed
    assert {"Write", "Edit", "MultiEdit", "NotebookRead", "NotebookEdit"} <= disallowed
    assert "WebFetch" in disallowed
    assert "TodoWrite" in disallowed


def test_claude_code_disallowed_tools_block_file_access_by_default():
    disallowed = set(_disallowed_tools(_minimal_recipe(read_files=False)))

    assert {"Read", "Glob", "Grep", "LS"} <= disallowed
    assert {"Write", "Edit", "MultiEdit", "NotebookRead", "NotebookEdit"} <= disallowed


def test_claude_code_compiler_edition_filter(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_claude_code(recipe, edition="developer-edition")

    assert len(outputs) == 1
    assert outputs[0].parent.name == "developer-edition"
    assert not (recipe.parent / "dist" / "claude-code" / "enterprise-edition").exists()


def test_claude_managed_agents_compiler_emits_selected_customer_artifact(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_claude_managed_agents(recipe)

    assert [path.name for path in outputs] == [
        "agent.yaml",
        "environment.yaml",
        "session-template.yaml",
    ]
    enterprise = yaml.safe_load(
        (recipe.parent / "dist" / "claude-managed-agents" / "enterprise-edition" / "agent.yaml").read_text()
    )
    enterprise_environment = yaml.safe_load(
        (
            recipe.parent
            / "dist"
            / "claude-managed-agents"
            / "enterprise-edition"
            / "environment.yaml"
        ).read_text()
    )

    assert not (recipe.parent / "dist" / "claude-managed-agents" / "developer-edition").exists()

    assert enterprise["model"] == "claude-sonnet-4-6"
    assert enterprise["mcp_servers"][0]["type"] == "url"
    assert enterprise["mcp_servers"][0]["name"] == "endor"
    enterprise_tools = {tool["type"]: tool for tool in enterprise["tools"]}
    assert "mcp_toolset" in enterprise_tools
    assert enterprise_tools["agent_toolset_20260401"]["default_config"]["enabled"] is False
    assert enterprise_tools["agent_toolset_20260401"]["configs"] == [
        {
            "name": "bash",
            "enabled": True,
            "permission_policy": {"type": "always_ask"},
        }
    ]
    assert "endorctl api list" in enterprise["system"]
    assert enterprise_environment["name"] == "endor-dependency-decision-helper"
    assert enterprise_environment["config"]["packages"] == {"npm": ["endorctl"]}


def test_claude_code_compiler_accepts_legacy_variant_aliases(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_claude_code(recipe, variant="standard")

    assert len(outputs) == 1
    assert outputs[0].parent.name == "developer-edition"
    assert not (recipe.parent / "dist" / "claude-code" / "standard").exists()


def test_cli_compiles_named_edition_and_legacy_variant_alias(tmp_path, capsys):
    developer_recipe = _copy_agent(tmp_path / "developer")
    enterprise_recipe = _copy_agent(tmp_path / "enterprise")

    developer_status = main([
        "compile",
        str(developer_recipe),
        "--target",
        "claude-code",
        "--edition",
        "developer-edition",
    ])
    developer_output = capsys.readouterr().out
    enterprise_status = main([
        "compile",
        str(enterprise_recipe),
        "--target",
        "claude-code",
        "--variant",
        "extended",
    ])
    enterprise_output = capsys.readouterr().out

    assert developer_status == 0
    assert enterprise_status == 0
    assert "developer-edition/dependency-decision-helper.md" in developer_output
    assert "enterprise-edition/dependency-decision-helper.md" in enterprise_output


def test_cli_compiles_claude_managed_agents_target(tmp_path, capsys):
    recipe = _copy_agent(tmp_path)

    status = main([
        "compile",
        str(recipe),
        "--target",
        "claude-managed-agents",
        "--edition",
        "developer-edition",
    ])
    output = capsys.readouterr().out

    assert status == 0
    assert "claude-managed-agents/developer-edition/agent.yaml" in output
    assert "claude-managed-agents/enterprise-edition" not in output


def test_claude_code_compiler_removes_legacy_output_dirs(tmp_path):
    recipe = _copy_agent(tmp_path)
    legacy_standard = recipe.parent / "dist" / "claude-code" / "standard"
    legacy_extended = recipe.parent / "dist" / "claude-code" / "extended"
    legacy_standard.mkdir(parents=True)
    legacy_extended.mkdir(parents=True)
    (legacy_standard / "dependency-decision-helper.md").write_text("stale", encoding="utf-8")
    (legacy_extended / "dependency-decision-helper.md").write_text("stale", encoding="utf-8")

    compile_claude_code(recipe)

    assert not legacy_standard.exists()
    assert not legacy_extended.exists()
    assert not (recipe.parent / "dist" / "claude-code" / "developer-edition").exists()
    assert (recipe.parent / "dist" / "claude-code" / "enterprise-edition").is_dir()


def test_claude_code_enterprise_edition_pins_read_only_endorctl_command_shapes(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe, edition="enterprise-edition")

    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-decision-helper.md"
    ).read_text()

    bash_blocks = _fenced_blocks(enterprise, "bash")
    assert bash_blocks == [
        """endorctl api list \\
  --resource PackageVersion \\
  --namespace oss \\
  --filter 'meta.name=="<prefix>://<package_name>@<version>"' \\
  --field-mask "uuid,meta.name"
""",
        """endorctl api list \\
  --resource Metric \\
  --namespace oss \\
  --filter 'meta.name=="package_version_scorecard" and meta.parent_uuid=="<package_version_uuid>"' \\
  --field-mask "spec.metric_values.scorecard.score_card.category_scores"
""",
        """endorctl api list \\
  --resource Metric \\
  --namespace oss \\
  --filter 'meta.name=="pkg_version_info_for_license" and meta.parent_uuid=="<package_version_uuid>"' \\
  --field-mask "spec.metric_values.licenseInfoType.license_info.all_licenses"
""",
        """endorctl api create \\
  --resource QuerySimilarPackages \\
  --namespace oss \\
  --data '{"meta":{"name":"similar-packages-query-<package_name>"},"spec":{"name":"<package_name>","edit_distance":2,"repo":"<ECOSYSTEM_ENUM>","exact_match":false}}'
""",
    ]
    assert "The only allowed `endorctl api create` form" in enterprise
    assert "do not generalize this exception to other resources" in enterprise


def test_raw_compiler_emits_setup_bundle(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_raw(recipe)

    names = {path.name for path in outputs}
    assert names == {
        "system-prompt-enterprise-edition.md",
        "mcp-config.json",
        "endorctl-setup.md",
    }
    assert "endor-cli-tools" in (recipe.parent / "dist" / "raw" / "mcp-config.json").read_text()
    assert "read-only Endor lookups" in (recipe.parent / "dist" / "raw" / "endorctl-setup.md").read_text()


def test_codex_compiler_emits_skill_artifact(tmp_path):
    recipe = _copy_agent(tmp_path)
    data = recipe.read_text(encoding="utf-8")
    data = data.replace("  - claude-managed-agents\n", "  - claude-managed-agents\n  - codex\n")
    recipe.write_text(data, encoding="utf-8")

    outputs = compile_codex(recipe)

    assert [path.name for path in outputs] == ["SKILL.md"]
    skill = (recipe.parent / "dist" / "codex" / "dependency-decision-helper" / "SKILL.md").read_text()
    assert "name: dependency-decision-helper" in skill
    assert "Generated from Endor Agent Kit recipe `dependency-decision-helper`" in skill
    assert "## Codex Host Contract" in skill
    assert "Shell commands, when used, must stay read-only" in skill
    assert "endorctl api list" in skill


def test_gemini_compiler_emits_skill_and_subagent_artifacts(tmp_path):
    recipe = _copy_agent(tmp_path)
    data = recipe.read_text(encoding="utf-8")
    data = data.replace("  - claude-managed-agents\n", "  - claude-managed-agents\n  - gemini\n")
    data = data.replace(
        "  claude-managed-agents:\n    - enterprise-edition\n",
        "  claude-managed-agents:\n    - enterprise-edition\n  gemini:\n    - enterprise-edition\n",
    )
    recipe.write_text(data, encoding="utf-8")

    outputs = compile_gemini(recipe)

    assert [path.name for path in outputs] == ["SKILL.md", "dependency-decision-helper.md"]
    skill = (recipe.parent / "dist" / "gemini" / "dependency-decision-helper" / "SKILL.md").read_text()
    agent = (
        recipe.parent / "dist" / "gemini" / "dependency-decision-helper" / "dependency-decision-helper.md"
    ).read_text()
    agent_frontmatter = yaml.safe_load(agent.split("---", 2)[1])

    assert "name: dependency-decision-helper" in skill
    assert "Generated from Endor Agent Kit recipe `dependency-decision-helper`" in skill
    assert "## Gemini CLI Host Contract" in skill
    assert "Shell commands, when used, must stay read-only" in skill
    assert "endorctl api list" in skill
    assert "data_gaps" in skill
    assert agent_frontmatter["kind"] == "local"
    assert agent_frontmatter["model"] == "inherit"
    assert agent_frontmatter["max_turns"] == 30
    assert "mcpServers" not in agent_frontmatter
    assert "endor_agent_kit_managed=true" in agent
    assert "## Gemini CLI Host Contract" in agent


def test_raw_compiler_removes_legacy_prompt_names(tmp_path):
    recipe = _copy_agent(tmp_path)
    raw_dir = recipe.parent / "dist" / "raw"
    raw_dir.mkdir(parents=True)
    legacy_standard = raw_dir / "system-prompt-standard.md"
    legacy_extended = raw_dir / "system-prompt-extended.md"
    legacy_standard.write_text("stale", encoding="utf-8")
    legacy_extended.write_text("stale", encoding="utf-8")

    compile_raw(recipe)

    assert not legacy_standard.exists()
    assert not legacy_extended.exists()
    assert not (raw_dir / "system-prompt-developer-edition.md").exists()
    assert (raw_dir / "system-prompt-enterprise-edition.md").is_file()


def test_claude_code_compiler_golden_hashes(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)
    enterprise = recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-decision-helper.md"

    assert _sha256(enterprise) == ENTERPRISE_EDITION_SHA256


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fenced_blocks(text: str, language: str) -> list[str]:
    blocks: list[str] = []
    marker = f"```{language}\n"
    for after_marker in text.split(marker)[1:]:
        blocks.append(after_marker.split("```", 1)[0])
    return blocks

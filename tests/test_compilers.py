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
from endor_agent_kit.publisher import publish_recipes
from endor_agent_kit.compilers.claude_code import _disallowed_tools
from endor_agent_kit.recipe import HostCapabilities, EndorAgentRecipe

from conftest import repo_root


ENTERPRISE_EDITION_SHA256 = "fcb5a7940ac72184b7865c0fa0bbf81fba5190487fb544ebfd6d497b16a7fec8"


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "dependency-reviewer"
    dst = tmp_path / "dependency-reviewer"
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
        name
        for _edition in ("developer-edition", "enterprise-edition")
        for name in (
            "dependency-reviewer.md",
            "dependency-reviewer-package-decision.md",
            "dependency-reviewer-package-risk.md",
            "dependency-reviewer-repository-review.md",
        )
    ]
    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-reviewer.md"
    ).read_text()

    enterprise_header = enterprise.split("---", 2)[1]
    assert "\ntools:" not in enterprise_header
    assert (recipe.parent / "dist" / "claude-code" / "developer-edition").is_dir()
    assert "mcpServers:" in enterprise_header
    assert "endor-cli-tools:" in enterprise_header
    assert "alwaysLoad: true" in enterprise_header
    assert "disallowedTools: Bash" not in enterprise_header
    assert "model: sonnet" in enterprise_header
    assert "endorctl agent api --agent-id dependency-reviewer list" in enterprise
    assert "data_gaps" in enterprise
    assert "## Endor Knowledge Pack" in enterprise
    assert "## Structured Output Contract" in enterprise
    assert "Context first" in enterprise


def test_claude_code_compiler_emits_named_profile_variants_in_same_edition_bundle(tmp_path):
    source = repo_root() / "source" / "agents" / "sca-remediation"
    target = tmp_path / "sca-remediation"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("dist"))

    outputs = compile_claude_code(target / "recipe.yaml", edition="enterprise-edition")

    assert [path.name for path in outputs] == [
        "sca-remediation.md",
        "sca-remediation-resolve-scope.md",
        "sca-remediation-evidence-check.md",
        "sca-remediation-selection-plan.md",
    ]
    scoped = (target / "dist" / "claude-code" / "enterprise-edition" / "sca-remediation-evidence-check.md").read_text()
    base = (target / "dist" / "claude-code" / "enterprise-edition" / "sca-remediation.md").read_text()
    assert "name: sca-remediation-evidence-check" in scoped
    assert "Profiles: `evidence-check`" in scoped
    assert "`selection-plan` - Selection Plan" not in scoped
    assert len(scoped) < len(base) * 0.7
    assert "Never edit files" in scoped
    assert "Do not fabricate findings" in scoped
    assert "## PR/MR Body And Comment Requirements" not in scoped


def test_ai_sast_profile_variant_reduces_input_without_losing_safety_invariants(tmp_path):
    source = repo_root() / "source" / "agents" / "ai-sast-remediation"
    target = tmp_path / "ai-sast-remediation"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("dist"))

    compile_claude_code(target / "recipe.yaml", edition="enterprise-edition")

    out_dir = target / "dist" / "claude-code" / "enterprise-edition"
    base = (out_dir / "ai-sast-remediation.md").read_text()
    scoped = (out_dir / "ai-sast-remediation-evidence-check.md").read_text()
    assert len(scoped) < len(base) * 0.7
    assert "Do not execute exploit steps against live systems" in scoped
    assert "Never let the developer requesting an exception self-approve it" in scoped
    assert "Create the Endor exception policy only after verified AppSec approval" not in scoped


def test_plugin_package_prompts_stay_within_compact_budgets(tmp_path):
    recipes = sorted((repo_root() / "source" / "agents").glob("*/recipe.yaml"))
    dest = tmp_path / "catalog"

    publish_recipes(recipes, dest, prune=True, include_plugins=True)

    errors: list[str] = []
    for path in _plugin_prompt_files(dest):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(dest).as_posix()
        budget = _prompt_budget(relative)
        if len(text) > budget:
            errors.append(f"{relative}: {len(text)} > {budget}")
        if "endor-agent-kit-setup" not in relative:
            for required in (
                "Evidence Gate Contract",
                "Never use memory",
                "Never dump or `cat` Endor config files",
                "Structured Output Contract",
                "Return exactly one parseable JSON object",
            ):
                if required not in text:
                    errors.append(f"{relative}: missing {required!r}")
    assert errors == []


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

    assert len(outputs) == 4
    assert {output.parent.name for output in outputs} == {"developer-edition"}
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
    assert "endorctl agent api --agent-id dependency-reviewer list" in enterprise["system"]
    assert enterprise_environment["name"] == "endor-dependency-reviewer"
    assert enterprise_environment["config"]["packages"] == {"npm": ["endorctl"]}


def test_claude_code_compiler_accepts_legacy_variant_aliases(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_claude_code(recipe, variant="standard")

    assert len(outputs) == 4
    assert {output.parent.name for output in outputs} == {"developer-edition"}
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
    assert "developer-edition/dependency-reviewer.md" in developer_output
    assert "enterprise-edition/dependency-reviewer.md" in enterprise_output


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
    (legacy_standard / "dependency-reviewer.md").write_text("stale", encoding="utf-8")
    (legacy_extended / "dependency-reviewer.md").write_text("stale", encoding="utf-8")

    compile_claude_code(recipe)

    assert not legacy_standard.exists()
    assert not legacy_extended.exists()
    assert (recipe.parent / "dist" / "claude-code" / "developer-edition").is_dir()
    assert (recipe.parent / "dist" / "claude-code" / "enterprise-edition").is_dir()


def test_claude_code_enterprise_edition_pins_read_only_endorctl_command_shapes(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe, edition="enterprise-edition")

    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-reviewer.md"
    ).read_text()

    assert _fenced_blocks(enterprise, "bash") == []
    assert "endorctl agent api --agent-id dependency-reviewer list -r PackageVersion" in enterprise
    assert "--field-mask \"uuid,meta.name,spec.ecosystem,spec.package_name,spec.release_timestamp\"" in enterprise
    assert "Shell execution is limited to the documented read-only" in enterprise
    assert "QuerySimilarPackages" not in enterprise


def test_raw_compiler_emits_setup_bundle(tmp_path):
    recipe = _copy_agent(tmp_path)

    outputs = compile_raw(recipe)

    names = {path.name for path in outputs}
    assert names == {
        "system-prompt-developer-edition.md",
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
    skill = (recipe.parent / "dist" / "codex" / "dependency-reviewer" / "SKILL.md").read_text()
    assert "name: dependency-reviewer" in skill
    assert "Generated from Endor Agent Kit recipe `dependency-reviewer`" in skill
    assert "## Codex Host Contract" in skill
    assert "Shell commands, when used, must stay read-only" in skill
    assert "## Structured Output Contract" in skill
    assert "endorctl agent api --agent-id dependency-reviewer list" in skill


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

    assert [path.name for path in outputs] == ["SKILL.md", "dependency-reviewer.md"]
    skill = (recipe.parent / "dist" / "gemini" / "dependency-reviewer" / "SKILL.md").read_text()
    agent = (
        recipe.parent / "dist" / "gemini" / "dependency-reviewer" / "dependency-reviewer.md"
    ).read_text()
    agent_frontmatter = yaml.safe_load(agent.split("---", 2)[1])

    assert "name: dependency-reviewer" in skill
    assert "Generated from Endor Agent Kit recipe `dependency-reviewer`" in skill
    assert "## Gemini CLI Host Contract" in skill
    assert "Shell commands, when used, must stay read-only" in skill
    assert "## Structured Output Contract" in skill
    assert "endorctl agent api --agent-id dependency-reviewer list" in skill
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
    assert (raw_dir / "system-prompt-developer-edition.md").is_file()
    assert (raw_dir / "system-prompt-enterprise-edition.md").is_file()


def test_claude_code_compiler_golden_hashes(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)
    enterprise = recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-reviewer.md"

    assert _sha256(enterprise) == ENTERPRISE_EDITION_SHA256


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fenced_blocks(text: str, language: str) -> list[str]:
    blocks: list[str] = []
    marker = f"```{language}\n"
    for after_marker in text.split(marker)[1:]:
        blocks.append(after_marker.split("```", 1)[0])
    return blocks


def _plugin_prompt_files(root: Path) -> list[Path]:
    patterns = (
        "plugins/claude/endor-labs-agent-kit/agents/*.md",
        "plugins/claude/ai-plugins/agents/*.md",
        "plugins/codex/endor-labs-agent-kit/skills/*/SKILL.md",
        "plugins/codex/endor-labs-agent-kit/agents/*.toml",
        "plugins/gemini/endor-labs-agent-kit/skills/*/SKILL.md",
        "plugins/gemini/endor-labs-agent-kit/agents/*.md",
        "plugins/antigravity/endor-labs-agent-kit/skills/*/SKILL.md",
        "plugins/antigravity/endor-labs-agent-kit/agents/*.md",
        "agents/*.md",
        "skills/*/SKILL.md",
        "cursor-sdk/agents/*.md",
    )
    paths: set[Path] = set()
    for pattern in patterns:
        paths.update(root.glob(pattern))
    return sorted(paths)


def _prompt_budget(relative_path: str) -> int:
    agent_id = _agent_id_from_prompt_path(relative_path)
    if agent_id == "endor-agent-kit-setup":
        return 11_000
    if agent_id == "dependency-reviewer":
        return 18_000
    if agent_id == "oss-upgrade-investigator":
        return 15_000
    if agent_id in {"cicd-posture", "troubleshooting", "configuration-automation"}:
        return 26_000
    if agent_id == "sca-remediation":
        # Full fallback carries resume, duplicate-PR, and worktree-isolation safety contracts.
        # Scoped read profiles remain subject to the same canonical-agent budget here and
        # have separate <70% size assertions above.
        return 38_000
    if agent_id == "ai-sast-remediation":
        return 36_000
    return 13_000


def _agent_id_from_prompt_path(relative_path: str) -> str:
    path = Path(relative_path)
    if path.name == "SKILL.md":
        return path.parent.name
    stem = path.stem
    if stem in {"endor-agent-kit-setup-agent", "endor-agent-kit-setup"}:
        return "endor-agent-kit-setup"
    if stem in {"troubleshooting-agent", "troubleshooting"}:
        return "troubleshooting"
    if stem.startswith("endor-"):
        stem = stem[len("endor-"):]
    if stem.endswith("-agent"):
        stem = stem[: -len("-agent")]
    known_agent_ids = {
        "ai-sast-remediation",
        "cicd-posture",
        "dependency-reviewer",
        "endor-agent-kit-setup",
        "troubleshooting",
        "findings-browser",
        "malware-responder",
        "dependency-reviewer",
        "configuration-automation",
        "remediation-planning",
        "dependency-reviewer",
        "sca-remediation",
        "oss-upgrade-investigator",
        "vulnerability-explainer",
    }
    for agent_id in sorted(known_agent_ids, key=len, reverse=True):
        if stem == agent_id or stem.startswith(f"{agent_id}-"):
            return agent_id
    return stem

from __future__ import annotations

import shutil

import yaml

from conftest import repo_root
from endor_agent_kit.compilers import compile_claude_code
from endor_agent_kit.publisher import publish_recipe
from endor_agent_kit.source_authoring import check_source_recipe_authoring
from endor_agent_kit.validator import validate_recipe_file
from host_artifact_bundle_contract import (
    assert_codex_skill_bundle,
    assert_host_bundle_files,
    assert_mcp_free_generated_artifact,
    assert_no_nested_edition_dirs,
    compiled_evidence_artifact_paths,
)


def _copy_agent(tmp_path):
    src = repo_root() / "source" / "agents" / "findings-browser"
    dst = tmp_path / "source" / "agents" / "findings-browser"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_findings_browser_recipe_is_read_only_mcp_free_and_new_agent_ready(tmp_path):
    recipe = _copy_agent(tmp_path)
    data = yaml.safe_load(recipe.read_text(encoding="utf-8"))
    report = check_source_recipe_authoring(recipe, new_agent=True)

    assert validate_recipe_file(recipe) == []
    assert report.ok
    assert data["id"] == "findings-browser"
    assert data["safety_class"] == "read_only"
    assert data["supported_transports"] == ["endorctl_agent_api"]
    assert data["required_endor_mcp_tools"] == []
    assert data["requires_endor_mcp"] == ""
    assert data["mutations"] == []
    assert data["compatible_hosts"] == ["claude-code", "claude-managed-agents", "codex", "gemini", "portable"]
    assert data["host_editions"] == {
        "claude-code": ["enterprise-edition"],
        "claude-managed-agents": ["enterprise-edition"],
        "gemini": ["enterprise-edition"],
    }
    output_names = {item["name"] for item in data["outputs"]}
    assert output_names == {
        "findings_verdict",
        "summary",
        "applied_filters",
        "severity_summary",
        "finding_results",
        "pagination",
        "recommended_next_steps",
        "evidence_queries",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    }


def test_findings_browser_compiled_artifact_carries_browse_contract(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_code(recipe)

    artifact = (
        recipe.parent
        / "dist"
        / "claude-code"
        / "enterprise-edition"
        / "findings-browser.md"
    ).read_text(encoding="utf-8")
    header = artifact.split("---", 2)[1]

    assert "Findings Browser" in artifact
    assert "Use this agent proactively when the user wants to browse" in artifact
    assert "## Endor Knowledge Pack" in artifact
    assert "Findings Browser Evidence Contract" in artifact
    assert "finding-browser-filtered" in artifact
    assert "findings_verdict" in artifact
    assert "applied_filters" in artifact
    assert "finding_results" in artifact
    assert "pagination" in artifact
    assert "Do not use broad unfiltered `Finding --list-all` queries" in artifact
    assert "does not require, configure, or start an Endor MCP server" in artifact
    assert "Endor MCP server" in artifact
    assert "Never run `endorctl scan`" in artifact
    assert "`--traverse` before reporting the" in artifact
    assert "Invoke the installed `endorctl` binary directly" in artifact
    assert "Never use `npx`, `npm exec`, `pnpm dlx`, or `yarn dlx`" in artifact
    assert "hook" not in header
    assert "disallowedTools: Bash" not in header
    assert_mcp_free_generated_artifact(artifact)


def test_findings_browser_publish_writes_all_host_surfaces(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert written_paths == {
        "claude-code/findings-browser/findings-browser.md",
        "claude-code/findings-browser/README.md",
        "claude-code/findings-browser/architecture.svg",
        "claude-code/findings-browser/endorctl-setup.md",
        "claude-managed-agents/findings-browser/agent.yaml",
        "claude-managed-agents/findings-browser/environment.yaml",
        "claude-managed-agents/findings-browser/session-template.yaml",
        "claude-managed-agents/findings-browser/README.md",
        "claude-managed-agents/findings-browser/architecture.svg",
        "claude-managed-agents/findings-browser/endorctl-setup.md",
        "codex/findings-browser/SKILL.md",
        "codex/findings-browser/README.md",
        "codex/findings-browser/architecture.svg",
        "codex/findings-browser/endorctl-setup.md",
        "gemini/findings-browser/SKILL.md",
        "gemini/findings-browser/findings-browser.md",
        "gemini/findings-browser/README.md",
        "gemini/findings-browser/architecture.svg",
        "gemini/findings-browser/endorctl-setup.md",
        "portable/findings-browser/README.md",
        "portable/findings-browser/agent.md",
        "portable/findings-browser/agent.manifest.json",
        "portable/findings-browser/output-contract.md",
        "portable/findings-browser/architecture.svg",
        "portable/findings-browser/endorctl-setup.md",
        "manifest.json",
        "README.md",
        "catalog.json",
    } | compiled_evidence_artifact_paths(
        "findings-browser",
        evidence_plan_ids=("browse",),
        profile_contract_ids=("resolve-scope", "browse", "exact-finding"),
    )

    claude_dir = dest / "claude-code" / "findings-browser"
    managed_dir = dest / "claude-managed-agents" / "findings-browser"
    codex_dir = dest / "codex" / "findings-browser"
    gemini_dir = dest / "gemini" / "findings-browser"
    portable_dir = dest / "portable" / "findings-browser"

    assert_host_bundle_files(claude_dir, {"findings-browser.md", "README.md", "architecture.svg", "endorctl-setup.md"})
    assert_host_bundle_files(managed_dir, {"agent.yaml", "environment.yaml", "session-template.yaml", "README.md", "architecture.svg", "endorctl-setup.md"})
    assert_codex_skill_bundle(
        codex_dir,
        expected_files={"SKILL.md", "README.md", "architecture.svg", "endorctl-setup.md"},
        skill_markers=(
            "Keep the workflow read-only",
            "findings_verdict",
            "Never run `endorctl scan`",
            "Evidence Query Recipes",
        ),
    )
    assert_host_bundle_files(gemini_dir, {"SKILL.md", "findings-browser.md", "README.md", "architecture.svg", "endorctl-setup.md"})
    assert_host_bundle_files(portable_dir, {"README.md", "agent.md", "agent.manifest.json", "output-contract.md", "architecture.svg", "endorctl-setup.md"})
    assert_no_nested_edition_dirs(claude_dir)
    assert_no_nested_edition_dirs(managed_dir)
    assert_no_nested_edition_dirs(gemini_dir)

    root_readme = (dest / "README.md").read_text(encoding="utf-8")
    assert "Findings Browser" in root_readme
    assert "codex/findings-browser/" in root_readme
    assert "Use the findings-browser skill" in root_readme
    assert_mcp_free_generated_artifact((claude_dir / "findings-browser.md").read_text(encoding="utf-8"))
    assert_mcp_free_generated_artifact((codex_dir / "SKILL.md").read_text(encoding="utf-8"))


def test_findings_browser_eval_cases_cover_browse_outcomes():
    evals = yaml.safe_load(
        (repo_root() / "source" / "agents" / "findings-browser" / "evals" / "cases.yaml").read_text()
    )

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "critical-reachable-project-findings",
        "exact-finding-uuid-lookup",
        "exploited-finding-prioritization",
        "filtered-no-results",
        "namespace-wide-truncated-cicd-findings",
        "missing-namespace-insufficient-data",
        "adversarial-finding-description-injection",
    }
    verdicts = {case["expected"]["findings_verdict"] for case in evals["cases"]}
    assert verdicts == {
        "ACTIVE_FINDINGS_FOUND",
        "EXACT_FINDING_FOUND",
        "NO_MATCHING_FINDINGS",
        "PARTIAL_RESULTS",
        "INSUFFICIENT_DATA",
    }
    for case in evals["cases"]:
        assert case["expected"]["required_evidence"]
        assert isinstance(case["expected"]["data_gaps_allowed"], bool)

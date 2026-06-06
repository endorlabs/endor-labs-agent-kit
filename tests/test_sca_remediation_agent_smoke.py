from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.publisher import publish_recipe
from endor_agent_kit.validator import validate_recipe_file

from conftest import repo_root
from host_artifact_bundle_contract import (
    assert_codex_skill_bundle,
    assert_host_bundle_files,
    assert_mcp_free_generated_artifact,
    assert_no_nested_edition_dirs,
)


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "sca-remediation"
    dst = tmp_path / "sca-remediation"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_sca_remediation_agent_is_mcp_free_and_action_contract_backed(tmp_path):
    recipe = _copy_agent(tmp_path)
    data = yaml.safe_load(recipe.read_text(encoding="utf-8"))

    assert validate_recipe_file(recipe) == []
    assert data["recipe_schema_version"] == 2
    assert data["safety_class"] == "mutating"
    assert data["supported_transports"] == ["endorctl_api"]
    assert data["required_endor_mcp_tools"] == []
    assert data["requires_endor_mcp"] == ""
    assert data["action_contracts_path"] == "actions.yaml"
    assert data["host_capabilities_required"] == {
        "run_commands": True,
        "read_files": True,
        "write_files": True,
        "open_pr": True,
    }

    actions = yaml.safe_load((recipe.parent / "actions.yaml").read_text(encoding="utf-8"))["actions"]
    action_ids = {action["id"] for action in actions}
    assert action_ids == {
        "resolve-endor-project",
        "query-sca-findings",
        "query-uia-evidence",
        "list-low-risk-uia-prs",
        "read-local-manifests",
        "resolve-upgrade-risk",
        "prepare-remediation-diff",
        "open-change-request",
        "post-remediation-comment",
        "create-remediation-ticket",
    }
    for action in actions:
        if action["safety_class"] == "mutating":
            assert action["confirmation_required"] is True


def test_sca_remediation_agent_generated_catalog_surface(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    root_readme = (dest / "README.md").read_text(encoding="utf-8")
    agent_dir = dest / "claude-code" / "sca-remediation"
    codex_dir = dest / "codex" / "sca-remediation"
    agent_readme = (agent_dir / "README.md").read_text(encoding="utf-8")
    prompt = (agent_dir / "sca-remediation.md").read_text(encoding="utf-8")

    assert "@agent-sca-remediation check this repository for P0 SCA findings" in root_readme
    assert "codex/sca-remediation" in root_readme
    assert "Use the sca-remediation skill to check this repository for P0 SCA findings" in root_readme
    assert "MCP-free Claude Code artifact" in prompt
    assert "Do not require the user to know an Endor project UUID" in prompt
    assert "Natural-Language Intake" in prompt
    assert "## Endor Knowledge Pack" in prompt
    assert "SCA Remediation Evidence Contract" in prompt
    assert "Preferred evidence resources: `Project`, `Finding`, `VersionUpgrade`" in prompt
    assert "Query `Finding` with `context.type==CONTEXT_TYPE_MAIN`" in prompt
    assert "Record missing credentials, namespace conflicts, project lookup failures" in prompt
    assert "Project scoping is mandatory" in prompt
    assert "Default Endor Context Scope" in prompt
    assert "Default to `context.type==CONTEXT_TYPE_MAIN` for Endor Findings" in prompt
    assert "PR/CI-run findings" in prompt
    assert "main-branch remediation counts" in prompt
    assert "Namespace Provenance" in prompt
    assert "Do not invent or reuse a namespace from unrelated examples" in prompt
    assert "Before running an Endor query with `-n <namespace>`" in prompt
    assert "retry that same candidate with `--traverse`" in prompt
    assert "Traverse fallback when the first project lookup has no match" in prompt
    assert "Do not print or dump an entire Endor config file" in prompt
    assert "extract only the namespace key" in prompt
    assert "namespace_provenance" in prompt
    assert "Every output gate must include `project_resolution.status`, `project_resolution.project_uuid`" in prompt
    assert 'Use `project_resolution.status: "resolved"` only after current Endor project evidence proves the project and namespace' in prompt
    assert "project_resolution" in prompt
    assert "package-level remediation" in prompt
    assert "VersionUpgrade/UIA evidence before calling" in prompt
    assert "A high finding count alone is not enough" in prompt
    assert "Do not require, configure, or start an Endor MCP server" in prompt
    assert "endorctl api list -r Finding" in prompt
    assert 'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="<PROJECT_UUID>" and spec.finding_categories contains FINDING_CATEGORY_VULNERABILITY' in prompt
    assert "uuid,context,meta.name,meta.description,meta.parent_uuid" in prompt
    assert "spec.source_code_version" in prompt
    assert "spec.target_uuid" in prompt
    assert "spec.dependency_file_paths" in prompt
    assert "endorctl api list -r VersionUpgrade" in prompt
    assert "Do not make current upstream/latest-version claims unless you verified them during the current run" in prompt
    assert "prepare-remediation-diff" in prompt
    assert "post-remediation-comment" in prompt
    assert "Query only main-context repository-scoped SCA vulnerability findings by default" in prompt
    assert "Use PR/CI-run or all-context findings only when the user explicitly asks" in prompt
    assert "resolve-upgrade-risk" in prompt
    assert "Risky / Indeterminate Upgrade Solver" in prompt
    assert "Other Non-Breaking / Low-Risk UIA-Backed PR Lane" in prompt
    assert "separate from both the strict P0/exploited queue and the Risky / Indeterminate Upgrade Solver" in prompt
    assert "low_risk_recommendations" in prompt
    assert "candidate_prs" in prompt
    assert "ready_to_open" in prompt
    assert "most_findings_in_one_pr" in prompt
    assert "p0_duplicates_hidden" in prompt
    assert "Do not rank a hidden P0/exploited duplicate as `most_findings_in_one_pr`" in prompt
    assert "Hide recommendations from the main low-risk candidate list" in prompt
    assert "Return exactly one `risk_decision.status`" in prompt
    assert "approved_low_risk" in prompt
    assert "approved_with_validation_required" in prompt
    assert "blocked_needs_compatibility_analysis" in prompt
    assert "Do not say \"not expected to break\"" in prompt
    assert "Selection / Plan gate is not complete until `risk_decision.status` is present" in prompt
    assert "Those are inputs to `risk_decision`, not the decision itself" in prompt
    assert "Validation Command Selection" in prompt
    assert "Do not assume a Java/Maven repository" in prompt
    assert "package manager, and manifest or lockfile" in prompt
    assert "package.json" in prompt
    assert "requirements.txt" in prompt
    assert "go.mod" in prompt
    assert ".csproj" in prompt
    assert "Cargo.toml" in prompt
    assert "use `-pl` only after confirming a root aggregator POM exists" in prompt
    assert "project-specific layout" not in prompt
    assert "services/api-gateway/pom.xml dependency:resolve" not in prompt
    assert "remediation/sca/<normalized-package-name>-<target-version>" in prompt
    assert "Do not use unrelated branch families such as `endor/fix/...`" in prompt
    assert "complete AURI-style PR/MR body draft" in prompt
    assert "Do not stop at a PR title or patch plan only" in prompt
    assert "Do not return an empty `change_requests` array when a PR/MR is part of the requested plan" in prompt
    assert "The PR/MR body draft must be lint-clean in the response itself" in prompt
    assert "close any ```diff fenced block immediately after the file-change lines" in prompt
    assert "render `### 🔎 Advisories This Upgrade Fixes` as an actual heading" in prompt
    assert "markdown link syntax" in prompt
    assert "The JSON object must be syntactically valid" in prompt
    assert "Security Remediation: <N> Endor finding instances fixed by dependency upgrade" in prompt
    assert "### At a Glance" in prompt
    assert "### 🔎 Advisories This Upgrade Fixes" in prompt
    assert "<details><summary>Advisories This Upgrade Fixes (<count>)</summary>" in prompt
    assert "<details open>" not in prompt
    assert "### Validation Plan" in prompt
    assert "### 🧪 Developer Validation" not in prompt
    assert "Advisory Provenance" in prompt
    assert "endor-agent-kit lint-sca-pr-body" in prompt
    assert "Do not omit this section" in prompt
    assert "Use the CVE as the visible link text while linking to the GitHub Advisory page" in prompt
    assert "(C) 🔴" in prompt
    assert "(H) 🟠" in prompt
    assert "(M) 🟡" in prompt
    assert "(L) 🟢" in prompt
    assert "Do not use bold severity words in the advisory list" in prompt
    assert "Do not claim companion artifacts" in prompt
    assert "Scope compatibility claims to Endor UIA/CIA evidence" in prompt
    assert_mcp_free_generated_artifact(prompt)
    assert_host_bundle_files(
        agent_dir,
        {"sca-remediation.md", "README.md", "actions.yaml", "architecture.svg", "endorctl-setup.md"},
    )
    assert_codex_skill_bundle(
        codex_dir,
        expected_files={"SKILL.md", "README.md", "actions.yaml", "architecture.svg", "endorctl-setup.md"},
        skill_markers=(
            "Treat file edits, branch pushes, PR/MR creation",
            "VersionUpgrade/UIA evidence",
        ),
    )
    assert_no_nested_edition_dirs(agent_dir)
    assert "![SCA Remediation architecture](architecture.svg)" in agent_readme
    assert "Claude Code does not need an Endor MCP server for this agent" in agent_readme
    assert "Rank Without Mutating" in agent_readme
    assert "VersionUpgrade/UIA evidence" in agent_readme
    assert "folded advisory/finding list" in agent_readme
    assert "Advisories This Upgrade Fixes" in agent_readme
    assert "deterministic `risk_decision`" in agent_readme
    assert "selection/plan gate is not complete" in agent_readme
    assert "remediation/sca/<package>-<target-version>" in agent_readme
    assert "UIA evidence, risk_decision, target files" in agent_readme
    assert "resolves risky or CIA-indeterminate upgrades" in agent_readme
    assert "CLAUDE_CONFIG_DIR" in agent_readme
    assert "endor-cli-tools" not in agent_readme
    assert "The run log should not reference user-level skills or Endor MCP tooling" in agent_readme

    architecture = (agent_dir / "architecture.svg").read_text(encoding="utf-8")
    assert "deterministic risk decisions" in architecture
    assert "RISK SOLVER" in architecture
    assert "Deterministic Verdict" in architecture
    assert "risk_decision" in architecture


def test_sca_remediation_agent_eval_cases_cover_v1_risks(tmp_path):
    recipe = _copy_agent(tmp_path)
    cases = yaml.safe_load((recipe.parent / "evals" / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    ids = {case["id"] for case in cases}

    assert {
        "natural-language-p0-intake",
        "uia-required-before-best-first-fix",
        "risky-upgrade-validation-gate",
        "low-risk-uia-backed-pr-lane",
        "cia-indeterminate-selection-gate",
        "namespace-provenance-before-query",
        "namespace-provenance-without-config-dump",
        "missing-project-or-auth",
        "approved-pr-with-comment",
        "pr-plan-includes-full-body",
    }.issubset(ids)

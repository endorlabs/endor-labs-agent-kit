from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code, compile_claude_managed_agents
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
    src = repo_root() / "source" / "agents" / "endor-troubleshooter"
    dst = tmp_path / "endor-troubleshooter"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def _assert_no_private_source_references(text: str) -> None:
    forbidden_patterns = {
        "absolute local home path": r"(?<![\w/-])/(?:Users|home)/[\w.-]+(?:/|$)",
        "repository monorepo slug": r"(?i)\b[\w.-]+/[\w.-]*monorepo[\w.-]*\b",
        "repo-internal source path": r"(?<![\w/-])(?:spec/internal|src/internal|src/hugo)(?![\w/-])",
        "Slack archive URL": r"https?://[\w.-]*slack\.com/archives/",
        "internal feature flag": r"\bENDOR_(?:SCAN|AISAST)_[A-Z0-9_]+\b",
    }
    for label, pattern in forbidden_patterns.items():
        assert not re.search(pattern, text), label


def test_endor_troubleshooter_recipe_is_read_only_and_mcp_free(tmp_path):
    recipe = _copy_agent(tmp_path)
    data = yaml.safe_load(recipe.read_text(encoding="utf-8"))

    assert validate_recipe_file(recipe) == []
    assert data["id"] == "endor-troubleshooter"
    assert data["safety_class"] == "read_only"
    assert data["supported_transports"] == ["endorctl_api"]
    assert data["required_endor_mcp_tools"] == []
    assert data["requires_endor_mcp"] == ""
    assert data["mutations"] == []
    assert data["compatible_hosts"] == ["claude-code", "claude-managed-agents", "codex", "gemini", "portable"]
    assert data["host_editions"] == {
        "claude-code": ["enterprise-edition"],
        "claude-managed-agents": ["enterprise-edition"],
        "gemini": ["enterprise-edition"],
    }
    assert data["host_capabilities_required"] == {
        "run_commands": True,
        "read_files": False,
        "write_files": False,
        "open_pr": False,
    }
    input_names = {item["name"] for item in data["inputs"]}
    assert {
        "issue_summary",
        "error_text",
        "endor_project_selector",
        "scan_result_uuid",
        "scan_workflow_result_uuid",
        "integration_selector",
        "issue_area_hint",
    }.issubset(input_names)
    output_names = {item["name"] for item in data["outputs"]}
    assert {
        "troubleshooting_verdict",
        "issue_lanes",
        "evidence_queries",
        "root_cause_hypotheses",
        "recommended_actions",
        "validation_plan",
        "support_escalation_packet",
        "future_action_contracts",
    }.issubset(output_names)


def test_endor_troubleshooter_compiled_artifact_carries_diagnostic_contract(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_code(recipe)

    artifact = (
        recipe.parent
        / "dist"
        / "claude-code"
        / "enterprise-edition"
        / "endor-troubleshooter.md"
    ).read_text(encoding="utf-8")
    header = artifact.split("---", 2)[1]

    assert "Endor Troubleshooter" in artifact
    assert "## Endor Knowledge Pack" in artifact
    assert "Endor Troubleshooter Evidence Contract" in artifact
    assert "Preferred evidence resources: `Project`, `ScanResult`, `ScanWorkflowResult`, `Integration`" in artifact
    assert "prepare a support packet with precise missing evidence" in artifact
    assert "troubleshooting_verdict" in artifact
    assert "ACTIONABLE_FIX_IDENTIFIED" in artifact
    assert "SUPPORT_ESCALATION_RECOMMENDED" in artifact
    assert "future_action_contracts" in artifact
    assert "SCAN_EXECUTION_FAILURE" in artifact
    assert "PR_SCAN_AND_BASELINE" in artifact
    assert "IDENTITY_PROVIDER_AND_SSO" in artifact
    assert "CONTAINER_IMAGE_AND_REGISTRY_SCANNING" in artifact
    assert "EXPORTERS_NOTIFICATIONS_AND_EXTERNAL_SYSTEMS" in artifact
    assert "HOST_CHECK_SANDBOX_AND_RUNTIME" in artifact
    assert "This agent is read-only and prescriptive" in artifact
    assert "run `endorctl scan`" in artifact
    assert "create scan log requests" in artifact
    assert "`ScanLogRequest` is a create-style API" in artifact
    assert "Use `endorctl --version`" in artifact
    assert "Do not use\n`endorctl version`" in artifact
    assert "Default repository-scoped Endor evidence to `context.type==CONTEXT_TYPE_MAIN`" in artifact
    assert "retry the same read-only query with `--traverse`" in artifact
    assert "PROJECT_NOT_FOUND" in artifact
    assert "Record both the original and\ntraverse query attempts" in artifact
    assert "Never merge PR/CI-run finding counts into main-context finding counts" in artifact
    assert "resolved_dependency_count" in artifact
    assert "Do not `get` `CallGraphData`" in artifact
    assert "endorctl scan --pr --pr-baseline=<baseline_branch> --pr-incremental" in artifact
    assert "https://docs.endorlabs.com/scan/pr-scans/" in artifact
    assert "--resource ScanResult" in artifact
    assert "--resource ScanWorkflowResult" in artifact
    assert "--resource PackageManager" in artifact
    assert "--resource SCMCredential" in artifact
    assert "--resource IdentityProvider" in artifact
    assert "--resource PRCommentConfig" in artifact
    assert "--resource NotificationTarget" in artifact
    assert "--resource Exporter" in artifact
    assert "Do not generalize them into create, update, delete, scan" in artifact
    assert '--filter \'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="<project_uuid>"\'' in artifact
    assert "does not require, configure, or start an Endor MCP server" in artifact
    assert "Scan Lifecycle And Stuck States" in artifact
    assert "Stuck `STATUS_RUNNING`" in artifact
    assert "merge-base" in artifact
    assert "Approximate Scans And Reachability Modes" in artifact
    assert "Toolchain And Host-Check" in artifact
    assert "Endorctl Version Hygiene" in artifact
    assert "SCM Installation Drift And Sync Logs" in artifact
    assert "Notifications And Exporters" in artifact
    assert "SBOM Import And Format Support" in artifact
    assert "authentication (the SSO handshake itself) from authorization" in artifact
    assert "ENDORCTL_RC_INTERNAL_ERROR" in artifact
    assert "ENDORCTL_RC_DEADLINE_EXCEEDED" in artifact
    assert "ENDORCTL_RC_HOST_CHECK_FAILURE" in artifact
    assert "ENDORCTL_RC_LICENSE_ERROR" in artifact
    assert "ENDORCTL_RC_POLICY_VIOLATION" in artifact
    assert "ENDORCTL_RC_GH_ACTION_WORKFLOW_SCAN_FAILURE" in artifact
    assert "ENDORCTL_RC_DEPENDENCY_SETUP_WARNING" in artifact
    assert "ScanResult.spec.exit_code" in artifact
    assert "Endor product license entitlement" in artifact
    assert "Code-specific diagnosis hints" in artifact
    assert "When to recommend support escalation" in artifact
    assert "scanner likely panicked" not in artifact
    assert "Bazel-driven toolchain" not in artifact
    assert "scanner's internal runner generation" not in artifact
    assert "OpenGrep" not in artifact
    assert "opengrep" not in artifact.lower()
    assert "mcpServers" not in artifact
    assert "endorctl ai-tools mcp-server" not in artifact
    assert "disallowedTools: Bash" not in header
    assert_mcp_free_generated_artifact(artifact)
    _assert_no_private_source_references(artifact)


def test_endor_troubleshooter_managed_agents_artifacts_are_read_only(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_managed_agents(recipe)

    out_dir = recipe.parent / "dist" / "claude-managed-agents" / "enterprise-edition"
    assert_host_bundle_files(
        out_dir,
        {"agent.yaml", "environment.yaml", "session-template.yaml"},
    )
    managed = yaml.safe_load((out_dir / "agent.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((out_dir / "environment.yaml").read_text(encoding="utf-8"))
    session = yaml.safe_load((out_dir / "session-template.yaml").read_text(encoding="utf-8"))
    managed_text = (out_dir / "agent.yaml").read_text(encoding="utf-8")

    assert not (recipe.parent / "dist" / "claude-managed-agents" / "developer-edition").exists()
    assert managed["name"] == "Endor Troubleshooter"
    assert managed["model"] == "claude-sonnet-4-6"
    assert managed["metadata"]["endor_agent_kit_recipe_id"] == "endor-troubleshooter"
    assert managed["mcp_servers"] == []
    assert "vault_ids" not in session
    assert environment["name"] == "endor-endor-troubleshooter"
    assert environment["config"]["networking"]["allowed_hosts"] == [
        "https://api.endorlabs.com",
    ]

    tools = {tool["type"]: tool for tool in managed["tools"]}
    assert "mcp_toolset" not in tools
    assert tools["agent_toolset_20260401"]["configs"][0]["name"] == "bash"
    assert "This Managed Agents artifact" in managed["system"]
    assert "read-only `endorctl api` lookups" in managed["system"]
    assert "Do not require Endor MCP" in managed["system"]
    assert "create scan log requests" in managed["system"]
    assert_mcp_free_generated_artifact(managed_text)
    _assert_no_private_source_references(managed_text)


def test_endor_troubleshooter_publish_writes_host_catalog_surfaces(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert written_paths == {
        "claude-code/endor-troubleshooter/endor-troubleshooter.md",
        "claude-code/endor-troubleshooter/README.md",
        "claude-code/endor-troubleshooter/architecture.svg",
        "claude-code/endor-troubleshooter/endorctl-setup.md",
        "claude-managed-agents/endor-troubleshooter/agent.yaml",
        "claude-managed-agents/endor-troubleshooter/environment.yaml",
        "claude-managed-agents/endor-troubleshooter/session-template.yaml",
        "claude-managed-agents/endor-troubleshooter/README.md",
        "claude-managed-agents/endor-troubleshooter/architecture.svg",
        "claude-managed-agents/endor-troubleshooter/endorctl-setup.md",
        "codex/endor-troubleshooter/SKILL.md",
        "codex/endor-troubleshooter/README.md",
        "codex/endor-troubleshooter/architecture.svg",
        "codex/endor-troubleshooter/endorctl-setup.md",
        "gemini/endor-troubleshooter/SKILL.md",
        "gemini/endor-troubleshooter/endor-troubleshooter.md",
        "gemini/endor-troubleshooter/README.md",
        "gemini/endor-troubleshooter/architecture.svg",
        "gemini/endor-troubleshooter/endorctl-setup.md",
        "portable/endor-troubleshooter/README.md",
        "portable/endor-troubleshooter/agent.md",
        "portable/endor-troubleshooter/agent.manifest.json",
        "portable/endor-troubleshooter/output-contract.md",
        "portable/endor-troubleshooter/architecture.svg",
        "portable/endor-troubleshooter/endorctl-setup.md",
        "manifest.json",
        "README.md",
    }
    agent_dir = dest / "claude-code" / "endor-troubleshooter"
    managed_dir = dest / "claude-managed-agents" / "endor-troubleshooter"
    codex_dir = dest / "codex" / "endor-troubleshooter"
    gemini_dir = dest / "gemini" / "endor-troubleshooter"
    portable_dir = dest / "portable" / "endor-troubleshooter"
    assert_host_bundle_files(
        agent_dir,
        {"endor-troubleshooter.md", "README.md", "architecture.svg", "endorctl-setup.md"},
    )
    assert_host_bundle_files(
        managed_dir,
        {"agent.yaml", "environment.yaml", "session-template.yaml", "README.md", "architecture.svg", "endorctl-setup.md"},
    )
    assert_codex_skill_bundle(
        codex_dir,
        expected_files={"SKILL.md", "README.md", "architecture.svg", "endorctl-setup.md"},
        skill_markers=(
            "Keep the workflow read-only",
            "future_action_contracts",
            "PR_SCAN_AND_BASELINE",
            "Do not write source files as part of this agent workflow.",
        ),
    )
    assert_host_bundle_files(
        gemini_dir,
        {"SKILL.md", "endor-troubleshooter.md", "README.md", "architecture.svg", "endorctl-setup.md"},
    )
    assert_host_bundle_files(
        portable_dir,
        {"README.md", "agent.md", "agent.manifest.json", "output-contract.md", "architecture.svg", "endorctl-setup.md"},
    )
    assert_no_nested_edition_dirs(agent_dir)
    assert_no_nested_edition_dirs(managed_dir)
    assert_no_nested_edition_dirs(gemini_dir)

    root_readme = (dest / "README.md").read_text(encoding="utf-8")
    agent_readme = (agent_dir / "README.md").read_text(encoding="utf-8")
    managed_readme = (managed_dir / "README.md").read_text(encoding="utf-8")
    codex_skill = (codex_dir / "SKILL.md").read_text(encoding="utf-8")
    codex_readme = (codex_dir / "README.md").read_text(encoding="utf-8")
    gemini_skill = (gemini_dir / "SKILL.md").read_text(encoding="utf-8")
    gemini_readme = (gemini_dir / "README.md").read_text(encoding="utf-8")
    setup = (agent_dir / "endorctl-setup.md").read_text(encoding="utf-8")
    architecture = (agent_dir / "architecture.svg").read_text(encoding="utf-8")

    assert "Endor Troubleshooter" in root_readme
    assert "Diagnose Endor Labs errors, warnings, scan failures" in root_readme
    assert "claude-code/endor-troubleshooter/" in root_readme
    assert "claude-managed-agents/endor-troubleshooter/" in root_readme
    assert "codex/endor-troubleshooter/" in root_readme
    assert "gemini/endor-troubleshooter/" in root_readme
    assert "portable/endor-troubleshooter/" in root_readme
    assert "@agent-endor-troubleshooter diagnose this Endor scan failure from redacted error text" in root_readme
    assert "@agent-endor-troubleshooter diagnose this Endor scan failure" in agent_readme
    assert "large monorepo" in agent_readme
    assert "Diagnose this Endor scan failure" in managed_readme
    assert "Endor Troubleshooter Codex Skill" in codex_readme
    assert "Use the endor-troubleshooter skill to diagnose this Endor scan failure" in codex_readme
    assert "## Codex Host Contract" in codex_skill
    assert "future_action_contracts" in codex_skill
    assert "Endor Troubleshooter Gemini CLI Bundle" in gemini_readme
    assert "## Gemini CLI Host Contract" in gemini_skill
    assert "future_action_contracts" in gemini_skill
    assert "Endor Troubleshooter uses only read-only Endor lookups" in setup
    assert "PUBLISHED CONTRACT" in architecture

    for text in (root_readme, agent_readme, managed_readme, codex_skill, codex_readme, gemini_skill, gemini_readme, setup, architecture):
        _assert_no_private_source_references(text)
        assert_mcp_free_generated_artifact(text)


def test_endor_troubleshooter_eval_cases_cover_troubleshooting_lanes():
    evals = yaml.safe_load(
        (repo_root() / "source" / "agents" / "endor-troubleshooter" / "evals" / "cases.yaml").read_text()
    )

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "failed-scan-exit-code-dependency-resolution",
        "slow-pr-scan-large-monorepo",
        "sso-login-loop",
        "container-registry-digest-errors",
        "missing-pr-comments-after-app-scan",
        "sparse-warning-insufficient-data",
        "stuck-scan-running-housekeeping-escalation",
        "pr-shallow-clone-diff-failure",
        "notification-delivery-failure-with-target-mismatch",
        "sbom-import-format-mismatch",
        "host-check-missing-toolchain",
        "license-error-product-entitlement-vs-software-license",
        "policy-violation-gha-unpinned-on-unrelated-pr",
        "deadline-exceeded-scheduler-contention",
    }
    verdicts = {case["expected"]["troubleshooting_verdict"] for case in evals["cases"]}
    assert verdicts == {
        "ACTIONABLE_FIX_IDENTIFIED",
        "LIKELY_ROOT_CAUSE_IDENTIFIED",
        "PARTIAL_DIAGNOSIS",
        "INSUFFICIENT_DATA",
        "SUPPORT_ESCALATION_RECOMMENDED",
    }
    for case in evals["cases"]:
        assert case["expected"]["required_evidence"]
        assert isinstance(case["expected"]["data_gaps_allowed"], bool)

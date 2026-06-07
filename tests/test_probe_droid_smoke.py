from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code, compile_claude_managed_agents, compile_raw
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
    src = repo_root() / "source" / "agents" / "probe-droid"
    dst = tmp_path / "probe-droid"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def _fixture() -> dict:
    return yaml.safe_load(
        (
            repo_root()
            / "tests"
            / "fixtures"
            / "probe_droid_selected_repos_regression.yaml"
        ).read_text(encoding="utf-8")
    )


def test_probe_droid_recipe_is_read_only_and_mcp_free(tmp_path):
    recipe = _copy_agent(tmp_path)
    data = yaml.safe_load(recipe.read_text(encoding="utf-8"))

    assert validate_recipe_file(recipe) == []
    assert data["id"] == "probe-droid"
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
        "github_org",
        "repository_urls",
        "github_inventory_json",
        "sampling_mode",
        "report_mode",
    }.issubset(input_names)
    report_mode = next(item for item in data["inputs"] if item["name"] == "report_mode")
    assert "complete drill-down JSON arrays" in report_mode["description"]
    output_names = {item["name"] for item in data["outputs"]}
    assert {
        "executive_report",
        "github_app_coverage",
        "not_onboarded_repositories",
        "onboarded_repositories_with_gaps",
        "confirmed_org_wide_actions",
        "sampled_prescription_hypotheses",
        "requires_full_inventory_validation",
        "evidence_queries",
        "future_scope",
    }.issubset(output_names)


def test_probe_droid_compiled_artifact_carries_onboarding_rules(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_code(recipe)

    artifact = (
        recipe.parent
        / "dist"
        / "claude-code"
        / "enterprise-edition"
        / "probe-droid.md"
    ).read_text(encoding="utf-8")
    header = artifact.split("---", 2)[1]

    assert "Probe Droid" in artifact
    assert "## Endor Knowledge Pack" in artifact
    assert "Probe Droid Evidence Contract" in artifact
    assert "Preferred evidence resources: `Project`, `ScanProfile`, `PackageManager`, `PackageVersion`" in artifact
    assert "Retry Endor project inventory with traversal" in artifact
    assert "GitHub Monitored-Branch Coverage Probe" in artifact
    assert "onboarding_verdict" in artifact
    assert "executive_report" in artifact
    assert "report_mode" in artifact
    assert "report_scope" in artifact
    assert "coverage_summary" in artifact
    assert "github_inventory_summary" in artifact
    assert "github_app_coverage" in artifact
    assert "selected_project_uuids" in artifact
    assert "repositories_not_selected" in artifact
    assert "selection_mapping_gaps" in artifact
    assert "not_onboarded_repositories" in artifact
    assert "onboarded_repositories_with_gaps" in artifact
    assert "If `endor_monitored_branch` is null, `UNKNOWN`, unavailable, unqueryable" in artifact
    assert "classify it under `onboarded_repositories_with_gaps`" in artifact
    assert "confirmed_org_wide_actions" in artifact
    assert "sampled_prescription_hypotheses" in artifact
    assert "requires_full_inventory_validation" in artifact
    assert "evidence_queries" in artifact
    assert "future_scope" in artifact
    assert "DEPENDENCY_RESOLUTION_PRIVATE_REGISTRY" in artifact
    assert "PACKAGE_MANAGER_INTEGRATION_MISSING" in artifact
    assert "REACHABILITY_DEPENDENCY_RESOLUTION_BLOCKED" in artifact
    assert "REPO_NOT_SELECTED_IN_APP" in artifact
    assert "github_app_installations_api_unavailable" in artifact
    assert "dependencies were not downloaded" in artifact
    assert "pg_config executable was not found" in artifact
    assert "PostgreSQL client development prerequisites" in artifact
    assert "psycopg2-binary" in artifact
    assert "top 5 actions" in artifact
    assert "Do not run `endorctl scan`" in artifact
    assert "Do not clone repositories" in artifact
    assert "GitHub.com only" in artifact
    assert "Default Endor Context Scope" in artifact
    assert "Default repository-scoped Endor evidence to `context.type==CONTEXT_TYPE_MAIN`" in artifact
    assert "Keep non-main counts" in artifact
    assert "retry the same read-only Endor inventory lookup with `--traverse`" in artifact
    assert "Traverse fallback when the first project inventory has no strict match" in artifact
    assert "`--traverse` before classifying repositories as not onboarded" in artifact
    assert "gh auth status" in artifact
    assert "gh repo list" in artifact
    assert "gh repo view" in artifact
    assert "https://api.github.com/orgs/<org>/repos" in artifact
    assert "Keep credentials out of logs and final output" in artifact
    assert "isDisabled" not in artifact
    assert "--resource ScanProfile" in artifact
    assert "--resource PackageManager" in artifact
    assert "--resource PackageVersion" in artifact
    assert "--resource Installation" in artifact
    assert "spec.git.ssh_clone_url" not in artifact
    assert "spec.disable_code_snippet_storage" not in artifact
    assert '--field-mask "uuid,meta.name,meta.tags,meta.create_time,meta.update_time,spec"' in artifact
    assert '--field-mask "uuid,meta.name,meta.tags,spec"' in artifact
    assert 'meta.parent_uuid=="<project_uuid>"' in artifact
    assert "call_graph_project_scope_unavailable" in artifact
    assert "Live Command Budget" in artifact
    assert "All live Endor and GitHub commands MUST be projected" in artifact
    assert "set -o pipefail" in artifact
    assert "Never pipe stderr into a JSON projection" in artifact
    assert "Do not use `2>&1 | jq`" in artifact
    assert "Optional evidence queries must fail" in artifact
    assert "they must not cancel package-version" in artifact
    assert "Do not treat temp-file capture" in artifact
    assert "retry at most once" in artifact
    assert "Do not print the full `gh repo list` JSON array" in artifact
    assert "Use root-tree summaries for org-wide first pass" in artifact
    assert "Do not run recursive GitHub tree calls across every repository" in artifact
    assert "do not spend live command budget reading the installed `SKILL.md`" in artifact
    assert "Run at most one all-project `PackageVersion` summary query" in artifact
    assert "Required lane arrays are not example arrays" in artifact
    assert "`not_onboarded_repositories`" in artifact
    assert "In single-repo or subset mode, do not print every Endor project" in artifact
    assert "Never expose complete PackageVersion JSON" in artifact
    assert "Do not expose `Installation.spec.user`" in artifact
    assert "Do not expose package manager credential material" in artifact
    assert "Do not expose full scan profile toolchain URLs" in artifact
    assert "Do not expose complete PackageVersion objects" in artifact
    assert "are not V1 monitored-branch coverage blockers" in artifact
    assert "Do not paste raw multi-megabyte Endor or GitHub JSON" in artifact
    assert 'spec.project_uuid=="<project_uuid>"' in artifact
    assert 'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="<project_uuid>"' in artifact
    assert "spec.resolution_errors" in artifact
    assert "confirmation_required: true" in artifact
    assert "`evidence_queries[]` rows must contain only those fields" in artifact
    assert "Repository lane rows describe current evidence only" in artifact
    assert "Put those proposed actions in `recommended_actions[]` or\n`confirmed_org_wide_actions[]`" in artifact
    assert "does not require, configure, or start an Endor MCP server" in artifact
    assert "documented read-only Endor and GitHub inventory lookups" in artifact
    assert "glab repo list" not in artifact
    assert "az repos list" not in artifact
    assert "Bitbucket repository inventory" not in artifact
    assert "endorctl toolchains detect" not in artifact
    assert "PR_QUICK_SCAN_ONLY" not in artifact
    assert "disallowedTools: Bash" not in header
    assert_mcp_free_generated_artifact(artifact)


def test_probe_droid_managed_agents_artifacts_carry_github_boundary(tmp_path):
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

    assert not (recipe.parent / "dist" / "claude-managed-agents" / "developer-edition").exists()
    assert managed["name"] == "Probe Droid"
    assert managed["model"] == "claude-sonnet-4-6"
    assert managed["metadata"]["endor_agent_kit_recipe_id"] == "probe-droid"
    assert managed["mcp_servers"] == []
    assert "vault_ids" not in session
    assert environment["name"] == "endor-probe-droid"
    assert environment["config"]["networking"]["allowed_hosts"] == [
        "https://api.endorlabs.com",
        "https://api.github.com",
        "https://github.com",
    ]
    assert environment["config"]["networking"]["allow_mcp_servers"] is False

    tools = {tool["type"]: tool for tool in managed["tools"]}
    assert "mcp_toolset" not in tools
    assert tools["agent_toolset_20260401"]["configs"][0]["name"] == "bash"
    assert "This Managed Agents artifact" in managed["system"]
    assert "GitHub.com inventory/file lookups" in managed["system"]
    assert "Do not require Endor MCP" in managed["system"]
    assert "api.github.com" in managed["system"]
    assert "https://api.github.com/orgs/<org>/repos" in managed["system"]
    assert "github_inventory_json" in managed["system"]
    assert "Do not run recursive GitHub tree calls across every repository" in managed["system"]
    assert "Run at most one all-project `PackageVersion` summary query" in managed["system"]


def test_probe_droid_publish_writes_claude_code_managed_and_codex_catalog_surfaces(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert written_paths == {
        "claude-code/probe-droid/probe-droid.md",
        "claude-code/probe-droid/README.md",
        "claude-code/probe-droid/architecture.svg",
        "claude-code/probe-droid/endorctl-setup.md",
        "claude-managed-agents/probe-droid/agent.yaml",
        "claude-managed-agents/probe-droid/environment.yaml",
        "claude-managed-agents/probe-droid/session-template.yaml",
        "claude-managed-agents/probe-droid/README.md",
        "claude-managed-agents/probe-droid/architecture.svg",
        "claude-managed-agents/probe-droid/endorctl-setup.md",
        "codex/probe-droid/SKILL.md",
        "codex/probe-droid/README.md",
        "codex/probe-droid/architecture.svg",
        "codex/probe-droid/endorctl-setup.md",
        "gemini/probe-droid/SKILL.md",
        "gemini/probe-droid/probe-droid.md",
        "gemini/probe-droid/README.md",
        "gemini/probe-droid/architecture.svg",
        "gemini/probe-droid/endorctl-setup.md",
        "portable/probe-droid/README.md",
        "portable/probe-droid/agent.md",
        "portable/probe-droid/agent.manifest.json",
        "portable/probe-droid/output-contract.md",
        "portable/probe-droid/architecture.svg",
        "portable/probe-droid/endorctl-setup.md",
        "manifest.json",
        "README.md",
    }
    agent_dir = dest / "claude-code" / "probe-droid"
    managed_dir = dest / "claude-managed-agents" / "probe-droid"
    codex_dir = dest / "codex" / "probe-droid"
    gemini_dir = dest / "gemini" / "probe-droid"
    portable_dir = dest / "portable" / "probe-droid"
    assert_host_bundle_files(
        agent_dir,
        {"probe-droid.md", "README.md", "architecture.svg", "endorctl-setup.md"},
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
            "Live Command Budget",
            "Do not run `endorctl scan`",
            "All live Endor and GitHub commands MUST be projected",
        ),
    )
    assert_host_bundle_files(
        gemini_dir,
        {"SKILL.md", "probe-droid.md", "README.md", "architecture.svg", "endorctl-setup.md"},
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
    managed_agent = (managed_dir / "agent.yaml").read_text(encoding="utf-8")
    managed_environment = yaml.safe_load((managed_dir / "environment.yaml").read_text(encoding="utf-8"))
    prompt = (agent_dir / "probe-droid.md").read_text(encoding="utf-8")
    codex_skill = (codex_dir / "SKILL.md").read_text(encoding="utf-8")
    codex_readme = (codex_dir / "README.md").read_text(encoding="utf-8")
    gemini_skill = (gemini_dir / "SKILL.md").read_text(encoding="utf-8")
    gemini_readme = (gemini_dir / "README.md").read_text(encoding="utf-8")
    setup = (agent_dir / "endorctl-setup.md").read_text(encoding="utf-8")
    architecture = (agent_dir / "architecture.svg").read_text(encoding="utf-8")

    assert "Probe Droid" in root_readme
    assert "claude-code/probe-droid/" in root_readme
    assert "claude-managed-agents/probe-droid/" in root_readme
    assert "codex/probe-droid/" in root_readme
    assert "gemini/probe-droid/" in root_readme
    assert "portable/probe-droid/" in root_readme
    assert "cp -R /path/to/endor-labs-agent-kit/codex/probe-droid" in root_readme
    assert "Use the probe-droid skill to probe GitHub org <org>" in root_readme
    assert "@agent-probe-droid probe GitHub org <org> for Endor monitored-branch onboarding gaps" in root_readme
    assert "GitHub read-only inventory credentials" in root_readme
    assert "![Probe Droid architecture](architecture.svg)" in agent_readme
    assert "Probe Droid does not need an Endor MCP server" in agent_readme
    assert "GitHub.com repository inventory" in agent_readme
    assert "Read-only GitHub.com credentials available to the managed session" in managed_readme
    assert "Probe GitHub org <org> for Endor monitored-branch onboarding gaps" in managed_readme
    assert "This Managed Agents artifact" in managed_agent
    assert "GitHub.com inventory/file lookups" in managed_agent
    assert "mcp_toolset" not in managed_agent
    assert managed_environment["config"]["networking"]["allowed_hosts"] == [
        "https://api.endorlabs.com",
        "https://api.github.com",
        "https://github.com",
    ]
    assert "Probe Droid Codex Skill" in codex_readme
    assert "No mutating repository, source-provider, or Endor writes for this skill." in codex_readme
    assert "Use the probe-droid skill to probe GitHub org <org>" in codex_readme
    assert "GitHub App selection gaps" in codex_readme
    assert "## Codex Host Contract" in codex_skill
    assert "Do not write source files as part of this agent workflow." in codex_skill
    assert "Probe Droid Gemini CLI Bundle" in gemini_readme
    assert "## Gemini CLI Host Contract" in gemini_skill
    assert "Do not write source files as part of this agent workflow." in gemini_skill
    assert "GitLab" not in agent_readme
    assert "Azure DevOps" not in agent_readme
    assert "Bitbucket" not in agent_readme
    assert "No scans, profile writes" in architecture
    assert "PUBLISHED CONTRACT" in architecture
    assert "GitHub commands must list repositories" in setup
    assert_mcp_free_generated_artifact(prompt)
    assert_mcp_free_generated_artifact(managed_agent)
    assert_mcp_free_generated_artifact(codex_skill)
    assert_mcp_free_generated_artifact(gemini_skill)


def test_probe_droid_raw_setup_documents_github_inventory_boundary(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_raw(recipe)

    setup = (recipe.parent / "dist" / "raw" / "endorctl-setup.md").read_text(encoding="utf-8")
    assert "Probe Droid also needs read-only GitHub.com inventory access" in setup
    assert "must not clone repositories" in setup
    assert "mutate GitHub settings" in setup


def test_probe_droid_eval_cases_cover_onboarding_outcomes():
    evals = yaml.safe_load(
        (repo_root() / "source" / "agents" / "probe-droid" / "evals" / "cases.yaml").read_text()
    )

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "github-org-selected-repos-partial-coverage",
        "private-registry-resolution-error",
        "reachability-blocked-by-resolution-or-toolchain",
        "single-repo-before-onboarding",
        "large-org-stratified-sampling",
        "inactive-and-archived-repository-classification",
        "missing-github-access",
        "selected-repos-sanitized-regression",
    }
    verdicts = {case["expected"]["onboarding_verdict"] for case in evals["cases"]}
    assert verdicts == {"PARTIAL_COVERAGE", "NOT_ONBOARDED", "INSUFFICIENT_DATA"}
    for case in evals["cases"]:
        assert case["expected"]["required_evidence"]
        assert isinstance(case["expected"]["data_gaps_allowed"], bool)


def test_probe_droid_sanitized_fixture_covers_selected_repo_lanes():
    fixture = _fixture()
    counts = fixture["observed_counts"]
    expected = fixture["expected_output"]

    assert counts["github_repositories_in_scope"] == 72
    assert counts["strict_github_org_matches"] == 22
    assert counts["not_onboarded_repositories"] == 50
    assert counts["inactive_repositories_threshold_365_days"] == 28
    assert len(fixture["github_app_coverage"]["selected_repositories"]) == 22
    assert len(fixture["not_onboarded_repositories"]) == 50
    assert fixture["extra_endor_github_projects_outside_org"] == [
        "external-example/java-service"
    ]

    assert expected["onboarding_verdict"] == "PARTIAL_COVERAGE"
    assert expected["executive_report"]["top_counts"] == {
        "github_repositories_in_scope": 72,
        "endor_projects_matched": 22,
        "repositories_not_onboarded": 50,
        "repositories_with_dependency_resolution_gaps": 1,
        "repositories_with_reachability_gaps": 3,
    }
    assert expected["github_app_coverage"] == {
        "status": "APP_INSTALLED_SELECTED_REPOS",
        "selected_repo_count": 22,
        "repositories_not_selected_count": 50,
    }

    gap_by_repo = {
        item["repository"]: item
        for item in expected["onboarded_repositories_with_gaps"]
    }
    npm_gap = gap_by_repo["acme-labs/platform-ui"]
    assert npm_gap["dependency_resolution_reason_codes"] == [
        "DEPENDENCY_RESOLUTION_PRIVATE_REGISTRY"
    ]
    assert npm_gap["package_manager_reason_codes"] == [
        "PACKAGE_MANAGER_AUTH_FAILED"
    ]
    assert npm_gap["reachability_reason_codes"] == [
        "REACHABILITY_DEPENDENCY_RESOLUTION_BLOCKED"
    ]
    assert npm_gap["package_evidence"]["error_category"] == (
        "ERROR_CATEGORY_PRIVATE_REGISTRY"
    )
    assert "dependencies were not downloaded" in npm_gap["package_evidence"]["error_summary"]

    for repo in ("acme-labs/python-webapp", "acme-labs/python-training-app"):
        gap = gap_by_repo[repo]
        assert gap["dependency_resolution_reason_codes"] == [
            "DEPENDENCY_RESOLUTION_TOOLCHAIN_MISSING"
        ]
        assert gap["reachability_reason_codes"] == [
            "REACHABILITY_BUILD_TOOLCHAIN_FAILED"
        ]
        assert "pg_config" in gap["package_evidence"]["error_summary"]
        assert gap["owner_role"] == "platform_team"
        assert gap["confidence"] == "HIGH"

    for action in expected["recommended_actions"]:
        assert action["confirmation_required"] is True
        assert action["owner_role"] in {"endor_admin", "platform_team"}
        assert action["confidence"] == "HIGH"

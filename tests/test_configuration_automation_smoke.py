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
    src = repo_root() / "source" / "agents" / "configuration-automation"
    dst = tmp_path / "configuration-automation"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def _fixture() -> dict:
    return yaml.safe_load(
        (
            repo_root()
            / "tests"
            / "fixtures"
            / "configuration_automation_selected_repos_regression.yaml"
        ).read_text(encoding="utf-8")
    )


def test_configuration_automation_recipe_is_read_only_and_mcp_free(tmp_path):
    recipe = _copy_agent(tmp_path)
    data = yaml.safe_load(recipe.read_text(encoding="utf-8"))

    assert validate_recipe_file(recipe) == []
    assert data["id"] == "configuration-automation"
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
    assert "human-first rollup" in report_mode["description"]
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


def test_configuration_automation_compiled_artifact_carries_onboarding_rules(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_code(recipe)

    artifact = (
        recipe.parent
        / "dist"
        / "claude-code"
        / "enterprise-edition"
        / "configuration-automation.md"
    ).read_text(encoding="utf-8")
    header = artifact.split("---", 2)[1]

    assert "Configuration Automation" in artifact
    assert "## Endor Knowledge Pack" in artifact
    assert "Configuration Automation Evidence Contract" in artifact
    assert "Preferred evidence resources: `Project`, `ScanProfile`, `PackageManager`, `PackageVersion`" in artifact
    assert "Retry Endor project inventory with traversal" in artifact
    assert "GitHub Monitored-Branch Coverage Probe" in artifact
    assert "onboarding_verdict" in artifact
    assert "executive_report" in artifact
    assert "report_mode" in artifact
    assert "human-first rollup" in artifact
    assert "coverage-vs-health distinction" in artifact
    assert "top offenders" in artifact
    assert "report_scope" in artifact
    assert "coverage_summary" in artifact
    assert "`coverage_summary` is mandatory for every response" in artifact
    assert "for one repository, set `total_repositories` to `1`" in artifact
    assert "github_inventory_summary" in artifact
    assert "github_app_coverage" in artifact
    assert "selected_project_uuids" in artifact
    assert "repositories_not_selected" in artifact
    assert "selection_mapping_gaps" in artifact
    assert "not_onboarded_repositories" in artifact
    assert "Do not use words such as `guess`, `assume`, or `likely`" in artifact
    assert "Every `not_onboarded_repositories[]` item must include `default_branch`" in artifact
    assert "Do not omit the key" in artifact
    assert "check that every object in `not_onboarded_repositories`" in artifact
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
    assert "If the user supplied a namespace in the current request, use\nthat provenance and do not inspect local Endor config" in artifact
    assert "Never print or dump an\nentire Endor config file" in artifact
    assert "Do not run `cat ~/.config/endorctl/config.yaml`" in artifact
    assert "Do not read tenant-specific, customer-specific,\nproduction, backup, or non-default Endor config directories" in artifact
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
    assert "GitHub owner URL such as `https://github.com/<owner>`" in artifact
    assert "normalize it to `github_org: <owner>`" in artifact
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
    assert "Use `--list-all` for every project-scoped or targeted `PackageVersion` query" in artifact
    assert "Normalize `spec.resolution_errors` before counting failures" in artifact
    assert "`null` and `{}` are\nnot meaningful resolution failures" in artifact
    assert "empty_resolution_error_object_count" in artifact
    assert "`ScanResult.spec.refs` is version-shaped evidence" in artifact
    assert 'an array of strings such as `["main"]`' in artifact
    assert "Treat `Project.spec.monitored_branch` as" in artifact
    assert "`ScanResult.spec.refs`, then `UNKNOWN` plus a data gap" in artifact
    assert "Some tenants reject `context` in the `Repository` field mask" in artifact
    assert '--field-mask "uuid,meta.name,meta.tags,spec"' in artifact
    assert "A newer version of endorctl\nis available" in artifact
    assert "Keep onboarding coverage and health quality visibly separate" in artifact
    assert "confirmation_required: true" in artifact
    assert "`evidence_queries[]` rows must contain only those fields" in artifact
    assert "must include `filter_summary` plus\n`field_mask_summary`" in artifact
    assert "Do not emit unsupported raw `filter` or `field_mask`\nfields" in artifact
    assert "Repository lane rows describe current evidence only" in artifact
    assert "Put those proposed actions in `recommended_actions[]` or\n`confirmed_org_wide_actions[]`" in artifact
    assert "Do not use\n`requires_confirmation` as a synonym" in artifact
    assert "For single-repository `runtime-smoke` or `evidence-check` runs" in artifact
    assert "keep `sampled_prescription_hypotheses` as an\nempty array" in artifact
    assert "Keep `validation_plan[]` read-only" in artifact
    assert "Do not put future mutation, scan,\nconfiguration, CI setup" in artifact
    assert "perform this strict type and scope self-check" in artifact
    assert "`executive_report` must be a non-empty object" in artifact
    assert "`github_app_coverage` must be a non-empty object, never `null`" in artifact
    assert '"status": "unknown"' in artifact
    assert "`requires_full_inventory_validation` must be an array" in artifact
    assert "`validation_plan` must be an array" in artifact
    assert "Every repository lane row in `not_onboarded_repositories[]`" in artifact
    assert "`ambiguous_matches[]`, and\n  `excluded_repositories[]` must include a normalized `repository`" in artifact
    assert "Do not use\n  `github_repository` as the only normalized repository identifier" in artifact
    assert 'set `default_branch` to `"UNKNOWN"`' in artifact
    assert "Every row in `onboarded_repositories_with_gaps[]` and" in artifact
    assert "`onboarded_healthy_repositories[]` must include `project_uuid`" in artifact
    assert 'Use\n  `endor_monitored_branch: "UNKNOWN"` only in `onboarded_repositories_with_gaps[]`' in artifact
    assert "Never put a row in\n  `onboarded_healthy_repositories[]` unless direct current evidence proves" in artifact
    assert "`report_scope` must include both `namespace` and\n  `namespace_provenance`" in artifact
    assert 'namespace_provenance: "current_request"' in artifact
    assert '"status": "planned_read_only"' in artifact
    assert "No Endor MCP needed" in artifact
    assert "documented read-only Endor and GitHub inventory lookups" in artifact
    assert "glab repo list" not in artifact
    assert "az repos list" not in artifact
    assert "Bitbucket repository inventory" not in artifact
    assert "endorctl toolchains detect" not in artifact
    assert "PR_QUICK_SCAN_ONLY" not in artifact
    assert "disallowedTools: Bash" not in header
    assert_mcp_free_generated_artifact(artifact)


def test_configuration_automation_managed_agents_artifacts_carry_github_boundary(tmp_path):
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
    assert managed["name"] == "Configuration Automation"
    assert managed["model"] == "claude-sonnet-4-6"
    assert managed["metadata"]["endor_agent_kit_recipe_id"] == "configuration-automation"
    assert managed["mcp_servers"] == []
    assert "vault_ids" not in session
    assert environment["name"] == "endor-configuration-automation"
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


def test_configuration_automation_publish_writes_claude_code_managed_and_codex_catalog_surfaces(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert written_paths == {
        "claude-code/configuration-automation/configuration-automation.md",
        "claude-code/configuration-automation/configuration-automation-evidence-check.md",
        "claude-code/configuration-automation/README.md",
        "claude-code/configuration-automation/architecture.svg",
        "claude-code/configuration-automation/endorctl-setup.md",
        "claude-managed-agents/configuration-automation/agent.yaml",
        "claude-managed-agents/configuration-automation/environment.yaml",
        "claude-managed-agents/configuration-automation/session-template.yaml",
        "claude-managed-agents/configuration-automation/README.md",
        "claude-managed-agents/configuration-automation/architecture.svg",
        "claude-managed-agents/configuration-automation/endorctl-setup.md",
        "codex/configuration-automation/SKILL.md",
        "codex/configuration-automation/README.md",
        "codex/configuration-automation/architecture.svg",
        "codex/configuration-automation/endorctl-setup.md",
        "gemini/configuration-automation/SKILL.md",
        "gemini/configuration-automation/configuration-automation.md",
        "gemini/configuration-automation/README.md",
        "gemini/configuration-automation/architecture.svg",
        "gemini/configuration-automation/endorctl-setup.md",
        "portable/configuration-automation/README.md",
        "portable/configuration-automation/agent.md",
        "portable/configuration-automation/agent.manifest.json",
        "portable/configuration-automation/output-contract.md",
        "portable/configuration-automation/architecture.svg",
        "portable/configuration-automation/endorctl-setup.md",
        "manifest.json",
        "README.md",
        "catalog.json",
    }
    agent_dir = dest / "claude-code" / "configuration-automation"
    managed_dir = dest / "claude-managed-agents" / "configuration-automation"
    codex_dir = dest / "codex" / "configuration-automation"
    gemini_dir = dest / "gemini" / "configuration-automation"
    portable_dir = dest / "portable" / "configuration-automation"
    assert_host_bundle_files(
        agent_dir,
        {"configuration-automation.md", "README.md", "architecture.svg", "endorctl-setup.md"},
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
        {"SKILL.md", "configuration-automation.md", "README.md", "architecture.svg", "endorctl-setup.md"},
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
    prompt = (agent_dir / "configuration-automation.md").read_text(encoding="utf-8")
    codex_skill = (codex_dir / "SKILL.md").read_text(encoding="utf-8")
    codex_readme = (codex_dir / "README.md").read_text(encoding="utf-8")
    gemini_skill = (gemini_dir / "SKILL.md").read_text(encoding="utf-8")
    gemini_readme = (gemini_dir / "README.md").read_text(encoding="utf-8")
    setup = (agent_dir / "endorctl-setup.md").read_text(encoding="utf-8")
    architecture = (agent_dir / "architecture.svg").read_text(encoding="utf-8")

    assert "Configuration Automation" in root_readme
    assert "claude-code/configuration-automation/" in root_readme
    assert "claude-managed-agents/configuration-automation/" in root_readme
    assert "codex/configuration-automation/" in root_readme
    assert "gemini/configuration-automation/" in root_readme
    assert "portable/configuration-automation/" in root_readme
    assert "cp -R /path/to/endor-labs-agent-kit/codex/configuration-automation" in root_readme
    assert "Use the configuration-automation skill to probe GitHub org <org>" in root_readme
    assert "@agent-configuration-automation probe GitHub org <org> for Endor monitored-branch onboarding gaps" in root_readme
    assert "GitHub read-only inventory credentials" in root_readme
    assert "![Configuration Automation architecture](architecture.svg)" in agent_readme
    assert "Configuration Automation does not need an Endor MCP server" in agent_readme
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
    assert "Configuration Automation Codex Skill" in codex_readme
    assert "No mutating repository, source-provider, or Endor writes for this skill." in codex_readme
    assert "Use the configuration-automation skill to probe GitHub org <org>" in codex_readme
    assert "GitHub App selection gaps" in codex_readme
    assert "## Codex Host Contract" in codex_skill
    assert "Do not write source files as part of this agent workflow." in codex_skill
    assert "Configuration Automation Gemini CLI Bundle" in gemini_readme
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


def test_configuration_automation_raw_setup_documents_github_inventory_boundary(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_raw(recipe)

    setup = (recipe.parent / "dist" / "raw" / "endorctl-setup.md").read_text(encoding="utf-8")
    assert "Configuration Automation also needs read-only GitHub.com inventory access" in setup
    assert "must not clone repositories" in setup
    assert "mutate GitHub settings" in setup


def test_configuration_automation_eval_cases_cover_onboarding_outcomes():
    evals = yaml.safe_load(
        (repo_root() / "source" / "agents" / "configuration-automation" / "evals" / "cases.yaml").read_text()
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
        "org-url-under-repository-urls-normalized",
        "endor-field-shape-normalization",
    }
    verdicts = {case["expected"]["onboarding_verdict"] for case in evals["cases"]}
    assert verdicts == {"PARTIAL_COVERAGE", "NOT_ONBOARDED", "INSUFFICIENT_DATA"}
    for case in evals["cases"]:
        assert case["expected"]["required_evidence"]
        assert isinstance(case["expected"]["data_gaps_allowed"], bool)


def test_configuration_automation_sanitized_fixture_covers_selected_repo_lanes():
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

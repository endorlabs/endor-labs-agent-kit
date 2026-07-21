from __future__ import annotations

from pathlib import Path

import yaml

from conftest import repo_root
from endor_agent_kit.ai_sast_triage import validate_ai_sast_gate_payload
from endor_agent_kit.knowledge_pack import (
    PACK_SECTION_HEADING,
    default_task_profile_for_agent,
    load_knowledge_pack,
    render_knowledge_pack_section,
    render_task_profile_prompt,
    validate_knowledge_pack,
)
from endor_agent_kit.recipe import load_yaml_file


def test_default_knowledge_pack_validates_against_source_agents():
    agent_ids = {
        str(load_yaml_file(path)["id"])
        for path in (repo_root() / "source" / "agents").glob("*/recipe.yaml")
    }

    assert validate_knowledge_pack(agent_ids=agent_ids) == []


def test_knowledge_pack_loader_exposes_precedence_and_global_rules():
    pack = load_knowledge_pack()

    assert pack.name == "Endor Knowledge Pack"
    assert sorted(pack.query_recipes) == [
        "ai-sast-count",
        "ai-sast-list",
        "cicd-posture-findings",
        "current-malware-intelligence",
        "endor-repo-codeowners",
        "endor-repo-tag-protection",
        "endor-repository-config",
        "exposure-guidance-source",
        "finding-browser-by-tag",
        "finding-browser-complete-counts",
        "finding-browser-filtered",
        "finding-by-uuid",
        "github-branch-protection",
        "github-workflow-files",
        "local-git-state",
        "local-manifest-inventory",
        "mcp-finding-by-uuid-check",
        "mcp-finding-by-uuid-full",
        "mcp-vulnerability-by-id-check",
        "mcp-vulnerability-by-id-full",
        "mcp-vulnerability-enrichment",
        "package-version-exact",
        "project-branch-coverage",
        "project-by-git",
        "project-by-uuid",
        "sca-exploited-finding-availability",
        "sca-finding-availability",
        "sca-finding-package-severity-groups",
        "scan-result-by-uuid",
        "selected-source-usage",
        "tenant-malware-findings",
        "tenant-package-inventory",
        "tenant-package-version-exact",
        "version-upgrade-by-package",
        "version-upgrade-count",
        "version-upgrade-detail",
        "version-upgrade-summary",
    ]
    assert set(pack.workflows) == {
        "ai-sast-triage",
        "cicd-posture",
        "dependency-decision-helper",
        "endor-troubleshooter",
        "findings-browser",
        "malware-response",
        "package-risk-summary",
        "probe-droid",
        "remediation-planner",
        "repository-dependency-reviewer",
        "sca-remediation",
        "upgrade-impact-analysis",
        "vulnerability-explainer",
    }
    assert any("workflow output contracts" in item for item in pack.precedence)
    assert any("source recipe instructions" in item for item in pack.precedence)
    assert [rule.id for rule in pack.global_rules] == [
        "context-first",
        "namespace-provenance",
        "query-efficiency",
        "verified-evidence",
        "evidence-ledger",
        "data-gaps",
    ]
    assert [profile.id for profile in pack.workflow_for("sca-remediation").task_profiles] == [
        "resolve-scope",
        "evidence-check",
        "selection-plan",
    ]
    assert [plan.profile_id for plan in pack.workflow_for("sca-remediation").evidence_query_plans] == [
        "resolve-scope",
        "evidence-check",
        "selection-plan",
    ]
    assert [
        recipe.id
        for recipe in pack.workflow_for("sca-remediation").evidence_query_recipes_for("selection-plan")
    ] == [
        "version-upgrade-summary",
        "version-upgrade-detail",
        "selected-source-usage",
        "selected-finding-detail",
    ]
    query_efficiency = next(rule for rule in pack.global_rules if rule.id == "query-efficiency")
    assert "--list-all" in query_efficiency.guidance
    assert "Use `--count` when only a complete scoped total matters" in query_efficiency.guidance
    assert "approved group aggregation paths" in query_efficiency.guidance
    assert "`--list-all` only when complete matching rows are required" in query_efficiency.guidance
    assert "Run independent compatible reads concurrently" in query_efficiency.guidance
    assert "early-stop" in query_efficiency.guidance
    ai_sast_recipe = next(
        recipe
        for recipe in pack.workflow_for("ai-sast-triage").evidence_query_recipes
        if recipe.id == "ai-sast-count"
    )
    assert ai_sast_recipe.canonical_id == "ai-sast-count"
    assert "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST" in ai_sast_recipe.template
    assert 'finding_tags contains "AI_SAST"' not in ai_sast_recipe.template
    assert "--count" in ai_sast_recipe.template
    assert "--list-all" not in ai_sast_recipe.template
    assert "spec.explanation" not in ai_sast_recipe.template
    assert "spec.explanation" not in ai_sast_recipe.fields
    assert all(
        recipe.canonical_id in pack.query_recipes
        for workflow in pack.workflows.values()
        for recipe in workflow.evidence_query_recipes
    )


def test_canonical_sca_finding_aggregation_preserves_package_and_severity_dimensions():
    recipe = load_knowledge_pack().query_recipes["sca-finding-package-severity-groups"]

    assert recipe.resource == "Finding"
    assert (
        "--group-aggregation-paths spec.target_dependency_package_name,spec.level"
        in recipe.template
    )
    assert "--field-mask" not in recipe.template
    assert "--list-all" not in recipe.template
    assert recipe.fields == (
        "group_response.groups",
        "aggregation_count.count",
        "spec.target_dependency_package_name",
        "spec.level",
    )


def test_canonical_version_upgrade_count_is_count_only_and_project_scoped():
    recipe = load_knowledge_pack().query_recipes["version-upgrade-count"]

    assert recipe.resource == "VersionUpgrade"
    assert 'spec.project_uuid=="<PROJECT_UUID>"' in recipe.template
    assert "spec.upgrade_info.worth_it==true" in recipe.template
    assert "--count" in recipe.template
    assert "--field-mask" not in recipe.template
    assert "--list-all" not in recipe.template
    assert recipe.fields == ("count",)


def test_canonical_ai_sast_count_is_metadata_free_and_main_context_scoped():
    recipe = load_knowledge_pack().query_recipes["ai-sast-count"]

    assert recipe.resource == "Finding"
    assert "context.type==CONTEXT_TYPE_MAIN" in recipe.template
    assert 'spec.project_uuid=="<PROJECT_UUID>"' in recipe.template
    assert 'spec.method=="SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"' in recipe.template
    assert "--count" in recipe.template
    assert "--field-mask" not in recipe.template
    assert "--list-all" not in recipe.template
    assert "spec.explanation" not in recipe.template
    assert recipe.fields == ("count",)


def test_canonical_project_by_uuid_uses_exact_get_without_filter():
    recipe = load_knowledge_pack().query_recipes["project-by-uuid"]

    assert recipe.resource == "Project"
    assert " get -r Project " in recipe.template
    assert "--uuid <PROJECT_UUID>" in recipe.template
    assert "--filter" not in recipe.template
    assert recipe.fields == (
        "uuid",
        "meta.name",
        "meta.parent_uuid",
        "spec.git",
    )


def test_sca_composite_aggregation_fixture_preserves_counts_and_package_set():
    fixture = yaml.safe_load(
        (repo_root() / "tests" / "fixtures" / "sca_finding_aggregation.yaml").read_text(
            encoding="utf-8"
        )
    )
    recipe = load_knowledge_pack().query_recipes["sca-finding-package-severity-groups"]
    encoded_paths = recipe.template.split("--group-aggregation-paths ", 1)[1].split(" ", 1)[0]
    paths = tuple(encoded_paths.split(","))

    grouped: dict[tuple[str, str], int] = {}
    for finding in fixture["findings"]:
        spec = finding["spec"]
        key = (spec["target_dependency_package_name"], spec["level"])
        grouped[key] = grouped.get(key, 0) + 1

    expected_groups = {
        (row["package"], row["severity"]): row["count"]
        for row in fixture["expected"]["groups"]
    }
    packages = sorted({package for package, _severity in grouped})
    severity_counts: dict[str, int] = {}
    for (_package, severity), count in grouped.items():
        severity_counts[severity] = severity_counts.get(severity, 0) + count

    assert paths == tuple(fixture["required_group_paths"])
    assert grouped == expected_groups
    assert packages == fixture["expected"]["packages"]
    assert severity_counts == fixture["expected"]["severity_counts"]
    assert sum(grouped.values()) == fixture["expected"]["total_count"]


def test_sca_evidence_check_promotes_two_bounded_reads_after_fixture_parity():
    workflow = load_knowledge_pack().workflow_for("sca-remediation")
    assert workflow is not None
    recipes = workflow.evidence_query_recipes_for("evidence-check")
    plan = workflow.evidence_query_plan_for("evidence-check")

    assert [recipe.id for recipe in recipes] == [
        "finding-package-severity-groups",
        "version-upgrade-count",
    ]
    assert [recipe.canonical_id for recipe in recipes] == [
        "sca-finding-package-severity-groups",
        "version-upgrade-count",
    ]
    assert all("--list-all" not in recipe.template for recipe in recipes)
    assert plan is not None
    assert any("concurrently" in step for step in plan.query_order)
    assert any("exploited" in item for item in plan.stop_after)


def test_ai_sast_routing_fixture_preserves_uuid_and_no_uuid_evidence_contracts():
    fixture = yaml.safe_load(
        (repo_root() / "tests" / "fixtures" / "ai_sast_routing.yaml").read_text(
            encoding="utf-8"
        )
    )
    workflow = load_knowledge_pack().workflow_for("ai-sast-triage")
    assert workflow is not None
    recipes = {
        recipe.id: recipe
        for recipe in workflow.evidence_query_recipes_for("evidence-check")
    }
    plan = workflow.evidence_query_plan_for("evidence-check")

    known_uuid = fixture["cases"]["known_uuid"]
    without_uuid = fixture["cases"]["without_uuid"]

    assert known_uuid["expected_route"]["initial_recipe"] == "finding-by-uuid"
    assert known_uuid["expected_route"]["conditional_recipe"] == "project-by-uuid"
    assert known_uuid["expected_route"]["maximum_endor_operations"] == 2
    assert validate_ai_sast_gate_payload(known_uuid["expected_output"]) == []
    assert (
        known_uuid["expected_output"]["verdicts"][0]["source_ref_provenance"]
        == "finding_source_ref_not_default_branch_proof"
    )

    assert without_uuid["expected_route"]["recipes"] == [
        "project-by-git",
        "ai-sast-count",
    ]
    assert without_uuid["expected_route"]["maximum_endor_operations"] == 2
    assert set(recipes) == {
        "finding-by-uuid",
        "project-by-uuid",
        "project-by-git",
        "ai-sast-count",
    }
    assert "--count" in recipes["ai-sast-count"].template
    assert "--list-all" not in recipes["ai-sast-count"].template
    assert "spec.explanation" not in recipes["ai-sast-count"].template
    assert plan is not None
    assert any("Finding UUID first" in step for step in plan.query_order)
    assert any("not proof of the repository default branch" in item for item in plan.avoid)


def test_runtime_task_profile_prompts_carry_gemini_contract_guards():
    troubleshooter = render_task_profile_prompt("endor-troubleshooter", "diagnose", compact=True)
    probe = render_task_profile_prompt("probe-droid", "evidence-check", compact=True)
    probe_full = render_knowledge_pack_section("probe-droid")

    assert "every nested issue_lanes.next_step, validation, action, why, reasoning" in troubleshooter
    assert "free of raw tool names or command-shaped" in troubleshooter
    assert "run a baseline scan" in troubleshooter
    assert "Every future_action_contracts row must include" in troubleshooter
    assert "confirmation_required true" in troubleshooter
    assert "github_app_coverage must be a non-empty" in probe
    assert "Every repository lane row, including ambiguous_matches" in probe
    assert "not github_repository alone" in probe
    assert "Onboarded" in probe
    assert "project_uuid and endor_monitored_branch" in probe
    assert "not onboarded_healthy_repositories" in probe
    assert "coverage counts separate from health quality" in probe
    assert "Project.spec.monitored_branch" in probe
    assert "ScanResult.spec.refs" in probe
    assert "resolution_errors: {}" in probe_full


def test_knowledge_pack_renders_global_section_for_known_agent():
    section = render_knowledge_pack_section("sca-remediation")

    assert section.startswith(PACK_SECTION_HEADING)
    assert "Context first" in section
    assert "Evidence Gate Contract" in section
    assert "Scope Normalization Contract" in section
    assert "normalized repo identity" in section
    assert "Mutability Gate Contract" in section
    assert "future action contract" in section
    assert "Agent Task Profiles" in section
    assert "`selection-plan` - Selection Plan" in section
    assert "Evidence Query Plans" in section
    assert "`selection-plan` - Selection Plan Query Plan" in section
    assert "Evidence Query Recipes" in section
    assert "`version-upgrade-summary` (selection-plan)" in section
    assert "Canonical: `version-upgrade-summary`" in section
    assert "endorctl agent api --agent-id <agent-id> list -r VersionUpgrade -n <namespace>" in section
    assert "narrowing through VersionUpgrade before detailed Finding expansion" in section
    assert "Never use memory" in section
    assert "Never dump or `cat` Endor config files" in section
    assert "SCA Remediation Evidence Contract" in section
    assert "Preferred evidence resources: `Project`, `Finding`, `VersionUpgrade`" in section
    assert "namespace_provenance" in section
    assert "data_gaps" in section
    assert "Workflow output contracts" in section


def test_profile_scoped_knowledge_section_omits_other_profiles_and_plans():
    section = render_knowledge_pack_section("sca-remediation", profile_id="evidence-check")

    assert "`evidence-check` - Evidence Check" in section
    assert "`evidence-check` - Evidence Availability Query Plan" in section
    assert "`resolve-scope` - Resolve Scope" not in section
    assert "`selection-plan` - Selection Plan" not in section
    assert "(resolve-scope)" not in section
    assert "(selection-plan)" not in section


def test_knowledge_pack_renders_task_profile_prompt():
    prompt = render_task_profile_prompt("sca-remediation", "selection-plan")

    assert "Agent task profile: `selection-plan`" in prompt
    assert "Use this compact profile instead of running the full workflow" in prompt
    assert "Stop when:" in prompt
    assert "Minimal evidence:" in prompt
    assert "VersionUpgrade/UIA evidence" in prompt
    assert "Evidence query plan:" in prompt
    assert "Query VersionUpgrade/UIA candidate summaries" in prompt
    assert "Do not enumerate broad Finding inventories" in prompt
    assert "Evidence query recipes:" in prompt
    assert "version-upgrade-summary" in prompt
    assert "canonical `version-upgrade-summary`" in prompt
    assert "--field-mask" in prompt
    assert "Output focus:" in prompt
    assert default_task_profile_for_agent("sca-remediation") == "selection-plan"

    compact = render_task_profile_prompt("sca-remediation", "selection-plan", compact=True)

    assert "Minimal evidence:" in compact
    assert "Required output focus:" in compact
    assert "resource is `Finding`" in compact
    assert "selected_remediation.branch_name" in compact
    assert "change_requests[].proposed_branch" in compact
    assert "never use selection labels such as `selected`" in compact


def test_cicd_posture_compact_profile_keeps_endor_native_recipes():
    compact = render_task_profile_prompt("cicd-posture", "posture", compact=True)

    assert "endor-repository-config" in compact
    assert "endor-repo-codeowners" in compact
    assert "endor-repo-tag-protection" in compact
    assert "github-branch-protection" not in compact


def test_measured_slow_read_profiles_have_compact_output_contracts():
    pack = load_knowledge_pack()
    probe = pack.workflow_for("probe-droid").task_profile_for("evidence-check")
    troubleshooter = pack.workflow_for("endor-troubleshooter").task_profile_for("diagnose")

    assert probe.compact is True
    assert probe.output_fields == (
        "onboarding_verdict",
        "executive_report",
        "report_scope",
        "coverage_summary",
        "github_inventory_summary",
        "github_app_coverage",
        "not_onboarded_repositories",
        "onboarded_repositories_with_gaps",
        "onboarded_healthy_repositories",
        "ambiguous_matches",
        "evidence_queries",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    )
    assert troubleshooter.compact is True
    assert "evidence_queries" in troubleshooter.output_fields
    assert "data_gaps" in troubleshooter.output_fields


def test_malware_workflow_uses_supported_finding_category_evidence():
    workflow = load_knowledge_pack().workflow_for("malware-response")
    section = render_knowledge_pack_section("malware-response")

    assert workflow is not None
    assert "Malware" not in {resource.name for resource in workflow.resources}
    assert "Endor OSS Malware feed" not in section
    assert "FINDING_CATEGORY_MALWARE" in section
    assert "tenant-malware-findings" in section


def test_knowledge_pack_validator_rejects_unknown_workflow_agent(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "unknown-agent.yaml").write_text(
        yaml.safe_dump(
            {
                "agent_id": "unknown-agent",
                "title": "Unknown Agent Contract",
                "summary": "Use namespace evidence and report data_gaps.",
                "resources": [
                    {
                        "name": "Project",
                        "purpose": "Resolve namespace-scoped project identity.",
                        "fields": ["uuid", "meta.name"],
                    }
                ],
                "retrieval_steps": ["Resolve namespace and project evidence."],
                "fallbacks": ["Record lookup failures in data_gaps."],
                "data_gaps": ["Record missing namespace access in data_gaps."],
                "task_profiles": [
                    {
                        "id": "evidence-check",
                        "title": "Evidence Check",
                        "summary": "Use namespace evidence and report data_gaps.",
                        "when_to_use": ["Use for read-only evidence checks."],
                        "minimal_evidence": ["Namespace evidence or data_gaps."],
                        "stop_when": ["Evidence is known or data_gaps are recorded."],
                        "output_focus": ["Return evidence_queries and data_gaps."],
                    }
                ],
                "evidence_query_plans": [
                    {
                        "profile_id": "evidence-check",
                        "title": "Evidence Check Query Plan",
                        "objective": "Check namespace evidence and record data_gaps.",
                        "query_order": ["Resolve namespace evidence."],
                        "avoid": ["Do not guess missing namespace evidence."],
                        "stop_after": ["Stop after evidence exists or data_gaps are recorded."],
                        "data_gaps": ["Record missing namespace evidence in data_gaps."],
                    }
                ],
                "evidence_query_recipes": [
                    {
                        "profile_id": "evidence-check",
                        "id": "project-by-git",
                        "resource": "Project",
                        "purpose": "Resolve namespace evidence.",
                        "template": "endorctl agent api --agent-id <agent-id> list -r Project -n <namespace> --field-mask \"uuid,meta.name\" -o json",
                        "fields": ["uuid", "meta.name"],
                        "constraints": ["Record missing namespace evidence in data_gaps."],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("references unknown agent 'unknown-agent'" in error for error in errors)


def test_knowledge_pack_validator_rejects_forbidden_public_wording(tmp_path):
    forbidden = "python " + "package"
    _write_minimal_pack(
        tmp_path,
        global_rule_guidance=f"Use a {forbidden} to fetch evidence.",
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any(f"forbidden public wording {forbidden!r}" in error for error in errors)


def test_knowledge_pack_validator_rejects_query_plan_for_unknown_profile(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_plans"][0]["profile_id"] = "unknown-profile"
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("references unknown task profile 'unknown-profile'" in error for error in errors)
    assert any("missing plan for task profile 'evidence-check'" in error for error in errors)


def test_knowledge_pack_validator_rejects_sca_selection_plan_finding_first(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["task_profiles"].append(
        {
            "id": "selection-plan",
            "title": "Selection Plan",
            "summary": "Select one candidate and report data_gaps.",
            "when_to_use": ["Use when selecting a remediation."],
            "minimal_evidence": ["VersionUpgrade and Finding evidence or data_gaps."],
            "stop_when": ["Stop with data_gaps when evidence is missing."],
            "output_focus": ["Return selected_remediation and data_gaps."],
        }
    )
    workflow["evidence_query_plans"].append(
        {
            "profile_id": "selection-plan",
            "title": "Selection Plan Query Plan",
            "objective": "Select one candidate and record data_gaps.",
            "query_order": [
                "Query Finding evidence first.",
                "Query VersionUpgrade evidence second.",
            ],
            "avoid": ["Do not guess missing data_gaps."],
            "stop_after": ["Stop after selection or data_gaps."],
            "data_gaps": ["Record missing evidence in data_gaps."],
        }
    )
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("selection-plan must narrow with VersionUpgrade before Finding detail expansion" in error for error in errors)


def test_knowledge_pack_validator_rejects_unsafe_query_recipe_template(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["template"] = "endorctl agent api --agent-id <agent-id> list -r Finding --list-all -o json"
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("must include explicit namespace" in error for error in errors)
    assert any("must include --field-mask" in error for error in errors)
    assert any("broad Finding --list-all templates are not allowed" in error for error in errors)


def test_knowledge_pack_validator_rejects_unknown_canonical_query_recipe_ref(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["canonical_id"] = "missing-query"
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any(
        "references unknown canonical query recipe 'missing-query'" in error
        for error in errors
    )


def test_knowledge_pack_validator_rejects_canonical_query_recipe_template_drift(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["canonical_id"] = "project-by-git"
    workflow["evidence_query_recipes"][0]["template"] = (
        'endorctl agent api --agent-id <agent-id> list -r Project -n <namespace> --field-mask "uuid" -o json'
    )
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any(
        "template does not match canonical query recipe 'project-by-git'" in error
        for error in errors
    )


def test_knowledge_pack_validator_rejects_unsafe_canonical_query_recipe_template(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template="endorctl agent api --agent-id <agent-id> list -r Finding --list-all -o json",
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any("query-recipes.yaml recipes[0].template: endorctl agent api commands must include explicit namespace" in error for error in errors)
    assert any("query-recipes.yaml recipes[0].template: endorctl agent api list commands must include --field-mask" in error for error in errors)
    assert any("query-recipes.yaml recipes[0].template: broad Finding --list-all templates are not allowed" in error for error in errors)


def test_knowledge_pack_validator_accepts_count_only_list_without_field_mask(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> "
            "--filter 'context.type==CONTEXT_TYPE_MAIN' --count -o json"
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert not any("must include --field-mask" in error for error in errors)


def test_knowledge_pack_validator_rejects_count_with_list_all(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> "
            "--filter 'context.type==CONTEXT_TYPE_MAIN' --count --list-all -o json"
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any("count-only list commands must not include --list-all" in error for error in errors)


def test_knowledge_pack_validator_accepts_approved_finding_grouping_without_field_mask(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> "
            "--filter 'context.type==CONTEXT_TYPE_MAIN' "
            "--group-aggregation-paths spec.target_dependency_package_name,spec.level -o json"
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert not any("must include --field-mask" in error for error in errors)
    assert not any("group aggregation" in error for error in errors)


def test_knowledge_pack_validator_rejects_empty_group_aggregation_paths(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> "
            "--filter 'context.type==CONTEXT_TYPE_MAIN' --group-aggregation-paths -o json"
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any("group aggregation requires at least one path" in error for error in errors)


def test_knowledge_pack_validator_rejects_unapproved_finding_group_path(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> "
            "--filter 'context.type==CONTEXT_TYPE_MAIN' "
            "--group-aggregation-paths spec.finding_metadata -o json"
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any(
        "group aggregation path 'spec.finding_metadata' is not approved for Finding"
        in error
        for error in errors
    )


def test_knowledge_pack_validator_rejects_grouping_with_list_all(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> "
            "--filter 'context.type==CONTEXT_TYPE_MAIN' "
            "--group-aggregation-paths spec.target_dependency_package_name,spec.level "
            "--list-all -o json"
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any("grouped list commands must not include --list-all" in error for error in errors)


def test_knowledge_pack_validator_rejects_field_mask_parent_child_collisions(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            'endorctl agent api --agent-id <agent-id> list -r VersionUpgrade -n <namespace> '
            '--field-mask "uuid,spec.upgrade_info,spec.upgrade_info.cia_results" -o json'
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any("field-mask must not include both a parent path and child path" in error for error in errors)


def test_knowledge_pack_validator_accepts_scoped_ai_sast_list_all_query(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["template"] = (
        'endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> --filter '
        '\'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="<PROJECT_UUID>" '
        'and spec.method=="SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"\' '
        '--field-mask "uuid,context.type,spec.project_uuid,spec.method" --list-all -o json'
    )
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert "workflows/sca-remediation.yaml evidence_query_recipes[0].template: broad Finding --list-all templates are not allowed" not in errors


def test_knowledge_pack_validator_accepts_scoped_finding_count_list_all_query(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["template"] = (
        "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace> --filter "
        "'<SCOPE_FILTER> and spec.dismiss==false and spec.level in [<LEVELS>] "
        "and spec.finding_categories contains <FINDING_CATEGORY>' "
        '--field-mask "uuid,spec.level,spec.finding_categories" --list-all -o json'
    )
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert "workflows/sca-remediation.yaml evidence_query_recipes[0].template: broad Finding --list-all templates are not allowed" not in errors


def _write_minimal_pack(root: Path, *, global_rule_guidance: str = "Record data_gaps.") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "name": "Endor Knowledge Pack",
                "version": "0.1.0",
                "precedence": [
                    "workflow output contracts and hard guardrails remain authoritative",
                    "source recipe instructions remain authoritative over this pack",
                    "Endor Knowledge Pack guidance augments generated recipes",
                ],
                "global_rules": [
                    {
                        "id": "context-first",
                        "title": "Context first",
                        "guidance": global_rule_guidance,
                    },
                    {
                        "id": "namespace-provenance",
                        "title": "Namespace provenance",
                        "guidance": "Record namespace_provenance.",
                    },
                    {
                        "id": "query-efficiency",
                        "title": "Efficient Endor queries",
                        "guidance": "Use field masks.",
                    },
                    {
                        "id": "verified-evidence",
                        "title": "Verified evidence only",
                        "guidance": "Use verified evidence.",
                    },
                    {
                        "id": "data-gaps",
                        "title": "Data gaps",
                        "guidance": "Record data_gaps.",
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_minimal_query_catalog(
    root: Path,
    *,
    template: str = 'endorctl agent api --agent-id <agent-id> list -r Project -n <namespace> --field-mask "uuid,meta.name" -o json',
) -> None:
    (root / "query-recipes.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "recipes": [
                    {
                        "id": "project-by-git",
                        "title": "Project By Git",
                        "resource": "Project",
                        "purpose": "Resolve project evidence.",
                        "template": template,
                        "fields": ["uuid", "meta.name"],
                        "constraints": ["Use explicit namespace."],
                        "completeness": "Complete for one selected namespace.",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _minimal_workflow() -> dict:
    return {
        "agent_id": "sca-remediation",
        "title": "SCA Remediation Evidence Contract",
        "summary": "Use namespace evidence and report data_gaps.",
        "resources": [
            {
                "name": "Project",
                "purpose": "Resolve namespace-scoped project identity.",
                "fields": ["uuid", "meta.name"],
            }
        ],
        "retrieval_steps": ["Resolve namespace and project evidence."],
        "fallbacks": ["Record lookup failures in data_gaps."],
        "data_gaps": ["Record missing namespace access in data_gaps."],
        "task_profiles": [
            {
                "id": "evidence-check",
                "title": "Evidence Check",
                "summary": "Use namespace evidence and report data_gaps.",
                "when_to_use": ["Use for read-only evidence checks."],
                "minimal_evidence": ["Namespace evidence or data_gaps."],
                "stop_when": ["Evidence is known or data_gaps are recorded."],
                "output_focus": ["Return evidence_queries and data_gaps."],
            }
        ],
        "evidence_query_plans": [
            {
                "profile_id": "evidence-check",
                "title": "Evidence Check Query Plan",
                "objective": "Check namespace evidence and record data_gaps.",
                "query_order": ["Resolve namespace evidence."],
                "avoid": ["Do not guess missing namespace evidence."],
                "stop_after": ["Stop after evidence exists or data_gaps are recorded."],
                "data_gaps": ["Record missing namespace evidence in data_gaps."],
            }
        ],
        "evidence_query_recipes": [
            {
                "profile_id": "evidence-check",
                "id": "project-by-git",
                "resource": "Project",
                "purpose": "Resolve namespace evidence.",
                "template": "endorctl agent api --agent-id <agent-id> list -r Project -n <namespace> --field-mask \"uuid,meta.name\" -o json",
                "fields": ["uuid", "meta.name"],
                "constraints": ["Record missing namespace evidence in data_gaps."],
            }
        ],
    }

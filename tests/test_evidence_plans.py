from __future__ import annotations

from dataclasses import replace
import json

from endor_agent_kit.evidence_plans import (
    EVIDENCE_PLAN_SCHEMA_VERSION,
    compile_evidence_plan,
    compile_evidence_plans,
    validate_evidence_plan,
)
from endor_agent_kit.profile_contracts import compile_profile_contract


DEFAULT_EVIDENCE_PLAN_PROFILES = {
    "ai-sast-remediation": "evidence-check",
    "cicd-posture": "posture",
    "configuration-automation": "evidence-check",
    "dependency-reviewer": "repository-review",
    "findings-browser": "browse",
    "malware-responder": "exposure-check",
    "oss-upgrade-investigator": "evidence-check",
    "remediation-planning": "selection-plan",
    "sca-remediation": "selection-plan",
    "troubleshooting": "diagnose",
}


def test_compiled_sca_evidence_plan_is_deterministic_and_source_bound():
    first = compile_evidence_plan("sca-remediation", "evidence-check")
    second = compile_evidence_plan("sca-remediation", "evidence-check")

    assert first.to_json_bytes() == second.to_json_bytes()
    assert validate_evidence_plan(first) == []
    payload = json.loads(first.to_json_bytes())
    assert payload["schema_version"] == EVIDENCE_PLAN_SCHEMA_VERSION
    assert payload["agent_id"] == "sca-remediation"
    assert payload["profile_id"] == "evidence-check"
    assert payload["execution"] == {
        "host_adapter_required": True,
        "mode": "prompt_fallback",
        "prompt_recipes_exposed": True,
    }
    assert payload["gate"]["expected_calls"] == 3
    assert payload["gate"]["max_calls"] == 4
    assert payload["steps"][0]["template"].startswith(
        "endorctl agent api --agent-id sca-remediation list"
    )
    assert [step["id"] for step in payload["steps"]] == [
        "project-by-git",
        "finding-package-severity-groups",
        "version-upgrade-count",
    ]
    assert payload["steps"][1]["concurrency_group"] == "availability"
    assert payload["steps"][2]["concurrency_group"] == "availability"
    for digest_name in (
        "plan_digest",
        "source_digest",
        "agent_source_digest",
        "profile_contract_digest",
        "knowledge_pack_digest",
    ):
        assert len(payload["provenance"][digest_name]) == 64
        int(payload["provenance"][digest_name], 16)


def test_compiled_ai_sast_plan_has_mutually_exclusive_uuid_routes():
    plan = compile_evidence_plan("ai-sast-remediation", "evidence-check")

    routes = {route.id: route for route in plan.routes}
    assert routes["known-finding"].condition == "runtime.finding_uuid_present"
    assert routes["repository"].condition == "runtime.finding_uuid_absent"
    assert {route.exclusive_group for route in routes.values()} == {"finding-selector"}
    assert routes["known-finding"].expected_calls == 1
    assert routes["known-finding"].max_calls == 2
    assert routes["repository"].expected_calls == 2
    assert routes["repository"].max_calls == 3
    project_label = next(step for step in plan.steps if step.id == "project-by-uuid")
    assert project_label.condition == "steps.finding-by-uuid.repository_identity_missing"


def test_compiled_ai_sast_known_finding_emits_compact_domain_evidence():
    plan = compile_evidence_plan("ai-sast-remediation", "evidence-check")
    finding = next(step for step in plan.steps if step.id == "finding-by-uuid")
    outputs = {output.name: output for output in finding.outputs}

    assert tuple(outputs) == (
        "finding_uuid",
        "project_uuid",
        "source_ref",
        "repository_identity",
        "finding_name",
        "severity",
        "cwe",
        "source_location",
        "file_path",
        "source_sha",
        "sast_rule_id",
        "classification_evidence",
        "data_flow_summary",
    )
    assert outputs["classification_evidence"].path == (
        "$.spec.finding_metadata.ai_sast_data.verification_scorecard"
    )
    assert outputs["classification_evidence"].required is False
    assert outputs["file_path"].path == (
        "$.spec.finding_metadata.ai_sast_data.location.relative_path"
    )
    assert all(output.required is False for output in tuple(outputs.values())[2:])
    assert all("exploit_reproduction" not in output.path for output in outputs.values())
    assert all("remediation" not in output.path for output in outputs.values())


def test_compiled_ai_sast_selection_plan_uses_compact_artifact_fast_path():
    plan = compile_evidence_plan("ai-sast-remediation", "selection-plan")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 3
    assert plan.max_calls == 4
    assert [step.id for step in plan.steps] == [
        "known-ai-sast-finding",
        "project-by-git",
        "ai-sast-selection",
        "selected-ai-sast-finding",
    ]
    routes = {route.id: route for route in plan.routes}
    assert routes["known-finding"].expected_calls == 1
    assert routes["repository"].expected_calls == 3
    inventory = plan.steps[2]
    detail = plan.steps[3]
    assert inventory.depends_on == ("project-by-git",)
    assert inventory.result_delivery == "runtime.large_result_artifact_required"
    assert "--list-all" in inventory.template
    assert "spec.finding_metadata" not in inventory.fields
    assert "spec.explanation" not in inventory.fields
    assert detail.depends_on == ("ai-sast-selection",)
    assert next(
        binding for binding in detail.inputs if binding.name == "finding_uuid"
    ).source == "steps.ai-sast-selection.selected_finding_uuid"
    assert routes["repository"].required_outputs[-1] == (
        "steps.selected-ai-sast-finding.finding_uuid"
    )
    assert "not a universal call ceiling" in " ".join(plan.stop_conditions)


def test_compiled_sca_selection_plan_narrows_summary_before_one_candidate_detail():
    plan = compile_evidence_plan("sca-remediation", "selection-plan")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 3
    assert plan.max_calls == 4
    assert [step.id for step in plan.steps] == [
        "project-by-git",
        "version-upgrade-summary",
        "version-upgrade-detail",
    ]
    summary = plan.steps[1]
    detail = plan.steps[2]
    assert "spec.upgrade_info.is_best==true" in summary.template
    assert "--sort-path spec.upgrade_info.score --sort-order descending" in summary.template
    assert "--page-size 1" in summary.template
    assert "--list-all" not in summary.template
    assert "spec.upgrade_info.vuln_finding_info" not in summary.fields
    assert "spec.upgrade_info.is_best" in summary.fields
    assert "spec.upgrade_info.score" in summary.fields
    assert detail.depends_on == (summary.id,)
    assert next(binding for binding in detail.inputs if binding.name == "candidate_uuid").source == (
        "steps.version-upgrade-summary.best_candidate_uuid"
    )
    assert plan.routes[0].required_outputs[-1] == (
        "steps.version-upgrade-detail.selected_candidate"
    )


def test_compiled_remediation_planning_plan_uses_three_read_fast_path_with_scoped_fallback():
    plan = compile_evidence_plan("remediation-planning", "selection-plan")

    assert validate_evidence_plan(plan) == []
    assert plan.attribution_agent_id == "remediation-planning"
    assert plan.expected_calls == 3
    assert plan.max_calls == 5
    assert [step.id for step in plan.steps] == [
        "project-by-git",
        "version-upgrade-summary",
        "version-upgrade-detail",
        "selected-finding-detail",
    ]
    assert all(
        step.template.startswith(
            "endorctl agent api --agent-id remediation-planning"
        )
        for step in plan.steps
    )
    assert "--page-size 1" in plan.steps[1].template
    assert "--list-all" not in plan.steps[1].template
    assert plan.steps[2].depends_on == ("version-upgrade-summary",)
    detail_outputs = {output.name: output for output in plan.steps[2].outputs}
    assert detail_outputs["from_package_version_uuid"].path == (
        "$.objects[0].spec.upgrade_info.from_pkg_version_uuid"
    )
    assert detail_outputs["fixed_finding_evidence"].path == (
        "$.objects[0].spec.upgrade_info.vuln_finding_info.fixed_findings"
    )
    fallback = plan.steps[3]
    assert fallback.condition == (
        "steps.version-upgrade-detail.fixed_finding_evidence_missing"
    )
    assert fallback.depends_on == ("version-upgrade-detail",)
    assert 'spec.target_uuid=="<FROM_PACKAGE_VERSION_UUID>"' in fallback.template
    assert "--page-size 25" in fallback.template
    assert "--list-all" not in fallback.template
    assert next(
        binding for binding in fallback.inputs if binding.name == "from_package_version_uuid"
    ).source == "steps.version-upgrade-detail.from_package_version_uuid"
    assert plan.profile_contract_digest == compile_profile_contract(
        "remediation-planning", "selection-plan"
    ).contract_digest


def test_compiled_oss_upgrade_plan_selects_exact_compact_candidate_before_detail():
    plan = compile_evidence_plan("oss-upgrade-investigator", "evidence-check")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 3
    assert plan.max_calls == 4
    assert [step.id for step in plan.steps] == [
        "project-by-git",
        "version-upgrade-by-package-exact",
        "version-upgrade-detail-compact",
    ]
    candidates = plan.steps[1]
    detail = plan.steps[2]
    assert candidates.depends_on == ("project-by-git",)
    assert "--page-size 1" in candidates.template
    assert "--list-all" not in candidates.template
    assert 'spec.upgrade_info.from_version=="<CURRENT_VERSION>"' in candidates.template
    assert 'spec.upgrade_info.to_version=="<TARGET_VERSION>"' in candidates.template
    assert "spec.upgrade_info" not in candidates.fields
    assert "spec.upgrade_info.total_findings_fixed" in candidates.fields
    assert "spec.upgrade_info.total_findings_introduced" in candidates.fields
    assert detail.depends_on == (candidates.id,)
    assert next(binding for binding in detail.inputs if binding.name == "candidate_uuid").source == (
        "steps.version-upgrade-by-package-exact.candidate_uuid"
    )
    assert "spec.upgrade_info" not in detail.fields
    assert "spec.upgrade_info.conflicts_map" in detail.fields
    assert plan.routes[0].required_outputs[-1] == (
        "steps.version-upgrade-detail-compact.selected_candidate"
    )
    assert all(
        step.template.startswith(
            "endorctl agent api --agent-id oss-upgrade-investigator"
        )
        for step in plan.steps
    )


def test_compiled_findings_browser_plan_routes_tag_or_filter_to_one_bounded_page():
    plan = compile_evidence_plan("findings-browser", "browse")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 1
    assert plan.max_calls == 1
    assert {route.condition for route in plan.routes} == {
        "runtime.finding_tag_present",
        "runtime.finding_tag_absent",
    }
    assert {step.id for step in plan.steps} == {
        "findings-by-tag",
        "filtered-findings",
    }
    assert all("--page-size 25" in step.template for step in plan.steps)
    assert all("--list-all" not in step.template for step in plan.steps)
    assert all(step.max_calls == 1 for step in plan.steps)
    assert plan.inventory_default_mode == "bounded"
    assert plan.exhaustive_supported is True
    assert plan.exhaustive_max_pages == 20
    assert all(
        step.template.startswith("endorctl agent api --agent-id findings-browser")
        for step in plan.steps
    )


def test_compiled_findings_browser_plan_defaults_to_child_namespace_coverage():
    plan = compile_evidence_plan("findings-browser", "browse")

    assert plan.namespace_traversal_default == "include_children"
    assert plan.exact_namespace_opt_out is True
    assert "namespace_traversal" in plan.cache_identity
    assert all("--traverse" in step.template for step in plan.steps)
    assert plan.to_dict()["scope"]["namespace_traversal_default"] == "include_children"


def test_evidence_plan_rejects_missing_default_child_namespace_traversal():
    plan = compile_evidence_plan("findings-browser", "browse")
    first, *remaining = plan.steps
    invalid = replace(
        plan,
        steps=(replace(first, template=first.template.replace(" --traverse", "")), *remaining),
    )

    assert any(
        "default child namespace coverage requires --traverse" in error
        for error in validate_evidence_plan(invalid)
    )


def test_compiled_troubleshooting_plan_routes_one_classified_issue_lane():
    plan = compile_evidence_plan("troubleshooting", "diagnose")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 1
    assert plan.max_calls == 3
    assert {route.condition for route in plan.routes} == {
        "runtime.issue_lane_equals_project",
        "runtime.issue_lane_equals_scan_result",
        "runtime.issue_lane_equals_finding",
        "runtime.issue_lane_equals_missing_findings",
    }
    assert {step.id for step in plan.steps} == {
        "project-by-git",
        "scan-result-by-uuid",
        "finding-by-uuid",
        "project-by-git-for-finding-count",
        "active-main-finding-count",
    }
    assert all(
        step.template.startswith("endorctl agent api --agent-id troubleshooting")
        for step in plan.steps
    )

    routes = {route.id: route for route in plan.routes}
    assert routes["missing-findings"].expected_calls == 2
    assert routes["missing-findings"].max_calls == 3
    steps = {step.id: step for step in plan.steps}
    count_step = steps["active-main-finding-count"]
    assert count_step.depends_on == ("project-by-git-for-finding-count",)
    assert "context.type==CONTEXT_TYPE_MAIN" in count_step.template
    assert 'spec.project_uuid=="<PROJECT_UUID>"' in count_step.template
    assert "spec.dismiss==false" in count_step.template
    assert "--count" in count_step.template
    assert "--list-all" not in count_step.template
    assert "spec.dismiss==null" not in count_step.template

    scan_step = steps["scan-result-by-uuid"]
    assert scan_step.max_calls == 1
    assert "| jq" in scan_step.template
    assert ".spec.components_executed" in scan_step.template
    assert ".spec.provisioning_result" in scan_step.template
    assert ".[0:3]" in scan_step.template


def test_evidence_plan_validator_rejects_untyped_multi_lane_routes():
    plan = compile_evidence_plan("troubleshooting", "diagnose")
    first, *remaining = plan.routes
    invalid = replace(
        plan,
        routes=(replace(first, condition="runtime.issue_lane_with_project"), *remaining),
    )

    assert any(
        "typed equality selectors" in error for error in validate_evidence_plan(invalid)
    )


def test_mcp_only_vulnerability_explainer_does_not_publish_a_synthetic_cli_plan():
    assert compile_evidence_plans("vulnerability-explainer") == ()


def test_compiled_dependency_review_plan_parallelizes_local_scope_and_one_aggregate():
    plan = compile_evidence_plan("dependency-reviewer", "repository-review")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 2
    assert plan.max_calls == 3
    assert [step.id for step in plan.steps] == [
        "local-manifest-inventory",
        "project-by-git",
        "finding-package-severity-groups",
    ]
    local, project, findings = plan.steps
    assert local.operation == "local_read"
    assert local.max_calls == 0
    assert local.inputs == ()
    assert local.concurrency_group == project.concurrency_group == "scope"
    assert findings.depends_on == ("project-by-git",)
    assert "--group-aggregation-paths" in findings.template
    assert "--list-all" not in findings.template


def test_compiled_configuration_plan_selects_adaptive_scan_readiness_route():
    plan = compile_evidence_plan("configuration-automation", "evidence-check")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 3
    assert plan.max_calls == 4
    assert [route.id for route in plan.routes] == [
        "single-repo",
        "selected-repositories",
        "fleet",
    ]
    assert {route.condition for route in plan.routes} == {
        "runtime.scope_mode_equals_single_repo",
        "runtime.scope_mode_equals_selected_repositories",
        "runtime.scope_mode_equals_fleet",
    }
    local, coverage = plan.steps[:2]
    assert local.operation == "local_read"
    assert local.max_calls == 0
    assert coverage.operation == "list"
    assert coverage.max_calls == 2
    assert "--page-size 2" in coverage.template
    assert "--list-all" not in coverage.template
    assert ".list.objects" in coverage.template
    complete_steps = [step for step in plan.steps if "--list-all" in step.template]
    assert len(complete_steps) == 8
    assert all(
        step.result_delivery == "runtime.large_result_artifact_required"
        for step in complete_steps
    )
    assert all(step.selection_condition.startswith("runtime.") for step in complete_steps)
    assert {step.route_id for step in complete_steps} == {
        "single-repo",
        "selected-repositories",
        "fleet",
    }


def test_compiled_malware_plan_routes_exact_findings_before_package_fanout():
    plan = compile_evidence_plan("malware-responder", "exposure-check")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 2
    assert plan.max_calls == 6
    assert [step.id for step in plan.steps] == [
        "finding-by-uuid",
        "dependency-metadata-by-uuid",
        "project-by-uuid",
        "tenant-package-version-exact",
        "tenant-malware-findings",
    ]
    assert [
        (route.id, route.condition, route.expected_calls, route.max_calls)
        for route in plan.routes
    ] == [
        ("known-finding", "runtime.finding_uuid_present", 2, 3),
        ("package-intelligence", "runtime.finding_uuid_absent", 2, 6),
    ]
    exact_finding, dependency, project, packages, findings = plan.steps
    assert exact_finding.operation == "get"
    assert exact_finding.max_calls == 1
    assert "get -r Finding" in exact_finding.template
    assert "--traverse" not in exact_finding.template
    assert dependency.operation == "get"
    assert dependency.max_calls == 1
    assert dependency.depends_on == ("finding-by-uuid",)
    assert "get -r DependencyMetadata" in dependency.template
    assert "spec.dependency_data" in dependency.template
    assert "spec.importer_data" in dependency.template
    assert project.operation == "get"
    assert project.condition == "steps.finding-by-uuid.repository_identity_missing"
    assert project.max_calls == 1
    assert "get -r Project" in project.template
    assert packages.fanout is not None
    assert packages.fanout.source == "runtime.affected_packages"
    assert packages.fanout.item_name == "affected_package"
    assert packages.fanout.max_items == 5
    assert packages.max_calls == 5
    assert "--page-size 100" in packages.template
    assert "--list-all" not in packages.template
    assert findings.fanout is None
    assert findings.max_calls == 1
    assert "--page-size 50" in findings.template
    assert "--list-all" not in findings.template


def test_compiled_cicd_posture_plan_uses_adaptive_subset_and_namespace_routes():
    plan = compile_evidence_plan("cicd-posture", "posture")

    assert validate_evidence_plan(plan) == []
    assert plan.expected_calls == 3
    assert plan.max_calls == 4
    assert [step.id for step in plan.steps] == [
        "subset-local-ci-inventory",
        "subset-project-by-git",
        "subset-cicd-posture-findings",
        "subset-endor-repository-config",
        "namespace-local-ci-inventory",
        "namespace-cicd-posture-findings",
        "namespace-endor-repository-config",
    ]
    assert [
        (route.id, route.condition, route.expected_calls, route.max_calls)
        for route in plan.routes
    ] == [
        ("repository-subset", "runtime.repo_full_name_present", 3, 4),
        ("namespace-wide", "runtime.repo_full_name_absent", 2, 2),
    ]
    project = plan.steps[1]
    subset_findings = plan.steps[2]
    subset_repository = plan.steps[3]
    namespace_findings = plan.steps[5]
    namespace_repository = plan.steps[6]
    assert project.max_calls == 2
    assert project.retry.when == "parent_namespace_empty_result"
    assert project.retry.append_args == ("--traverse",)
    assert 'spec.git.full_name=="<owner/repo>"' in project.template
    assert subset_findings.depends_on == ("subset-project-by-git",)
    assert 'spec.project_uuid=="<PROJECT_UUID>"' in subset_findings.template
    assert subset_repository.depends_on == ("subset-project-by-git",)
    assert 'meta.parent_uuid=="<PROJECT_UUID>"' in subset_repository.template
    assert "--page-size 100" in namespace_findings.template
    assert "--page-size 50" in namespace_repository.template
    assert all("--list-all" not in step.template for step in plan.steps)
    assert all(
        "--traverse" not in step.template
        for step in plan.steps
    )


def test_every_agent_api_default_profile_has_one_bounded_evidence_plan():
    plans = {
        agent_id: compile_evidence_plan(agent_id, profile_id)
        for agent_id, profile_id in DEFAULT_EVIDENCE_PLAN_PROFILES.items()
    }

    assert len(plans) == 10
    assert compile_evidence_plans("vulnerability-explainer") == ()
    assert all(validate_evidence_plan(plan) == [] for plan in plans.values())
    assert all(
        "--list-all" not in step.template
        or (
            step.selection_condition.startswith("runtime.")
            and step.result_delivery == "runtime.large_result_artifact_required"
        )
        for plan in plans.values()
        for step in plan.steps
    )
    assert all(
        plan.profile_contract_digest
        == compile_profile_contract(agent_id, plan.profile_id).contract_digest
        for agent_id, plan in plans.items()
    )


def test_row_list_steps_declare_explicit_page_and_request_limits():
    plans = (
        compile_evidence_plan(agent_id, profile_id)
        for agent_id, profile_id in DEFAULT_EVIDENCE_PLAN_PROFILES.items()
    )
    row_lists = [
        step
        for plan in plans
        for step in plan.steps
        if step.operation == "list"
        and "--list-all" not in step.template
        and "--count" not in step.template
        and "--group-aggregation-paths" not in step.template
    ]

    assert row_lists
    assert all(step.pagination is not None for step in row_lists)
    assert all(step.pagination.page_size >= 1 for step in row_lists if step.pagination)
    assert all(step.pagination.max_pages >= 1 for step in row_lists if step.pagination)
    namespace_repository = next(
        step
        for step in row_lists
        if step.id == "namespace-endor-repository-config"
    )
    assert namespace_repository.pagination.page_size == 50
    assert namespace_repository.pagination.max_pages == 1
    assert namespace_repository.max_calls == 1
    subset_repository = next(
        step for step in row_lists if step.id == "subset-endor-repository-config"
    )
    assert subset_repository.pagination.page_size == 2
    assert subset_repository.pagination.max_pages == 1
    assert subset_repository.max_calls == 1


def test_evidence_plan_validator_rejects_hidden_unbounded_pagination():
    plan = compile_evidence_plan("findings-browser", "browse")
    first, *remaining = plan.steps
    invalid = replace(
        plan,
        steps=(replace(first, template=f"{first.template} --list-all"), *remaining),
    )

    assert any("--list-all" in error for error in validate_evidence_plan(invalid))


def test_compile_evidence_plans_returns_only_source_declared_profiles():
    assert [
        plan.profile_id for plan in compile_evidence_plans("sca-remediation")
    ] == ["evidence-check", "selection-plan"]
    assert [
        plan.profile_id for plan in compile_evidence_plans("dependency-reviewer")
    ] == ["repository-review"]


def test_evidence_plan_validator_rejects_invalid_dag():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    first, second, third = plan.steps
    invalid = replace(
        plan,
        steps=(
            replace(first, depends_on=(third.id,)),
            second,
            replace(third, depends_on=(first.id,)),
        ),
    )

    assert any("dependency cycle" in error for error in validate_evidence_plan(invalid))


def test_evidence_plan_validator_rejects_missing_binding():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    first, second, third = plan.steps
    project_binding = next(binding for binding in second.inputs if binding.name == "project_uuid")
    invalid = replace(
        plan,
        steps=(
            first,
            replace(
                second,
                inputs=tuple(
                    replace(project_binding, source="steps.project-by-git.missing_output")
                    if binding is project_binding
                    else binding
                    for binding in second.inputs
                ),
            ),
            third,
        ),
    )

    assert any("unknown output" in error for error in validate_evidence_plan(invalid))


def test_evidence_plan_validator_rejects_unbounded_retry():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    first, *remaining = plan.steps
    invalid = replace(
        plan,
        steps=(
            replace(first, retry=replace(first.retry, eligible=True, max_attempts=0)),
            *remaining,
        ),
    )

    assert any("bounded max_attempts" in error for error in validate_evidence_plan(invalid))


def test_evidence_plan_validator_rejects_non_allowlisted_retry_fallback():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    first, *remaining = plan.steps
    invalid = replace(
        plan,
        steps=(
            replace(first, retry=replace(first.retry, append_args=("--list-all",))),
            *remaining,
        ),
    )

    assert any("fallback arguments" in error for error in validate_evidence_plan(invalid))


def test_evidence_plan_validator_rejects_unsafe_operation():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    first, *remaining = plan.steps
    invalid = replace(plan, steps=(replace(first, operation="create"), *remaining))

    assert any("unsafe operation" in error for error in validate_evidence_plan(invalid))


def test_evidence_plan_validator_rejects_wrong_agent_attribution():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    invalid = replace(plan, attribution_agent_id="ai-sast-remediation")

    assert any("attribution agent_id" in error for error in validate_evidence_plan(invalid))
    assert any(
        "expected agent_id" in error
        for error in validate_evidence_plan(plan, expected_agent_id="ai-sast-remediation")
    )


def test_evidence_plan_validator_rejects_missing_namespace_contract():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    invalid = replace(plan, namespace_required=False)

    assert any("namespace is required" in error for error in validate_evidence_plan(invalid))


def test_evidence_plan_validator_rejects_budget_overrun():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    invalid = replace(plan, max_calls=2)

    assert any("call budget" in error for error in validate_evidence_plan(invalid))


def test_evidence_plan_validator_isolates_prompt_fallback_from_host_execution():
    plan = compile_evidence_plan("sca-remediation", "evidence-check")
    invalid = replace(plan, execution_mode="host_adapter")

    assert any("prompt recipes" in error for error in validate_evidence_plan(invalid))

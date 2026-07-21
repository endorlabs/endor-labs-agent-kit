from __future__ import annotations

from dataclasses import replace
import json

from endor_agent_kit.evidence_plans import (
    EVIDENCE_PLAN_SCHEMA_VERSION,
    compile_evidence_plan,
    compile_evidence_plans,
    validate_evidence_plan,
)


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
    plan = compile_evidence_plan("ai-sast-triage", "evidence-check")

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
    assert detail.depends_on == (summary.id,)
    assert next(binding for binding in detail.inputs if binding.name == "candidate_uuid").source == (
        "steps.version-upgrade-summary.best_candidate_uuid"
    )
    assert plan.routes[0].required_outputs[-1] == (
        "steps.version-upgrade-detail.selected_candidate"
    )


def test_compile_evidence_plans_returns_only_source_declared_profiles():
    assert [
        plan.profile_id for plan in compile_evidence_plans("sca-remediation")
    ] == ["evidence-check", "selection-plan"]
    assert compile_evidence_plans("dependency-decision-helper") == ()


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
    invalid = replace(plan, attribution_agent_id="ai-sast-triage")

    assert any("attribution agent_id" in error for error in validate_evidence_plan(invalid))
    assert any(
        "expected agent_id" in error
        for error in validate_evidence_plan(plan, expected_agent_id="ai-sast-triage")
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

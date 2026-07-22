from __future__ import annotations

from endor_agent_kit.profile_contracts import (
    compile_profile_contract,
    profile_contract_from_dict,
    validate_profile_output_payload,
)
import pytest


def test_compiled_sca_evidence_profile_contract_is_projected_and_source_bound():
    contract = compile_profile_contract("sca-remediation", "evidence-check")
    payload = contract.to_dict()

    expected_fields = (
        "summary",
        "project_resolution",
        "evidence_queries",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    )
    assert contract.agent_id == "sca-remediation"
    assert contract.profile_id == "evidence-check"
    assert contract.output_fields == expected_fields
    assert contract.required_fields == expected_fields
    assert contract.gate_validator_id == "sca-remediation.read-only-profile"
    assert contract.gate_validator_version == "1"
    assert contract.policy_pack_support is True
    assert payload["provider_neutral_schema"]["required"] == list(expected_fields)
    assert tuple(payload["provider_neutral_schema"]["properties"]) == expected_fields
    for digest_name in ("source_digest", "recipe_digest", "knowledge_pack_digest", "contract_digest"):
        assert len(payload[digest_name]) == 64
        int(payload[digest_name], 16)


def test_compiled_sca_selection_plan_contract_omits_non_selection_workflow_state():
    contract = compile_profile_contract("sca-remediation", "selection-plan")

    expected_fields = (
        "summary",
        "project_resolution",
        "evidence_queries",
        "selected_remediation",
        "uia_evidence",
        "risk_decision",
        "change_requests",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    )
    assert contract.projection_applied is True
    assert contract.output_fields == expected_fields
    assert contract.required_fields == expected_fields
    assert tuple(contract.provider_neutral_schema["properties"]) == expected_fields
    assert len(contract.provider_neutral_schema_json) < 10_000
    for omitted_field in (
        "remediation_candidates",
        "patch_plan",
        "validation",
        "tickets",
        "task_state",
    ):
        assert omitted_field not in contract.provider_neutral_schema["properties"]


def test_read_only_profile_validator_accepts_projected_evidence_and_rejects_mutation_fields():
    payload = {
        "summary": "Evidence is unavailable.",
        "project_resolution": None,
        "evidence_queries": [],
        "data_gaps": ["Endor Project evidence was unavailable."],
        "policy_context": {},
        "policy_evaluations": [],
    }

    assert validate_profile_output_payload("sca-remediation", "evidence-check", payload) == []

    errors = validate_profile_output_payload(
        "sca-remediation",
        "evidence-check",
        {**payload, "selected_remediation": {"name": "not allowed"}},
    )
    assert errors == ["selected_remediation: not allowed by task profile evidence-check"]


def test_compiled_ai_sast_evidence_profile_uses_compact_domain_verdicts():
    contract = compile_profile_contract("ai-sast-remediation", "evidence-check")
    verdicts = contract.provider_neutral_schema["properties"]["verdicts"]
    verdict = verdicts["items"]
    expected_fields = {
        "finding_uuid",
        "finding_name",
        "classification",
        "severity",
        "cwe",
        "source_location",
        "file_path",
        "source_sha",
        "source_ref",
        "source_ref_provenance",
        "sast_rule_id",
        "data_flow_summary",
        "scorecard_summary",
        "exploit_reproduction_summary",
        "remediation_guidance_summary",
        "priority_rationale",
        "result_count",
        "evidence",
    }

    assert verdict["additionalProperties"] is False
    assert set(verdict["properties"]) == expected_fields
    assert set(verdict["required"]) == expected_fields
    assert verdict["properties"]["result_count"]["type"] == ["integer", "null"]
    assert set(verdict["properties"]["evidence"]["items"]["properties"]) == {
        "label",
        "location",
        "url",
        "snippet",
        "note",
    }
    assert "branch_name" not in verdict["properties"]
    assert "malware_name" not in verdict["properties"]


def test_remediation_planning_profiles_expose_only_their_decision_gate_outputs():
    expected = {
        "resolve-scope": (
            "summary",
            "project_resolution",
            "evidence_queries",
            "data_gaps",
            "policy_context",
            "policy_evaluations",
        ),
        "evidence-check": (
            "summary",
            "project_resolution",
            "evidence_queries",
            "remediation_options",
            "data_gaps",
            "policy_context",
            "policy_evaluations",
        ),
        "selection-plan": (
            "summary",
            "project_resolution",
            "evidence_queries",
            "remediation_options",
            "selected_remediation",
            "data_gaps",
            "policy_context",
            "policy_evaluations",
        ),
    }

    contracts = {
        profile_id: compile_profile_contract("remediation-planning", profile_id)
        for profile_id in expected
    }

    assert {
        profile_id: contract.output_fields
        for profile_id, contract in contracts.items()
    } == expected
    assert all(contract.projection_applied for contract in contracts.values())
    assert (
        len(contracts["resolve-scope"].provider_neutral_schema_json)
        < len(contracts["selection-plan"].provider_neutral_schema_json)
    )


def test_remaining_default_profiles_have_explicit_output_boundaries():
    expected = {
        ("cicd-posture", "posture"): (
            "posture_verdict",
            "summary",
            "scope",
            "raw_counts",
            "dimension_scores",
            "score_validation",
            "critical_overrides",
            "endor_findings",
            "github_evidence",
            "local_ci_evidence",
            "recommended_actions",
            "evidence_queries",
            "data_gaps",
            "policy_context",
            "policy_evaluations",
        ),
        ("findings-browser", "browse"): (
            "findings_verdict",
            "summary",
            "applied_filters",
            "severity_summary",
            "finding_results",
            "pagination",
            "evidence_queries",
            "data_gaps",
            "policy_context",
            "policy_evaluations",
        ),
        ("malware-responder", "exposure-check"): (
            "incident_verdict",
            "summary",
            "affected_package_set",
            "tenant_scope",
            "tenant_exposure_summary",
            "impacted_projects",
            "possible_exposures",
            "evidence_queries",
            "data_gaps",
            "policy_context",
            "policy_evaluations",
        ),
        ("oss-upgrade-investigator", "evidence-check"): (
            "upgrade_recommendation",
            "risk_delta",
            "reasons",
            "breaking_change_notes",
            "next_checks",
            "summary",
            "evidence_queries",
            "data_gaps",
            "selected_upgrade",
            "findings_fixed",
            "findings_introduced",
            "cia_status",
            "policy_context",
            "policy_evaluations",
        ),
        ("vulnerability-explainer", "explain"): (
            "action",
            "severity",
            "exploitability",
            "remediation",
            "summary",
            "evidence_queries",
            "data_gaps",
            "policy_context",
            "policy_evaluations",
        ),
    }

    contracts = {
        identity: compile_profile_contract(*identity) for identity in expected
    }

    assert {
        identity: contract.output_fields for identity, contract in contracts.items()
    } == expected
    assert all(contract.projection_applied for contract in contracts.values())


def test_serialized_profile_contract_round_trips_and_rejects_tampering():
    compiled = compile_profile_contract("dependency-reviewer", "repository-review")

    restored = profile_contract_from_dict(
        compiled.to_dict(),
        expected_agent_id="dependency-reviewer",
        expected_profile_id="repository-review",
    )

    assert restored == compiled

    tampered = compiled.to_dict()
    tampered["output_fields"].append("selected_remediation")
    with pytest.raises(ValueError, match="output_fields do not match schema properties"):
        profile_contract_from_dict(tampered)

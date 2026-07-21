from __future__ import annotations

import json
from pathlib import Path
import re

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.recipe import load_recipe
from endor_agent_kit.structured_output_contracts import (
    STRUCTURED_OUTPUT_CONTRACTS,
    json_schema_for_agent,
    normalize_structured_output_payload,
    required_fields_for,
    strict_transport_schema_for_agent,
    validate_structured_output_payload,
)


def test_structured_output_contracts_match_recipe_outputs():
    recipe_contracts = {}
    for recipe_path in sorted((repo_root() / "source" / "agents").glob("*/recipe.yaml")):
        recipe = load_recipe(recipe_path)
        recipe_contracts[recipe.id] = tuple(
            (field.name, field.kind, field.required)
            for field in recipe.outputs
        )

    registry_contracts = {
        agent_id: tuple((field.name, field.kind, field.required) for field in fields)
        for agent_id, fields in STRUCTURED_OUTPUT_CONTRACTS.items()
    }

    assert registry_contracts == recipe_contracts


def test_required_fields_for_preserves_recipe_order():
    assert required_fields_for("dependency-reviewer") == (
        "profile",
        "summary",
        "evidence_queries",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    )


def test_profile_output_contract_reduces_required_fields_without_weakening_evidence_gaps():
    fields = (
        "onboarding_verdict",
        "evidence_queries",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    )
    schema = json_schema_for_agent("configuration-automation", fields)
    payload = {
        "onboarding_verdict": "INSUFFICIENT_DATA",
        "evidence_queries": [],
        "data_gaps": ["unavailable: project evidence not returned"],
        "policy_context": {},
        "policy_evaluations": [],
    }

    assert required_fields_for("configuration-automation", fields) == fields
    assert tuple(schema["required"]) == fields
    assert tuple(schema["properties"]) == fields
    assert validate_structured_output_payload("configuration-automation", payload, fields) == []


def test_all_structured_contracts_require_evidence_queries():
    for agent_id in STRUCTURED_OUTPUT_CONTRACTS:
        assert "evidence_queries" in required_fields_for(agent_id)


def test_json_schema_for_agent_preserves_required_fields_and_shapes():
    schema = json_schema_for_agent("sca-remediation")
    strict_schema = strict_transport_schema_for_agent("sca-remediation")

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == list(required_fields_for("sca-remediation"))
    assert strict_schema["required"] == list(strict_schema["properties"])
    assert schema["properties"]["evidence_queries"]["type"] == "array"
    assert schema["properties"]["policy_context"]["type"] == ["object", "null"]
    assert schema["properties"]["policy_evaluations"]["type"] == "array"
    evidence_query = schema["properties"]["evidence_queries"]["items"]
    assert evidence_query["additionalProperties"] is False
    assert evidence_query["required"] == [
        "name",
        "resource",
        "source",
        "status",
        "query_template_id",
        "filter_summary",
        "field_mask_summary",
        "result_count",
        "reason",
    ]
    assert schema["properties"]["project_resolution"]["type"] == ["object", "null"]


def test_task_state_is_strict_nullable_and_legacy_omittable() -> None:
    for agent_id in ("sca-remediation", "ai-sast-remediation"):
        logical_schema = json_schema_for_agent(agent_id)
        schema = strict_transport_schema_for_agent(agent_id)
        task_state = schema["properties"]["task_state"]

        assert "task_state" not in logical_schema["required"]
        assert "task_state" in logical_schema["properties"]
        assert schema["required"] == list(schema["properties"])
        assert task_state["type"] == ["object", "null"]
        assert task_state["additionalProperties"] is False
        assert set(task_state["required"]) == set(task_state["properties"])
        assert task_state["properties"]["schema_version"]["const"] == "1"

        legacy_payload = {
            field: _placeholder_value(kind)
            for field, kind in _field_kinds(agent_id).items()
        }
        legacy_payload["evidence_queries"] = []
        legacy_payload["data_gaps"] = ["Runtime task state was not supplied."]

        assert validate_structured_output_payload(agent_id, legacy_payload) == []
        strict_payload = {**legacy_payload, "task_state": None}
        assert "task_state" not in normalize_structured_output_payload(agent_id, strict_payload)
        assert validate_structured_output_payload(agent_id, strict_payload) == []


def test_ai_sast_patch_schema_is_complete_strict_and_embeds_change_impact() -> None:
    schema = json_schema_for_agent("ai-sast-remediation")
    assert "change_impact" not in schema["properties"]
    patch = schema["properties"]["patches"]["items"]
    expected = {
        "finding_uuid",
        "source_sha",
        "patch_diff",
        "patch_reason",
        "patch_summary",
        "reason",
        "remediation_guidance_used",
        "remediation_guidance_rejected",
        "exploit_reproduction_used",
        "exploit_context",
        "file_path",
        "branch_name",
        "branch",
        "proposed_branch",
        "patch_confidence",
        "confidence",
        "changed_files",
        "modified_files",
        "files",
        "sibling_files_referenced",
        "validation_plan",
        "change_impact",
    }

    assert patch["additionalProperties"] is False
    assert set(patch["required"]) == expected == set(patch["properties"])
    assert patch["properties"]["patch_confidence"]["type"] == ["integer", "null"]
    assert patch["properties"]["validation_plan"]["items"]["required"] == [
        "command",
        "status",
        "purpose",
    ]
    impact = patch["properties"]["change_impact"]
    assert impact["type"] == ["object", "null"]
    assert impact["additionalProperties"] is False
    assert set(impact["required"]) == set(impact["properties"])
    assert impact["properties"]["patch_digest"]["pattern"] == "^[0-9a-f]{64}$"
    assert impact["properties"]["status"]["enum"] == [
        "verified",
        "blocked",
        "unavailable",
        "not_applicable",
        None,
    ]


def test_ai_sast_legacy_patch_aliases_normalize_without_dropping_aliases() -> None:
    payload = {
        "patches": [
            {
                "branch": "remediation/ai-sast/example",
                "files": ["src/example.py"],
                "confidence": 84,
                "patch_summary": "Validate the input.",
                "exploit_context": "Unsafe input reaches the sink.",
            }
        ]
    }

    normalized = normalize_structured_output_payload("ai-sast-remediation", payload)
    patch = normalized["patches"][0]

    assert patch["branch_name"] == patch["branch"]
    assert patch["changed_files"] == patch["files"]
    assert patch["patch_confidence"] == patch["confidence"]
    assert patch["patch_reason"] == patch["patch_summary"]
    assert patch["exploit_reproduction_used"] == patch["exploit_context"]


def test_materialized_ai_sast_patch_fixture_passes_strict_item_schema() -> None:
    fixture = json.loads(
        (repo_root() / "tests" / "fixtures" / "ai-sast-strict-patch.json").read_text(encoding="utf-8")
    )
    schema = json_schema_for_agent("ai-sast-remediation")["properties"]["patches"]["items"]

    _assert_value_matches_schema(fixture, schema)


def test_json_schema_for_configuration_automation_and_troubleshooter_nested_outputs():
    cicd_schema = json_schema_for_agent("cicd-posture")
    assert cicd_schema["properties"]["posture_verdict"]["type"] == "string"
    assert "raw_counts" in cicd_schema["properties"]
    assert "score_validation" in cicd_schema["properties"]

    probe_schema = json_schema_for_agent("configuration-automation")
    report_scope = probe_schema["properties"]["report_scope"]
    executive_report = probe_schema["properties"]["executive_report"]

    assert "mode" in report_scope["properties"]
    assert "namespace_provenance" in report_scope["properties"]
    assert "endor_namespace" in report_scope["properties"]
    assert "monitored_branch_policy" in report_scope["properties"]
    assert "top_counts" in executive_report["properties"]
    healthy_row = probe_schema["properties"]["onboarded_healthy_repositories"]["items"]
    assert "endor_project_uuid" in healthy_row["properties"]
    assert "github_default_branch" in healthy_row["properties"]
    assert "endor_monitored_branch" in healthy_row["properties"]

    troubleshooter_schema = json_schema_for_agent("troubleshooting")
    executive_summary = troubleshooter_schema["properties"]["executive_summary"]
    intake_classification = troubleshooter_schema["properties"]["intake_classification"]
    support_packet = troubleshooter_schema["properties"]["support_escalation_packet"]

    assert "issue_title" in executive_summary["properties"]
    assert "confirmation_required" in executive_summary["properties"]
    assert "issue_lanes" in intake_classification["properties"]
    assert "redactions_applied" in support_packet["properties"]


def test_json_schema_for_all_agents_is_codex_strict_object_compatible():
    for agent_id in STRUCTURED_OUTPUT_CONTRACTS:
        schema = strict_transport_schema_for_agent(agent_id)
        _assert_strict_objects(schema)


def test_json_schema_cli_prints_agent_schema(capsys):
    status = main(["structured-output-schema", "--agent", "sca-remediation"])
    output = capsys.readouterr().out

    assert status == 0
    assert '"title": "Endor Agent Kit sca-remediation final output"' in output
    assert '"evidence_queries"' in output


def test_json_schema_cli_prints_profile_projected_logical_schema(capsys):
    status = main(
        [
            "structured-output-schema",
            "--agent",
            "sca-remediation",
            "--task-profile",
            "evidence-check",
        ]
    )
    schema = json.loads(capsys.readouterr().out)

    expected = (
        "summary",
        "project_resolution",
        "evidence_queries",
        "data_gaps",
        "policy_context",
        "policy_evaluations",
    )
    assert status == 0
    assert tuple(schema["properties"]) == expected
    assert tuple(schema["required"]) == expected
    assert "task_state" not in schema["properties"]


def test_policy_evaluation_schema_includes_invalid_fact_provenance():
    schema = json_schema_for_agent("sca-remediation")

    evaluation = schema["properties"]["policy_evaluations"]["items"]

    assert "invalid_facts" in evaluation["properties"]


def test_structured_output_contract_rejects_missing_required_fields():
    errors = validate_structured_output_payload(
        "vulnerability-explainer",
        {
            "action": "explain",
            "severity": "high",
            "exploitability": [],
            "summary": "Explained with missing remediation and data gaps.",
        },
    )

    assert "remediation: required" in errors
    assert "data_gaps: required" in errors


def test_structured_output_contract_rejects_wrong_value_shapes():
    errors = validate_structured_output_payload(
        "dependency-reviewer",
        {
            "profile": "package-risk",
            "risk_posture": "elevated",
            "findings": "none",
            "strengths": [],
            "next_checks": [],
            "summary": "Malformed findings.",
            "data_gaps": "none",
        },
    )

    assert "findings: must be an array" in errors
    assert "data_gaps: must be an array" in errors


def test_structured_output_contract_allows_null_object_when_gap_is_recorded():
    errors = validate_structured_output_payload(
        "remediation-planning",
        {
            "summary": "No selected remediation without evidence.",
            "project_resolution": {"status": "unresolved"},
            "evidence_queries": [],
            "remediation_options": [],
            "selected_remediation": None,
            "data_gaps": ["Missing Finding and VersionUpgrade evidence."],
            "policy_context": {"status": "not_configured"},
            "policy_evaluations": [],
        },
    )

    assert errors == []


def test_structured_output_contract_requires_data_gap_when_evidence_queries_empty():
    errors = validate_structured_output_payload(
        "configuration-automation",
        {
            field: _placeholder_value(kind)
            for field, kind in _field_kinds("configuration-automation").items()
        },
    )

    assert "data_gaps: required when evidence_queries is empty" in errors


def test_structured_output_contract_rejects_incomplete_evidence_query_rows():
    errors = validate_structured_output_payload(
        "vulnerability-explainer",
        {
            "action": "MONITOR",
            "severity": "high",
            "exploitability": [],
            "remediation": [],
            "summary": "Missing normalized evidence query fields.",
            "evidence_queries": [{"resource": "Vulnerability", "status": "succeeded", "query": "raw query"}],
            "data_gaps": [],
            "policy_context": {"status": "not_configured"},
            "policy_evaluations": [],
        },
    )

    assert "evidence_queries[0].query: unsupported ledger field" in errors
    assert "evidence_queries[0].name: required" in errors
    assert "evidence_queries[0].source: required" in errors


def _field_kinds(agent_id: str) -> dict[str, str]:
    return {
        field.name: field.kind
        for field in STRUCTURED_OUTPUT_CONTRACTS[agent_id]
        if field.required
    }


def _placeholder_value(kind: str):
    if kind.startswith("list["):
        return []
    if kind == "object":
        return {}
    if kind == "integer":
        return 0
    return "fixture"


def _assert_strict_objects(schema):
    schema_type = schema.get("type")
    type_values = schema_type if isinstance(schema_type, list) else [schema_type]
    if "object" in type_values:
        assert schema.get("additionalProperties") is False
        assert set(schema.get("required", [])) == set(schema.get("properties", {}))
    if "array" in type_values and isinstance(schema.get("items"), dict):
        _assert_strict_objects(schema["items"])
    for child in schema.get("properties", {}).values():
        if isinstance(child, dict):
            _assert_strict_objects(child)


def _assert_value_matches_schema(value, schema):
    raw_types = schema.get("type")
    types = raw_types if isinstance(raw_types, list) else [raw_types]
    if value is None:
        assert "null" in types
        return
    if "object" in types:
        assert isinstance(value, dict)
        assert set(value) == set(schema["required"])
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(schema["properties"])
        for key, child in schema["properties"].items():
            _assert_value_matches_schema(value[key], child)
    elif "array" in types:
        assert isinstance(value, list)
        for item in value:
            _assert_value_matches_schema(item, schema["items"])
    elif "string" in types:
        assert isinstance(value, str)
    elif "integer" in types:
        assert isinstance(value, int) and not isinstance(value, bool)
    elif "boolean" in types:
        assert isinstance(value, bool)
    if "const" in schema:
        assert value == schema["const"]
    if "enum" in schema:
        assert value in schema["enum"]
    if isinstance(value, str) and "pattern" in schema:
        assert re.fullmatch(schema["pattern"], value)

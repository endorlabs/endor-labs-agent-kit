from __future__ import annotations

from pathlib import Path

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.recipe import load_recipe
from endor_agent_kit.structured_output_contracts import (
    STRUCTURED_OUTPUT_CONTRACTS,
    json_schema_for_agent,
    required_fields_for,
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
    assert required_fields_for("dependency-decision-helper") == (
        "verdict",
        "conditions",
        "alternatives",
        "summary",
        "data_gaps",
    )


def test_json_schema_for_agent_preserves_required_fields_and_shapes():
    schema = json_schema_for_agent("sca-remediation")

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True
    assert schema["required"] == list(required_fields_for("sca-remediation"))
    assert schema["properties"]["evidence_queries"]["type"] == "array"
    assert schema["properties"]["project_resolution"]["type"] == ["object", "null"]


def test_json_schema_cli_prints_agent_schema(capsys):
    status = main(["structured-output-schema", "--agent", "sca-remediation"])
    output = capsys.readouterr().out

    assert status == 0
    assert '"title": "Endor Agent Kit sca-remediation final output"' in output
    assert '"evidence_queries"' in output


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
        "package-risk-summary",
        {
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
        "remediation-planner",
        {
            "summary": "No selected remediation without evidence.",
            "project_resolution": {"status": "unresolved"},
            "evidence_queries": [],
            "remediation_options": [],
            "selected_remediation": None,
            "data_gaps": ["Missing Finding and VersionUpgrade evidence."],
        },
    )

    assert errors == []


def test_structured_output_contract_requires_data_gap_when_evidence_queries_empty():
    errors = validate_structured_output_payload(
        "probe-droid",
        {
            field: _placeholder_value(kind)
            for field, kind in _field_kinds("probe-droid").items()
        },
    )

    assert "data_gaps: required when evidence_queries is empty" in errors


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

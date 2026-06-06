"""Structured output contracts for generated Endor agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StructuredOutputField:
    """One declared structured output field for an agent."""

    name: str
    kind: str
    required: bool = True


STRUCTURED_OUTPUT_CONTRACTS: dict[str, tuple[StructuredOutputField, ...]] = {
    "ai-sast-triage": (
        StructuredOutputField("summary", "string"),
        StructuredOutputField("project_resolution", "object"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("verdicts", "list[object]"),
        StructuredOutputField("patches", "list[object]"),
        StructuredOutputField("change_requests", "list[object]"),
        StructuredOutputField("approvals", "list[object]"),
        StructuredOutputField("exception_policies", "list[object]"),
        StructuredOutputField("tickets", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "dependency-decision-helper": (
        StructuredOutputField("verdict", "enum"),
        StructuredOutputField("conditions", "list[string]"),
        StructuredOutputField("alternatives", "list[string]"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "endor-troubleshooter": (
        StructuredOutputField("troubleshooting_verdict", "enum"),
        StructuredOutputField("executive_summary", "object"),
        StructuredOutputField("intake_classification", "object"),
        StructuredOutputField("issue_lanes", "list[object]"),
        StructuredOutputField("affected_resources", "list[object]"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("evidence_summary", "object"),
        StructuredOutputField("root_cause_hypotheses", "list[object]"),
        StructuredOutputField("recommended_actions", "list[object]"),
        StructuredOutputField("validation_plan", "list[object]"),
        StructuredOutputField("support_escalation_packet", "object"),
        StructuredOutputField("data_gaps", "list[string]"),
        StructuredOutputField("future_action_contracts", "list[object]"),
        StructuredOutputField("future_scope", "list[string]"),
    ),
    "package-risk-summary": (
        StructuredOutputField("risk_posture", "enum"),
        StructuredOutputField("findings", "list[string]"),
        StructuredOutputField("strengths", "list[string]"),
        StructuredOutputField("next_checks", "list[string]"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "probe-droid": (
        StructuredOutputField("onboarding_verdict", "enum"),
        StructuredOutputField("executive_report", "object"),
        StructuredOutputField("report_scope", "object"),
        StructuredOutputField("coverage_summary", "object"),
        StructuredOutputField("github_inventory_summary", "object"),
        StructuredOutputField("github_app_coverage", "object"),
        StructuredOutputField("not_onboarded_repositories", "list[object]"),
        StructuredOutputField("onboarded_repositories_with_gaps", "list[object]"),
        StructuredOutputField("onboarded_healthy_repositories", "list[object]"),
        StructuredOutputField("ambiguous_matches", "list[object]"),
        StructuredOutputField("excluded_repositories", "list[object]"),
        StructuredOutputField("recommended_actions", "list[object]"),
        StructuredOutputField("confirmed_org_wide_actions", "list[object]"),
        StructuredOutputField("sampled_prescription_hypotheses", "list[object]"),
        StructuredOutputField("requires_full_inventory_validation", "list[object]"),
        StructuredOutputField("validation_plan", "list[object]"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
        StructuredOutputField("future_scope", "list[string]"),
    ),
    "remediation-planner": (
        StructuredOutputField("summary", "string"),
        StructuredOutputField("project_resolution", "object"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("remediation_options", "list[object]"),
        StructuredOutputField("selected_remediation", "object"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "repository-dependency-reviewer": (
        StructuredOutputField("risk_posture", "enum"),
        StructuredOutputField("manifests", "list[object]"),
        StructuredOutputField("dependencies_reviewed", "list[object]"),
        StructuredOutputField("findings", "list[object]"),
        StructuredOutputField("recommended_actions", "list[string]"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "sca-remediation": (
        StructuredOutputField("summary", "string"),
        StructuredOutputField("remediation_candidates", "list[object]"),
        StructuredOutputField("project_resolution", "object"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("selected_remediation", "object"),
        StructuredOutputField("uia_evidence", "list[object]"),
        StructuredOutputField("risk_decision", "object"),
        StructuredOutputField("patch_plan", "list[object]"),
        StructuredOutputField("validation", "list[object]"),
        StructuredOutputField("change_requests", "list[object]"),
        StructuredOutputField("tickets", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "upgrade-impact-analysis": (
        StructuredOutputField("upgrade_recommendation", "enum"),
        StructuredOutputField("risk_delta", "enum"),
        StructuredOutputField("reasons", "list[string]"),
        StructuredOutputField("breaking_change_notes", "list[string]"),
        StructuredOutputField("next_checks", "list[string]"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
        StructuredOutputField("upgrade_candidates", "list[object]", required=False),
        StructuredOutputField("selected_upgrade", "object", required=False),
        StructuredOutputField("findings_fixed", "integer", required=False),
        StructuredOutputField("findings_introduced", "integer", required=False),
        StructuredOutputField("cia_status", "string", required=False),
        StructuredOutputField("breaking_changes", "list[string]", required=False),
        StructuredOutputField("manifest_files", "list[string]", required=False),
        StructuredOutputField("dependency_delta", "object", required=False),
        StructuredOutputField("fixed_cves", "list[string]", required=False),
        StructuredOutputField("endor_patch", "string", required=False),
        StructuredOutputField("score_explanation", "string", required=False),
    ),
    "vulnerability-explainer": (
        StructuredOutputField("action", "enum"),
        StructuredOutputField("severity", "string"),
        StructuredOutputField("exploitability", "list[string]"),
        StructuredOutputField("remediation", "list[string]"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
}


def known_structured_agent_ids() -> tuple[str, ...]:
    """Return agent ids with structured output contracts."""

    return tuple(sorted(STRUCTURED_OUTPUT_CONTRACTS))


def required_fields_for(agent_id: str) -> tuple[str, ...]:
    """Return required top-level output fields for an agent."""

    return tuple(field.name for field in STRUCTURED_OUTPUT_CONTRACTS.get(agent_id, ()) if field.required)


def json_schema_for_agent(agent_id: str) -> dict[str, Any]:
    """Return a JSON Schema for the agent's final structured output."""

    contract = STRUCTURED_OUTPUT_CONTRACTS.get(agent_id)
    if not contract:
        raise ValueError(f"unknown structured output contract: {agent_id}")
    properties = {
        field.name: _json_schema_for_field(field)
        for field in contract
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Endor Agent Kit {agent_id} final output",
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def validate_structured_output_payload(agent_id: str, payload: dict[str, Any]) -> list[str]:
    """Validate top-level field presence and basic JSON value shapes."""

    contract = STRUCTURED_OUTPUT_CONTRACTS.get(agent_id)
    if not contract:
        return []
    errors: list[str] = []
    for field in contract:
        if field.name not in payload:
            if field.required:
                errors.append(f"{field.name}: required")
            continue
        errors.extend(_kind_errors(field, payload[field.name]))
    errors.extend(_evidence_query_ledger_errors(payload))
    errors.extend(_evidence_gap_contract_errors(contract, payload))
    return errors


def _json_schema_for_field(field: StructuredOutputField) -> dict[str, Any]:
    nullable = not field.required or field.kind == "object"
    if field.name in FIELD_SCHEMA_OVERRIDES:
        return _with_nullable(FIELD_SCHEMA_OVERRIDES[field.name](), nullable=nullable)
    return _json_schema_for_kind(field.kind, nullable=nullable)


def _json_schema_for_kind(kind: str, *, nullable: bool = False) -> dict[str, Any]:
    if kind.startswith("list["):
        item_kind = kind.removeprefix("list[").removesuffix("]")
        schema: dict[str, Any] = {
            "type": "array",
            "items": _json_schema_for_array_item_kind(item_kind),
        }
        return _with_nullable(schema, nullable=nullable)
    if kind == "object":
        return _with_nullable(_generic_object_schema(), nullable=nullable)
    if kind == "integer":
        return _with_nullable({"type": "integer"}, nullable=nullable)
    if kind in {"string", "enum"}:
        return _with_nullable({"type": "string"}, nullable=nullable)
    return {}


def _json_schema_for_array_item_kind(kind: str) -> dict[str, Any]:
    if kind == "object":
        return _generic_object_schema()
    if kind in {"string", "enum"}:
        return {"type": "string"}
    if kind == "integer":
        return {"type": "integer"}
    return {}


def _with_nullable(schema: dict[str, Any], *, nullable: bool) -> dict[str, Any]:
    if not nullable:
        return schema
    result = dict(schema)
    schema_type = result.get("type")
    if isinstance(schema_type, str):
        result["type"] = [schema_type, "null"]
    return result


def _strict_object_schema(properties: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _nullable_string() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _nullable_integer() -> dict[str, Any]:
    return {"type": ["integer", "null"]}


def _nullable_boolean() -> dict[str, Any]:
    return {"type": ["boolean", "null"]}


def _nullable_object() -> dict[str, Any]:
    return _with_nullable(_generic_object_schema(), nullable=True)


def _nullable_string_array() -> dict[str, Any]:
    return {
        "type": ["array", "null"],
        "items": {"type": "string"},
    }


def _nullable_object_array() -> dict[str, Any]:
    return {
        "type": ["array", "null"],
        "items": _generic_object_schema(),
    }


def _generic_object_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "id": _nullable_string(),
            "uuid": _nullable_string(),
            "name": _nullable_string(),
            "title": _nullable_string(),
            "status": _nullable_string(),
            "summary": _nullable_string(),
            "description": _nullable_string(),
            "source": _nullable_string(),
            "reason": _nullable_string(),
            "url": _nullable_string(),
            "resource": _nullable_string(),
            "resource_type": _nullable_string(),
            "action": _nullable_string(),
            "validation": _nullable_string(),
            "confirmation_required": _nullable_boolean(),
            "count": _nullable_integer(),
            "result_count": _nullable_integer(),
            "project_uuid": _nullable_string(),
            "namespace": _nullable_string(),
            "namespace_provenance": _nullable_string(),
            "repo_full_name": _nullable_string(),
            "normalized_repo_full_name": _nullable_string(),
            "repo_url": _nullable_string(),
            "default_branch": _nullable_string(),
            "selected_branch": _nullable_string(),
            "monitored_branch": _nullable_string(),
            "package": _nullable_string(),
            "package_name": _nullable_string(),
            "ecosystem": _nullable_string(),
            "version": _nullable_string(),
            "from_version": _nullable_string(),
            "to_version": _nullable_string(),
            "finding_uuid": _nullable_string(),
            "version_upgrade_uuid": _nullable_string(),
            "uia_uuid": _nullable_string(),
            "severity": _nullable_string(),
            "level": _nullable_string(),
            "risk": _nullable_string(),
            "upgrade_risk": _nullable_string(),
            "cia_status": _nullable_string(),
            "findings_fixed": _nullable_integer(),
            "findings_introduced": _nullable_integer(),
            "path": _nullable_string(),
            "file": _nullable_string(),
            "line": _nullable_integer(),
            "branch_name": _nullable_string(),
            "proposed_branch": _nullable_string(),
            "base_branch": _nullable_string(),
            "notes": _nullable_string_array(),
            "data_gaps": _nullable_string_array(),
            "evidence": _nullable_string_array(),
            "next_steps": _nullable_string_array(),
        }
    )


def _project_resolution_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "project_uuid": _nullable_string(),
            "namespace": _nullable_string(),
            "namespace_provenance": _nullable_string(),
            "repo_full_name": _nullable_string(),
            "repo_url": _nullable_string(),
            "normalized_repo_full_name": _nullable_string(),
            "default_branch": _nullable_string(),
            "selected_branch": _nullable_string(),
            "monitored_branch": _nullable_string(),
            "branch_provenance": _nullable_string(),
            "traverse_attempted": _nullable_boolean(),
            "traverse_result": _nullable_string(),
            "attempted_selectors": _nullable_string_array(),
        }
    )


def _report_scope_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "project_uuid": _nullable_string(),
            "namespace": _nullable_string(),
            "namespace_provenance": _nullable_string(),
            "repo_full_name": _nullable_string(),
            "repo_url": _nullable_string(),
            "normalized_repo_full_name": _nullable_string(),
            "default_branch": _nullable_string(),
            "selected_branch": _nullable_string(),
            "monitored_branch": _nullable_string(),
            "branch_provenance": _nullable_string(),
            "traverse_attempted": _nullable_boolean(),
            "traverse_result": _nullable_string(),
            "attempted_selectors": _nullable_string_array(),
            "github_org": _nullable_string(),
            "repositories_requested": _nullable_string_array(),
            "mode": _nullable_string(),
            "monitored_branch_policy": _nullable_string(),
            "sampling_mode": _nullable_string(),
            "sample_size": _nullable_integer(),
            "sample_seed": _nullable_string(),
            "sampling_basis": _nullable_string(),
            "coverage_limitations": _nullable_string_array(),
            "v1_exclusions": _nullable_string_array(),
        }
    )


def _executive_summary_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "issue_title": _nullable_string(),
            "impact": _nullable_string(),
            "likely_owner": _nullable_string(),
            "confidence": _nullable_string(),
            "next_best_action": _nullable_string(),
            "confirmation_required": _nullable_boolean(),
        }
    )


def _intake_classification_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "issue_lanes": _nullable_string_array(),
            "affected_product_area": _nullable_string(),
            "affected_ecosystem": _nullable_string(),
            "affected_integration_type": _nullable_string(),
            "resource_selectors_used": _nullable_string_array(),
        }
    )


def _support_escalation_packet_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "include": _nullable_string_array(),
            "redactions_applied": _nullable_string_array(),
            "reason_to_escalate": _nullable_string(),
        }
    )


def _executive_report_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "verdict": _nullable_string(),
            "headline": _nullable_string(),
            "top_counts": _nullable_object(),
            "top_blockers": _nullable_string_array(),
            "top_actions": _nullable_object_array(),
            "drill_down_sections": _nullable_string_array(),
        }
    )


def _coverage_summary_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "github_repositories_in_scope": _nullable_integer(),
            "github_repositories_sampled": _nullable_integer(),
            "endor_projects_matched": _nullable_integer(),
            "repositories_not_onboarded": _nullable_integer(),
            "repositories_with_dependency_resolution_gaps": _nullable_integer(),
            "repositories_with_reachability_gaps": _nullable_integer(),
            "repositories_with_github_app_gaps": _nullable_integer(),
            "repositories_healthy": _nullable_integer(),
            "repositories_ambiguous": _nullable_integer(),
            "excluded_repositories": _nullable_integer(),
            "top_repeated_blockers": _nullable_string_array(),
        }
    )


def _github_inventory_summary_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "source": _nullable_string(),
            "pagination_complete": _nullable_boolean(),
            "inventory_limit": _nullable_integer(),
            "archived_count": _nullable_integer(),
            "inactive_count": _nullable_integer(),
            "manifest_families_seen": _nullable_string_array(),
            "data_gaps": _nullable_string_array(),
        }
    )


def _github_app_coverage_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "selected_repo_count": _nullable_integer(),
            "selected_project_uuids": _nullable_string_array(),
            "selected_repositories": _nullable_string_array(),
            "repositories_not_selected": _nullable_string_array(),
            "selection_mapping_gaps": _nullable_string_array(),
            "scanner_status": _nullable_string(),
            "sync_errors": _nullable_string_array(),
            "evidence": _nullable_object_array(),
        }
    )


def _selected_remediation_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "package": _nullable_string(),
            "from_version": _nullable_string(),
            "to_version": _nullable_string(),
            "branch_name": _nullable_string(),
            "project_uuid": _nullable_string(),
            "namespace": _nullable_string(),
            "namespace_provenance": _nullable_string(),
            "uia_uuid": _nullable_string(),
            "version_upgrade_uuid": _nullable_string(),
            "upgrade_risk": _nullable_string(),
            "risk": _nullable_string(),
            "cia_status": _nullable_string(),
            "cia": _nullable_string(),
            "findings_fixed": _nullable_integer(),
            "findings_introduced": _nullable_integer(),
            "manifests": _nullable_string_array(),
            "affected_manifests": _nullable_string_array(),
        }
    )


def _risk_decision_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "summary": _nullable_string(),
            "reason": _nullable_string(),
            "source_usage_summary": _nullable_string(),
            "validation_requirements": _nullable_string_array(),
        }
    )


def _evidence_queries_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "name": _nullable_string(),
                "resource": _nullable_string(),
                "source": _nullable_string(),
                "status": _nullable_string(),
                "query_template_id": _nullable_string(),
                "filter_summary": _nullable_string(),
                "field_mask_summary": _nullable_string(),
                "result_count": _nullable_integer(),
                "reason": _nullable_string(),
            }
        ),
    }


def _uia_evidence_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "resource": _nullable_string(),
                "resource_type": _nullable_string(),
                "uuid": _nullable_string(),
                "uia_uuid": _nullable_string(),
                "version_upgrade_uuid": _nullable_string(),
                "upgrade_risk": _nullable_string(),
                "cia_status": _nullable_string(),
                "findings_fixed": _nullable_integer(),
                "total_findings_fixed": _nullable_integer(),
                "findings_introduced": _nullable_integer(),
                "total_findings_introduced": _nullable_integer(),
                "fixed_findings": _nullable_string_array(),
                "sample_fixed_findings": _nullable_string_array(),
                "score_explanation": _nullable_string(),
                "breaking_changes": _nullable_string_array(),
            }
        ),
    }


def _remediation_candidates_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "package": _nullable_string(),
                "from_version": _nullable_string(),
                "to_version": _nullable_string(),
                "uia_uuid": _nullable_string(),
                "version_upgrade_uuid": _nullable_string(),
                "upgrade_risk": _nullable_string(),
                "cia_status": _nullable_string(),
                "findings_fixed": _nullable_integer(),
                "findings_introduced": _nullable_integer(),
                "reason": _nullable_string(),
            }
        ),
    }


def _patch_plan_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "package": _nullable_string(),
                "from_version": _nullable_string(),
                "to_version": _nullable_string(),
                "manifest": _nullable_string(),
                "branch_name": _nullable_string(),
                "change_type": _nullable_string(),
                "status": _nullable_string(),
                "reason": _nullable_string(),
            }
        ),
    }


def _validation_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "command": _nullable_string(),
                "status": _nullable_string(),
                "reason": _nullable_string(),
                "output": _nullable_string(),
            }
        ),
    }


def _change_requests_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "status": _nullable_string(),
                "base_branch": _nullable_string(),
                "proposed_branch": _nullable_string(),
                "title": _nullable_string(),
                "body": _nullable_string(),
                "url": _nullable_string(),
                "reason": _nullable_string(),
            }
        ),
    }


def _tickets_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "status": _nullable_string(),
                "title": _nullable_string(),
                "body": _nullable_string(),
                "url": _nullable_string(),
                "reason": _nullable_string(),
            }
        ),
    }


FIELD_SCHEMA_OVERRIDES = {
    "executive_report": _executive_report_schema,
    "executive_summary": _executive_summary_schema,
    "intake_classification": _intake_classification_schema,
    "coverage_summary": _coverage_summary_schema,
    "github_inventory_summary": _github_inventory_summary_schema,
    "github_app_coverage": _github_app_coverage_schema,
    "support_escalation_packet": _support_escalation_packet_schema,
    "project_resolution": _project_resolution_schema,
    "report_scope": _report_scope_schema,
    "selected_remediation": _selected_remediation_schema,
    "selected_upgrade": _selected_remediation_schema,
    "dependency_delta": _generic_object_schema,
    "risk_decision": _risk_decision_schema,
    "evidence_queries": _evidence_queries_schema,
    "uia_evidence": _uia_evidence_schema,
    "remediation_candidates": _remediation_candidates_schema,
    "remediation_options": _remediation_candidates_schema,
    "upgrade_candidates": _remediation_candidates_schema,
    "patch_plan": _patch_plan_schema,
    "validation": _validation_schema,
    "validation_plan": _validation_schema,
    "change_requests": _change_requests_schema,
    "tickets": _tickets_schema,
}


def _kind_errors(field: StructuredOutputField, value: Any) -> list[str]:
    if field.kind.startswith("list["):
        if not isinstance(value, list):
            return [f"{field.name}: must be an array"]
        return []
    if field.kind == "object":
        if value is not None and not isinstance(value, dict):
            return [f"{field.name}: must be an object or null"]
        return []
    if field.kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return [f"{field.name}: must be an integer"]
        return []
    if field.kind in {"string", "enum"}:
        if not isinstance(value, str):
            return [f"{field.name}: must be a string"]
        return []
    return []


def _evidence_gap_contract_errors(
    contract: tuple[StructuredOutputField, ...],
    payload: dict[str, Any],
) -> list[str]:
    required = {field.name for field in contract if field.required}
    if "evidence_queries" not in required:
        return []
    evidence_queries = payload.get("evidence_queries")
    data_gaps = payload.get("data_gaps")
    if isinstance(evidence_queries, list) and isinstance(data_gaps, list):
        if not evidence_queries and not data_gaps:
            return ["data_gaps: required when evidence_queries is empty"]
        if not evidence_queries and _claims_current_evidence(payload):
            return ["evidence_queries: required when current Endor or repository evidence is claimed"]
    return []


EVIDENCE_QUERY_LEDGER_FIELDS = (
    "name",
    "resource",
    "source",
    "status",
    "query_template_id",
    "filter_summary",
    "field_mask_summary",
    "result_count",
    "reason",
)

EVIDENCE_QUERY_REQUIRED_TEXT_FIELDS = ("name", "resource", "source", "status")
EVIDENCE_QUERY_GAP_STATUSES = (
    "blocked",
    "error",
    "failed",
    "lookup_unavailable",
    "no_results",
    "unavailable",
)


def _evidence_query_ledger_errors(payload: dict[str, Any]) -> list[str]:
    evidence_queries = payload.get("evidence_queries")
    if not isinstance(evidence_queries, list):
        return []
    data_gaps = _string_list(payload.get("data_gaps"))
    errors: list[str] = []
    for index, item in enumerate(evidence_queries):
        if not isinstance(item, dict):
            errors.append(f"evidence_queries[{index}]: must be an object")
            continue
        for field in item:
            if field not in EVIDENCE_QUERY_LEDGER_FIELDS:
                errors.append(f"evidence_queries[{index}].{field}: unsupported ledger field")
        for field in EVIDENCE_QUERY_LEDGER_FIELDS:
            if field not in item:
                errors.append(f"evidence_queries[{index}].{field}: required")
        for field in EVIDENCE_QUERY_REQUIRED_TEXT_FIELDS:
            if field in item and not _text(item.get(field)):
                errors.append(f"evidence_queries[{index}].{field}: must be a non-empty string")
        for field in EVIDENCE_QUERY_LEDGER_FIELDS:
            if field == "result_count" or field not in item or item[field] is None:
                continue
            if not isinstance(item[field], str):
                errors.append(f"evidence_queries[{index}].{field}: must be a string or null")
        if "result_count" in item and item["result_count"] is not None:
            if isinstance(item["result_count"], bool) or not isinstance(item["result_count"], int):
                errors.append(f"evidence_queries[{index}].result_count: must be an integer or null")
        status = _text(item.get("status")).lower()
        if any(marker in status for marker in EVIDENCE_QUERY_GAP_STATUSES):
            if not _text(item.get("reason")) and not data_gaps:
                errors.append(f"evidence_queries[{index}].reason: required for unavailable or failed evidence")
    return errors


def _claims_current_evidence(payload: dict[str, Any]) -> bool:
    for field in (
        "findings",
        "sca_findings",
        "remediation_candidates",
        "remediation_options",
        "uia_evidence",
        "version_upgrades",
        "upgrade_candidates",
        "verdicts",
        "dependencies_reviewed",
        "affected_resources",
    ):
        if isinstance(payload.get(field), list) and payload[field]:
            return True
    for field in ("project_resolution", "report_scope"):
        value = payload.get(field)
        if isinstance(value, dict):
            status = _text(value.get("status")).lower()
            if status == "resolved" and _text(value.get("project_uuid")):
                return True
    return False


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            text = " ".join(
                str(item.get(field))
                for field in ("id", "signal", "reason", "description")
                if item.get(field)
            )
            if text:
                result.append(text)
    return result


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""

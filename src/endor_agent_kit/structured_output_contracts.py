"""Structured output contracts for generated Endor agents."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class StructuredOutputField:
    """One declared structured output field for an agent."""

    name: str
    kind: str
    required: bool = True


POLICY_OUTPUT_FIELDS = (
    StructuredOutputField(
        "policy_context",
        "object",
    ),
    StructuredOutputField(
        "policy_evaluations",
        "list[object]",
    ),
)


ENUM_FIELD_VALUES: dict[tuple[str, str], tuple[str, ...]] = {
    # Must stay set-equal to workflow_output_contracts.cicd_posture VERDICT_BANDS;
    # this module is a leaf, so a lockstep test enforces the pairing instead of an import.
    ("cicd-posture", "posture_verdict"): (
        "HEALTHY",
        "NEEDS_ATTENTION",
        "HIGH_RISK",
        "CRITICAL",
        "INSUFFICIENT_DATA",
    ),
    ("configuration-automation", "onboarding_verdict"): (
        "READY_TO_ONBOARD",
        "PARTIAL_COVERAGE",
        "NOT_ONBOARDED",
        "INSUFFICIENT_DATA",
    ),
    ("dependency-reviewer", "profile"): (
        "package-decision",
        "package-risk",
        "repository-review",
    ),
    ("dependency-reviewer", "verdict"): (
        "SAFE",
        "SAFE_WITH_CONDITIONS",
        "NOT_RECOMMENDED",
        "BLOCKED",
    ),
    ("dependency-reviewer", "risk_posture"): (
        "LOW",
        "MODERATE",
        "HIGH",
        "CRITICAL",
        "UNKNOWN",
    ),
    ("findings-browser", "findings_verdict"): (
        "EXACT_FINDING_FOUND",
        "ACTIVE_FINDINGS_FOUND",
        "NO_MATCHING_FINDINGS",
        "PARTIAL_RESULTS",
        "INSUFFICIENT_DATA",
    ),
    ("malware-responder", "incident_verdict"): (
        "CONFIRMED_EXPOSURE",
        "POSSIBLE_EXPOSURE",
        "NOT_OBSERVED",
        "INSUFFICIENT_DATA",
    ),
    ("oss-upgrade-investigator", "upgrade_recommendation"): (
        "UPGRADE_NOW",
        "UPGRADE_WITH_CAUTION",
        "DEFER",
        "INSUFFICIENT_DATA",
    ),
    ("oss-upgrade-investigator", "risk_delta"): (
        "LOWER",
        "SAME",
        "HIGHER",
        "UNKNOWN",
    ),
    # PROJECT_NOT_FOUND is commanded by the zero-match rule in the troubleshooting
    # instructions even though the verdict list there omits it; both are honored here.
    ("troubleshooting", "troubleshooting_verdict"): (
        "ACTIONABLE_FIX_IDENTIFIED",
        "LIKELY_ROOT_CAUSE_IDENTIFIED",
        "PARTIAL_DIAGNOSIS",
        "PROJECT_NOT_FOUND",
        "INSUFFICIENT_DATA",
        "SUPPORT_ESCALATION_RECOMMENDED",
        "NO_ISSUE_FOUND",
    ),
    ("vulnerability-explainer", "action"): (
        "CRITICAL_ACTION_REQUIRED",
        "ACTION_RECOMMENDED",
        "MONITOR",
        "INSUFFICIENT_DATA",
    ),
}


_BASE_STRUCTURED_OUTPUT_CONTRACTS: dict[str, tuple[StructuredOutputField, ...]] = {
    "ai-sast-remediation": (
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
        StructuredOutputField("task_state", "object", required=False),
    ),
    "cicd-posture": (
        StructuredOutputField("posture_verdict", "enum"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("scope", "object"),
        StructuredOutputField("raw_counts", "object"),
        StructuredOutputField("dimension_scores", "object"),
        StructuredOutputField("score_validation", "object"),
        StructuredOutputField("critical_overrides", "list[object]"),
        StructuredOutputField("endor_findings", "list[object]"),
        StructuredOutputField("github_evidence", "list[object]"),
        StructuredOutputField("local_ci_evidence", "list[object]"),
        StructuredOutputField("recommended_actions", "list[object]"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "dependency-reviewer": (
        StructuredOutputField("profile", "enum"),
        StructuredOutputField("verdict", "enum", required=False),
        StructuredOutputField("conditions", "list[string]", required=False),
        StructuredOutputField("alternatives", "list[string]", required=False),
        StructuredOutputField("risk_posture", "enum", required=False),
        StructuredOutputField("manifests", "list[object]", required=False),
        StructuredOutputField("dependencies_reviewed", "list[object]", required=False),
        StructuredOutputField("findings", "list[object]", required=False),
        StructuredOutputField("strengths", "list[string]", required=False),
        StructuredOutputField("next_checks", "list[string]", required=False),
        StructuredOutputField("recommended_actions", "list[string]", required=False),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "troubleshooting": (
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
    "findings-browser": (
        StructuredOutputField("findings_verdict", "enum"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("applied_filters", "object"),
        StructuredOutputField("severity_summary", "object"),
        StructuredOutputField("finding_results", "list[object]"),
        StructuredOutputField("pagination", "object"),
        StructuredOutputField("recommended_next_steps", "list[object]"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "malware-responder": (
        StructuredOutputField("incident_verdict", "enum"),
        StructuredOutputField("summary", "string"),
        StructuredOutputField("incident_intake", "object"),
        StructuredOutputField("malware_intelligence", "list[object]"),
        StructuredOutputField("affected_package_set", "list[object]"),
        StructuredOutputField("tenant_scope", "object"),
        StructuredOutputField("tenant_exposure_summary", "object"),
        StructuredOutputField("impacted_projects", "list[object]"),
        StructuredOutputField("possible_exposures", "list[object]"),
        StructuredOutputField("ioc_hunting_guidance", "list[object]"),
        StructuredOutputField("remediation_guidance", "list[object]"),
        StructuredOutputField("future_action_contracts", "list[object]"),
        StructuredOutputField("references", "list[object]"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "configuration-automation": (
        StructuredOutputField("onboarding_verdict", "enum"),
        StructuredOutputField("executive_report", "object"),
        StructuredOutputField("report_scope", "object"),
        StructuredOutputField("coverage_summary", "object"),
        StructuredOutputField("github_inventory_summary", "object"),
        StructuredOutputField("github_app_coverage", "object"),
        StructuredOutputField("issue_cohorts", "list[object]"),
        StructuredOutputField("inventory_artifacts", "list[object]"),
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
    "remediation-planning": (
        StructuredOutputField("summary", "string"),
        StructuredOutputField("project_resolution", "object"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("remediation_options", "list[object]"),
        StructuredOutputField("selected_remediation", "object"),
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "sca-remediation": (
        StructuredOutputField("summary", "string"),
        StructuredOutputField("remediation_candidates", "list[object]"),
        StructuredOutputField("project_resolution", "object"),
        StructuredOutputField("execution_context", "object"),
        StructuredOutputField("evidence_queries", "list[object]"),
        StructuredOutputField("selected_remediation", "object"),
        StructuredOutputField("uia_evidence", "list[object]"),
        StructuredOutputField("risk_decision", "object"),
        StructuredOutputField("dependency_graph_audit", "object"),
        StructuredOutputField("patch_plan", "list[object]"),
        StructuredOutputField("validation", "list[object]"),
        StructuredOutputField("change_requests", "list[object]"),
        StructuredOutputField("tickets", "list[object]"),
        StructuredOutputField("data_gaps", "list[string]"),
        StructuredOutputField("task_state", "object", required=False),
    ),
    "oss-upgrade-investigator": (
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

STRUCTURED_OUTPUT_CONTRACTS: dict[str, tuple[StructuredOutputField, ...]] = {
    agent_id: fields + POLICY_OUTPUT_FIELDS
    for agent_id, fields in _BASE_STRUCTURED_OUTPUT_CONTRACTS.items()
}


def known_structured_agent_ids() -> tuple[str, ...]:
    """Return agent ids with structured output contracts."""

    return tuple(sorted(STRUCTURED_OUTPUT_CONTRACTS))


def required_fields_for(
    agent_id: str,
    output_fields: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Return required top-level output fields for an agent."""

    return tuple(field.name for field in _contract_for_output_fields(agent_id, output_fields) if field.required)


def json_schema_for_agent(
    agent_id: str,
    output_fields: tuple[str, ...] | None = None,
    *,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Return a JSON Schema for the agent's final structured output."""

    contract = _contract_for_output_fields(agent_id, output_fields)
    if not contract:
        raise ValueError(f"unknown structured output contract: {agent_id}")
    properties = {
        field.name: _json_schema_for_field(
            field,
            agent_id=agent_id,
            profile_id=profile_id,
        )
        for field in contract
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"Endor Agent Kit {agent_id} final output",
        "type": "object",
        "additionalProperties": False,
        "required": [field.name for field in contract if field.required],
        "properties": properties,
    }


def strict_transport_schema_for_agent(
    agent_id: str,
    output_fields: tuple[str, ...] | None = None,
    *,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Return a strict-host schema with every logical property present.

    Optional logical fields remain nullable, and
    :func:`normalize_structured_output_payload` converts present-null values
    back to omission before logical validation.
    """

    schema = json_schema_for_agent(
        agent_id,
        output_fields,
        profile_id=profile_id,
    )
    schema["required"] = list(schema["properties"])
    return schema


def validate_structured_output_payload(
    agent_id: str,
    payload: dict[str, Any],
    output_fields: tuple[str, ...] | None = None,
    *,
    allowed_query_template_ids: frozenset[str] | set[str] | None = None,
) -> list[str]:
    """Validate top-level field presence and basic JSON value shapes.

    ``allowed_query_template_ids`` is supplied by callers that know the
    knowledge-pack recipe inventory (see ``profile_contracts``); this module
    stays a leaf and never computes the set itself. ``None`` disables the check.
    """

    contract = _contract_for_output_fields(agent_id, output_fields)
    if not contract:
        return []
    payload = normalize_structured_output_payload(
        agent_id,
        payload,
        preserve_null_fields=output_fields or (),
    )
    errors: list[str] = []
    for field in contract:
        if field.name not in payload:
            if field.required:
                errors.append(f"{field.name}: required")
            continue
        errors.extend(_kind_errors(field, payload[field.name]))
        enum_values = ENUM_FIELD_VALUES.get((agent_id, field.name))
        if (
            enum_values is not None
            and isinstance(payload[field.name], str)
            and payload[field.name] not in enum_values
        ):
            errors.append(
                f"{field.name}: must be one of {', '.join(enum_values)}"
            )
    errors.extend(
        _evidence_query_ledger_errors(
            payload, allowed_query_template_ids=allowed_query_template_ids
        )
    )
    errors.extend(_project_scope_resolution_errors(payload))
    errors.extend(_summary_count_errors(payload))
    errors.extend(_evidence_gap_contract_errors(contract, payload))
    return errors


def _contract_for_output_fields(
    agent_id: str,
    output_fields: tuple[str, ...] | None,
) -> tuple[StructuredOutputField, ...]:
    contract = STRUCTURED_OUTPUT_CONTRACTS.get(agent_id, ())
    if output_fields is None:
        return contract
    fields_by_name = {field.name: field for field in contract}
    unknown = tuple(name for name in output_fields if name not in fields_by_name)
    if unknown:
        raise ValueError(f"profile output contract references unknown fields: {', '.join(unknown)}")
    return tuple(
        StructuredOutputField(name, fields_by_name[name].kind, required=True)
        for name in output_fields
    )


def normalize_structured_output_payload(
    agent_id: str,
    payload: dict[str, Any],
    *,
    preserve_null_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Normalize strict present-null optional keys to legacy omitted-key form."""

    normalized = dict(payload)
    preserved = set(preserve_null_fields)
    for field in STRUCTURED_OUTPUT_CONTRACTS.get(agent_id, ()):
        if (
            not field.required
            and field.name not in preserved
            and normalized.get(field.name) is None
        ):
            normalized.pop(field.name, None)
    if agent_id == "ai-sast-remediation" and isinstance(normalized.get("patches"), list):
        normalized["patches"] = [
            _normalize_ai_sast_patch(item) if isinstance(item, dict) else item
            for item in normalized["patches"]
        ]
    return normalized


def _normalize_ai_sast_patch(patch: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(patch)
    aliases = {
        "branch_name": ("branch", "proposed_branch"),
        "changed_files": ("modified_files", "files"),
        "patch_confidence": ("confidence",),
        "patch_reason": ("patch_summary", "reason"),
        "exploit_reproduction_used": ("exploit_context",),
    }
    for canonical, candidates in aliases.items():
        if normalized.get(canonical) is not None:
            continue
        for alias in candidates:
            if normalized.get(alias) is not None:
                normalized[canonical] = normalized[alias]
                break
    return normalized


def _json_schema_for_field(
    field: StructuredOutputField,
    *,
    agent_id: str,
    profile_id: str | None,
) -> dict[str, Any]:
    nullable = not field.required or field.kind == "object"
    profile_override = PROFILE_FIELD_SCHEMA_OVERRIDES.get(
        (agent_id, profile_id, field.name)
    )
    if profile_override is not None:
        return _with_nullable(profile_override(), nullable=nullable)
    agent_override = AGENT_FIELD_SCHEMA_OVERRIDES.get((agent_id, field.name))
    if agent_override is not None:
        return _with_nullable(agent_override(), nullable=nullable)
    if field.name in FIELD_SCHEMA_OVERRIDES:
        return _with_nullable(FIELD_SCHEMA_OVERRIDES[field.name](), nullable=nullable)
    enum_values = ENUM_FIELD_VALUES.get((agent_id, field.name))
    if enum_values is not None:
        return _with_nullable(
            {"type": "string", "enum": list(enum_values)},
            nullable=nullable,
        )
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
    enum_values = result.get("enum")
    if isinstance(enum_values, list) and None not in enum_values:
        result["enum"] = [*enum_values, None]
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


def _nullable_enum(values: tuple[str, ...]) -> dict[str, Any]:
    return {"type": ["string", "null"], "enum": [*values, None]}


def _required_string() -> dict[str, Any]:
    return {"type": "string", "minLength": 1}


def _nullable_object() -> dict[str, Any]:
    return _with_nullable(_generic_object_schema(), nullable=True)


def _nullable_endor_project_object() -> dict[str, Any]:
    return _with_nullable(
        _strict_object_schema(
            {
                "matched": _nullable_boolean(),
                "project_uuid": _nullable_string(),
                "project_name": _nullable_string(),
                "namespace": _nullable_string(),
                "match_method": _nullable_string(),
            }
        ),
        nullable=True,
    )


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
            "owner": _nullable_string(),
            "expected_effect": _nullable_string(),
            "validation": _nullable_string(),
            "confirmation_required": _nullable_boolean(),
            "count": _nullable_integer(),
            "result_count": _nullable_integer(),
            "project_uuid": _nullable_string(),
            "endor_project_uuid": _nullable_string(),
            "namespace": _nullable_string(),
            "endor_namespace": _nullable_string(),
            "namespace_provenance": _nullable_string(),
            "repo_full_name": _nullable_string(),
            "repository": _nullable_string(),
            "normalized_repo_full_name": _nullable_string(),
            "repo_url": _nullable_string(),
            "default_branch": _nullable_string(),
            "github_default_branch": _nullable_string(),
            "selected_branch": _nullable_string(),
            "monitored_branch": _nullable_string(),
            "endor_monitored_branch": _nullable_string(),
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
            "changed_file": _nullable_string(),
            "changed_files": _nullable_string_array(),
            "files_changed": _nullable_string_array(),
            "modified_files": _nullable_string_array(),
            "line": _nullable_integer(),
            "branch_name": _nullable_string(),
            "proposed_branch": _nullable_string(),
            "base_branch": _nullable_string(),
            "notes": _nullable_string_array(),
            "data_gaps": _nullable_string_array(),
            "evidence": _nullable_string_array(),
            "next_steps": _nullable_string_array(),
            "endor_project": _nullable_endor_project_object(),
            "aliases": _nullable_string_array(),
            "affected_versions": _nullable_string_array(),
            "version_range": _nullable_string(),
            "confidence": _nullable_string(),
            "malware_name": _nullable_string(),
            "campaign": _nullable_string(),
            "indicator": _nullable_string(),
            "type": _nullable_string(),
            "project_name": _nullable_string(),
            "manifest_path": _nullable_string(),
            "observed_version": _nullable_string(),
            "exposure_status": _nullable_string(),
            "match_type": _nullable_string(),
            "first_observed": _nullable_string(),
            "last_observed": _nullable_string(),
            "installed_at": _nullable_string(),
            "detected_at": _nullable_string(),
            "reference": _nullable_string(),
            "references": _nullable_string_array(),
            "iocs": _nullable_string_array(),
            "remediation": _nullable_string_array(),
            "mode": _nullable_string(),
            "project_scope": _nullable_string_array(),
            "ecosystems": _nullable_string_array(),
            "traverse_attempted": _nullable_boolean(),
            "include_child_namespaces": _nullable_boolean(),
            "confirmed_exposure_count": _nullable_integer(),
            "possible_exposure_count": _nullable_integer(),
            "not_observed_count": _nullable_integer(),
            "unknown_due_to_scope_gap_count": _nullable_integer(),
        }
    )


def _project_resolution_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "project_uuid": _nullable_string(),
            "namespace": _nullable_string(),
            "endor_namespace": _nullable_string(),
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


def _execution_context_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "mode": _nullable_enum(("evidence_only", "local_checkout")),
            "endor_auth": _nullable_enum(("available", "unavailable", "unknown")),
            "local_checkout": _nullable_boolean(),
            "source_provider_access": _nullable_enum(
                ("read_write", "read_only", "unavailable", "unknown")
            ),
            "local_validation": _nullable_enum(
                ("available", "unavailable", "not_attempted", "unknown")
            ),
            "limitations": _nullable_string_array(),
        }
    )


def _report_scope_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "project_uuid": _nullable_string(),
            "namespace": _nullable_string(),
            "endor_namespace": _nullable_string(),
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


def _findings_browse_applied_filters_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "namespace": _nullable_string(),
            "namespace_provenance": _nullable_string(),
            "namespace_traversal": _nullable_string(),
            "scope": _nullable_string(),
            "project_uuid": _nullable_string(),
            "repository": _nullable_string(),
            "finding_categories": _nullable_string_array(),
            "severity_levels": _nullable_string_array(),
            "status_filter": _nullable_string(),
            "package_name": _nullable_string(),
            "ecosystem": _nullable_string(),
            "dependency_scope": _nullable_string(),
            "reachability_filter": _nullable_string(),
            "cve_or_ghsa": _nullable_string(),
            "tag_filter": _nullable_string(),
            "page_size": _nullable_integer(),
            "completeness_required": _nullable_boolean(),
        }
    )


def _findings_browse_severity_summary_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "count": _nullable_integer(),
            "critical": _nullable_integer(),
            "high": _nullable_integer(),
            "medium": _nullable_integer(),
            "low": _nullable_integer(),
            "info": _nullable_integer(),
            "status": _nullable_string(),
            "summary": _nullable_string(),
        }
    )


def _findings_browse_results_schema() -> dict[str, Any]:
    row = _strict_object_schema(
        {
            "uuid": _nullable_string(),
            "finding_uuid": _nullable_string(),
            "name": _nullable_string(),
            "title": _nullable_string(),
            "level": _nullable_string(),
            "severity": _nullable_string(),
            "project_uuid": _nullable_string(),
            "categories": _nullable_string_array(),
            "finding_categories": _nullable_string_array(),
            "finding_tags": _nullable_string_array(),
            "target_dependency_package_name": _nullable_string(),
            "package_name": _nullable_string(),
            "ecosystem": _nullable_string(),
            "version": _nullable_string(),
            "aliases": _nullable_string_array(),
            "summary": _nullable_string(),
        }
    )
    return {"type": "array", "items": row}


def _findings_browse_pagination_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "page_size": _nullable_integer(),
            "result_count": _nullable_integer(),
            "returned_count": _nullable_integer(),
            "has_next_page": _nullable_boolean(),
            "next_page_token": _nullable_string(),
            "next_page_id": _nullable_string(),
            "status": _nullable_string(),
            "summary": _nullable_string(),
            "complete": _nullable_boolean(),
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
            "finding_instances_fixed": _nullable_integer(),
            "unique_advisories_fixed": _nullable_integer(),
            "fixed_finding_uuids": _nullable_string_array(),
            "findings_introduced": _nullable_integer(),
            "manifests": _nullable_string_array(),
            "affected_manifests": _nullable_string_array(),
            "selection_blocked": _nullable_boolean(),
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


def _dependency_graph_audit_schema() -> dict[str, Any]:
    # Derived from the audit engine's own vocabulary so the transport schema
    # and the runtime validator can never drift apart. Imported lazily: this
    # module stays a leaf at import time, and schema builders only run inside
    # json_schema_for_agent(), after package initialization. Frozenset-backed
    # vocabularies are sorted so generated contract JSON stays deterministic.
    from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
        AUDIT_STATUSES,
        CLASSIFICATIONS,
        GRAPH_RUNTIME_KINDS,
        MAVEN_PROFILE,
        MAX_DEPENDENCY_PATH,
        MAX_EVIDENCE_ITEMS,
        MAX_MANIPULATIONS,
        MAX_VALIDATION_REQUIREMENTS,
        SEMANTIC_EFFECTS,
        SUPPORTED_PROFILES,
    )

    # `type` carries only the type-driven (Maven) vocabulary; every
    # mechanism-driven manager keeps `type` null and expresses its construct
    # through the free-string `mechanism`, whose per-manager enforcement is
    # owned by the runtime validator — strict transport schemas cannot
    # express per-manager conditionals.
    maven_types = sorted(
        MAVEN_PROFILE.native_types
        | MAVEN_PROFILE.override_types
        | MAVEN_PROFILE.removal_types
    )
    manipulation = _strict_object_schema(
        {
            "type": _nullable_enum(tuple(maven_types)),
            "coordinate": _nullable_string(),
            "classification": _nullable_enum(CLASSIFICATIONS),
            "semantic_effect": _nullable_enum(SEMANTIC_EFFECTS),
            "mechanism": _nullable_string(),
            "replacement": _nullable_string(),
            "evidence": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "maxItems": MAX_EVIDENCE_ITEMS,
            },
        }
    )
    return _strict_object_schema(
        {
            "package_manager": _nullable_enum(
                tuple(profile.name for profile in SUPPORTED_PROFILES)
            ),
            "status": _nullable_enum(AUDIT_STATUSES),
            "manifest": _nullable_string(),
            "dependency_path": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "maxItems": MAX_DEPENDENCY_PATH,
            },
            "manipulations": {
                "type": ["array", "null"],
                "items": manipulation,
                "maxItems": MAX_MANIPULATIONS,
            },
            "validation_requirements": {
                "type": ["array", "null"],
                "items": {"type": "string", "enum": sorted(GRAPH_RUNTIME_KINDS)},
                "maxItems": MAX_VALIDATION_REQUIREMENTS,
            },
        }
    )


def _evidence_queries_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "name": _nullable_string(),
                "resource": _nullable_string(),
                "source": {
                    "type": ["string", "null"],
                    "enum": [*EVIDENCE_QUERY_SOURCE_VALUES, None],
                },
                "status": {
                    "type": ["string", "null"],
                    "enum": [*EVIDENCE_QUERY_STATUS_VALUES, None],
                },
                "query_template_id": _nullable_string(),
                "filter_summary": _nullable_string(),
                "field_mask_summary": _nullable_string(),
                "result_count": _nullable_integer(),
                "list_all": _nullable_boolean(),
                "artifact": _with_nullable(
                    _strict_object_schema(
                        {
                            "artifact_ref": {"type": "string"},
                            "sha256": {"type": "string"},
                            "format": {"type": "string"},
                            "bytes": {"type": "integer"},
                            "row_count": {"type": "integer"},
                        }
                    ),
                    nullable=True,
                ),
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
                "finding_instances_fixed": _nullable_integer(),
                "unique_advisories_fixed": _nullable_integer(),
                "fixed_finding_uuids": _nullable_string_array(),
                "findings_introduced": _nullable_integer(),
                "total_findings_introduced": _nullable_integer(),
                "fixed_findings": _nullable_string_array(),
                "sample_fixed_findings": _nullable_string_array(),
                "score_explanation": _nullable_string(),
                "breaking_changes": _nullable_string_array(),
            }
        ),
    }


def _ai_sast_evidence_verdicts_schema() -> dict[str, Any]:
    evidence_item = _strict_object_schema(
        {
            "label": _nullable_string(),
            "location": _nullable_string(),
            "url": _nullable_string(),
            "snippet": _nullable_string(),
            "note": _nullable_string(),
        }
    )
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "finding_uuid": _nullable_string(),
                "finding_name": _nullable_string(),
                "classification": _nullable_string(),
                "severity": _nullable_string(),
                "cwe": _nullable_string(),
                "source_location": _nullable_string(),
                "file_path": _nullable_string(),
                "source_sha": _nullable_string(),
                "source_ref": _nullable_string(),
                "source_ref_provenance": _nullable_string(),
                "sast_rule_id": _nullable_string(),
                "data_flow_summary": _nullable_string(),
                "scorecard_summary": _nullable_string(),
                "exploit_reproduction_summary": _nullable_string(),
                "remediation_guidance_summary": _nullable_string(),
                "priority_rationale": _nullable_string(),
                "result_count": _nullable_integer(),
                "evidence": {"type": ["array", "null"], "items": evidence_item},
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


def _patch_validation_plan_schema() -> dict[str, Any]:
    return {
        "type": ["array", "null"],
        "items": _strict_object_schema(
            {
                "command": _nullable_string(),
                "status": _nullable_string(),
                "purpose": _nullable_string(),
            }
        ),
    }


def _change_impact_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "patch_digest": {
                "type": ["string", "null"],
                "pattern": "^[0-9a-f]{64}$",
            },
            "status": {
                "type": ["string", "null"],
                "enum": ["verified", "blocked", "unavailable", "not_applicable", None],
            },
            "searched_call_sites": _nullable_string_array(),
            "factories": _nullable_string_array(),
            "tests": _nullable_string_array(),
            "framework_providers": _nullable_string_array(),
            "config_keys": _nullable_string_array(),
            "validation_evidence": _nullable_string_array(),
        }
    )


def _patches_schema() -> dict[str, Any]:
    nullable_strings = (
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
    )
    nullable_arrays = (
        "changed_files",
        "modified_files",
        "files",
        "sibling_files_referenced",
    )
    properties = {name: _nullable_string() for name in nullable_strings}
    properties.update({name: _nullable_integer() for name in ("patch_confidence", "confidence")})
    properties.update({name: _nullable_string_array() for name in nullable_arrays})
    properties["validation_plan"] = _patch_validation_plan_schema()
    properties["change_impact"] = _with_nullable(_change_impact_schema(), nullable=True)
    return {
        "type": "array",
        "items": _strict_object_schema(properties),
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
                "inventory": _with_nullable(_change_request_inventory_schema(), nullable=True),
            }
        ),
    }


def _change_request_inventory_schema() -> dict[str, Any]:
    candidate = _strict_object_schema(
        {
            "author": _nullable_string(),
            "author_type": _nullable_string(),
            "branch": _nullable_string(),
            "state": _nullable_string(),
            "files": _nullable_string_array(),
            "url": _nullable_string(),
            "current_version": _nullable_string(),
            "target_version": _nullable_string(),
            "exact_duplicate": _nullable_boolean(),
        }
    )
    key = _strict_object_schema(
        {
            "repository": _nullable_string(),
            "base_branch": _nullable_string(),
            "ecosystem": _nullable_string(),
            "normalized_package": _nullable_string(),
            "manifest": _nullable_string(),
            "current_version": _nullable_string(),
            "target_version": _nullable_string(),
            "finding_set": _nullable_string_array(),
        }
    )
    reconciliation = _strict_object_schema(
        {
            "status": _nullable_string(),
            "reason": _nullable_string(),
            "selected_target_version": _nullable_string(),
            "uia_evidence_checked_at": _nullable_string(),
            "upstream_evidence_checked_at": _nullable_string(),
            "operator_choice_required": _nullable_boolean(),
        }
    )
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "lookup_method": _nullable_string(),
            "checked_at": _nullable_string(),
            "fresh_recheck": _nullable_boolean(),
            "key": _with_nullable(key, nullable=True),
            "candidates": {"type": ["array", "null"], "items": candidate},
            "reconciliation": _with_nullable(reconciliation, nullable=True),
        }
    )


def _selection_plan_change_requests_schema() -> dict[str, Any]:
    """Require one semantically complete inventory at the SCA selection gate."""

    candidate = _strict_object_schema(
        {
            "author": _required_string(),
            "author_type": _required_string(),
            "branch": _required_string(),
            "state": _required_string(),
            "files": {"type": "array", "items": {"type": "string"}},
            "url": _required_string(),
            "current_version": _nullable_string(),
            "target_version": _nullable_string(),
            "exact_duplicate": {"type": "boolean"},
        }
    )
    key = _strict_object_schema(
        {
            "repository": _required_string(),
            "base_branch": _required_string(),
            "ecosystem": _required_string(),
            "normalized_package": _required_string(),
            "manifest": _required_string(),
            "current_version": _required_string(),
            "target_version": _required_string(),
            "finding_set": {"type": "array", "items": {"type": "string"}},
        }
    )
    reconciliation = _strict_object_schema(
        {
            "status": _required_string(),
            "reason": _nullable_string(),
            "selected_target_version": _nullable_string(),
            "uia_evidence_checked_at": _nullable_string(),
            "upstream_evidence_checked_at": _nullable_string(),
            "operator_choice_required": _nullable_boolean(),
        }
    )
    inventory = _strict_object_schema(
        {
            "status": {
                "type": "string",
                "enum": [
                    "none_found",
                    "exact_duplicate",
                    "different_target",
                    "unavailable",
                ],
            },
            "lookup_method": _required_string(),
            "checked_at": _required_string(),
            "fresh_recheck": {"type": "boolean"},
            "key": key,
            "candidates": {"type": "array", "items": candidate},
            "reconciliation": reconciliation,
        }
    )
    request = _strict_object_schema(
        {
            "status": _nullable_string(),
            "base_branch": _nullable_string(),
            "proposed_branch": _nullable_string(),
            "title": _nullable_string(),
            "body": _nullable_string(),
            "url": _nullable_string(),
            "reason": _nullable_string(),
            "inventory": inventory,
        }
    )
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": 1,
        "items": request,
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


def _policy_context_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "status": _nullable_string(),
            "pack_id": _nullable_string(),
            "pack_version": _nullable_string(),
            "sha256": _nullable_string(),
            "source": _nullable_string(),
        }
    )


def _policy_evaluations_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": _strict_object_schema(
            {
                "policy_id": _nullable_string(),
                "effect": _nullable_string(),
                "decision": _nullable_string(),
                "message": _nullable_string(),
                "facts_used": _nullable_string_array(),
                "missing_facts": _nullable_string_array(),
                "invalid_facts": _nullable_string_array(),
            }
        ),
    }


def _task_state_schema() -> dict[str, Any]:
    return _strict_object_schema(
        {
            "schema_version": {"type": "string", "const": "1"},
            "run_id": _nullable_string(),
            "workflow_instance_id": _nullable_string(),
            "workflow_intent_digest": _nullable_string(),
            "phase": _nullable_string(),
            "source_profile": _nullable_string(),
            "target_profile": _nullable_string(),
            "source_phase": _nullable_string(),
            "target_phase": _nullable_string(),
            "parent_state_digest": _nullable_string(),
            "repository": _nullable_string(),
            "namespace": _nullable_string(),
            "head_fingerprint": _nullable_string(),
            "diff_fingerprint": _nullable_string(),
            "status": _nullable_string(),
            "evidence": _nullable_object(),
            "plan": _nullable_object(),
            "validation": _nullable_object_array(),
            "change_request_inventory": _nullable_object_array(),
            "external_action_ids": _nullable_string_array(),
            "data_gaps": _nullable_string_array(),
        }
    )


PROFILE_FIELD_SCHEMA_OVERRIDES = {
    (
        "ai-sast-remediation",
        "evidence-check",
        "verdicts",
    ): _ai_sast_evidence_verdicts_schema,
    (
        "sca-remediation",
        "selection-plan",
        "change_requests",
    ): _selection_plan_change_requests_schema,
    (
        "findings-browser",
        "browse",
        "applied_filters",
    ): _findings_browse_applied_filters_schema,
    (
        "findings-browser",
        "browse",
        "severity_summary",
    ): _findings_browse_severity_summary_schema,
    (
        "findings-browser",
        "browse",
        "finding_results",
    ): _findings_browse_results_schema,
    (
        "findings-browser",
        "browse",
        "pagination",
    ): _findings_browse_pagination_schema,
}


def _slim_row_array_schema(properties: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"type": "array", "items": _strict_object_schema(properties)}


def _dependency_reviewer_findings_schema() -> dict[str, Any]:
    # Taught shape: package coordinate, evidence type, severity or posture
    # effect, evidence source, and concise explanation. EPSS/KEV slots land
    # here in the intelligence-lanes PR.
    return _slim_row_array_schema(
        {
            "package_name": _nullable_string(),
            "ecosystem": _nullable_string(),
            "version": _nullable_string(),
            "finding_uuid": _nullable_string(),
            "evidence_type": _nullable_string(),
            "severity": _nullable_string(),
            "posture_effect": _nullable_string(),
            "source": _nullable_string(),
            "explanation": _nullable_string(),
        }
    )


def _dependency_reviewer_manifests_schema() -> dict[str, Any]:
    return _slim_row_array_schema(
        {
            "path": _nullable_string(),
            "ecosystem": _nullable_string(),
            "package_manager": _nullable_string(),
            "tier": _nullable_string(),
            "direct_dependency_count": _nullable_integer(),
            "notes": _nullable_string(),
        }
    )


def _dependency_reviewer_dependencies_schema() -> dict[str, Any]:
    return _slim_row_array_schema(
        {
            "package_name": _nullable_string(),
            "ecosystem": _nullable_string(),
            "version": _nullable_string(),
            "manifest_path": _nullable_string(),
            "direct": _nullable_boolean(),
            "scope": _nullable_string(),
            "notes": _nullable_string(),
        }
    )


def _malware_affected_package_schema() -> dict[str, Any]:
    # Mirrors the affected_package_set row template in the instructions.
    return _slim_row_array_schema(
        {
            "ecosystem": _nullable_string(),
            "package_name": _nullable_string(),
            "version": _nullable_string(),
            "version_range": _nullable_string(),
            "source": _nullable_string(),
            "confidence": _nullable_string(),
        }
    )


def _malware_impacted_projects_schema() -> dict[str, Any]:
    # Mirrors the impacted_projects row template in the instructions.
    return _slim_row_array_schema(
        {
            "status": _nullable_string(),
            "project_uuid": _nullable_string(),
            "project_name": _nullable_string(),
            "namespace": _nullable_string(),
            "repo_full_name": _nullable_string(),
            "ecosystem": _nullable_string(),
            "package_name": _nullable_string(),
            "version": _nullable_string(),
            "path": _nullable_string(),
            "source": _nullable_string(),
        }
    )


def _configuration_healthy_repository_schema() -> dict[str, Any]:
    # Template keys plus the branch keys pinned by the nested-output smoke test.
    return _slim_row_array_schema(
        {
            "repository": _nullable_string(),
            "endor_project_uuid": _nullable_string(),
            "github_default_branch": _nullable_string(),
            "endor_monitored_branch": _nullable_string(),
            "healthy_reason": _nullable_string(),
            "confidence": _nullable_string(),
            "confidence_reason": _nullable_string(),
        }
    )


def _configuration_excluded_repository_schema() -> dict[str, Any]:
    return _slim_row_array_schema(
        {
            "repository": _nullable_string(),
            "reason": _nullable_string(),
            "evidence": _nullable_string_array(),
        }
    )


# Per-(agent, field) row schemas replacing the generic object blob, consulted
# after profile overrides and before the shared field-name table so slim rows
# apply on the full contract (profile_id None) without colliding across agents
# that share a field name. Bounded scope: dependency-reviewer, the
# malware-responder exposure rows, and the two simple configuration-automation
# repository row shapes. Documented follow-up: cicd-posture rows and the
# remaining configuration-automation rows (not_onboarded_repositories,
# onboarded_repositories_with_gaps, and friends carry nested evidence shapes
# that need their own design pass).
AGENT_FIELD_SCHEMA_OVERRIDES = {
    ("dependency-reviewer", "findings"): _dependency_reviewer_findings_schema,
    ("dependency-reviewer", "manifests"): _dependency_reviewer_manifests_schema,
    ("dependency-reviewer", "dependencies_reviewed"): _dependency_reviewer_dependencies_schema,
    ("malware-responder", "affected_package_set"): _malware_affected_package_schema,
    ("malware-responder", "impacted_projects"): _malware_impacted_projects_schema,
    ("configuration-automation", "onboarded_healthy_repositories"): _configuration_healthy_repository_schema,
    ("configuration-automation", "excluded_repositories"): _configuration_excluded_repository_schema,
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
    "execution_context": _execution_context_schema,
    "report_scope": _report_scope_schema,
    "selected_remediation": _selected_remediation_schema,
    "selected_upgrade": _selected_remediation_schema,
    "dependency_delta": _generic_object_schema,
    "risk_decision": _risk_decision_schema,
    "dependency_graph_audit": _dependency_graph_audit_schema,
    "evidence_queries": _evidence_queries_schema,
    "uia_evidence": _uia_evidence_schema,
    "remediation_candidates": _remediation_candidates_schema,
    "remediation_options": _remediation_candidates_schema,
    "upgrade_candidates": _remediation_candidates_schema,
    "patch_plan": _patch_plan_schema,
    "patches": _patches_schema,
    "validation": _validation_schema,
    "validation_plan": _validation_schema,
    "change_requests": _change_requests_schema,
    "tickets": _tickets_schema,
    "policy_context": _policy_context_schema,
    "policy_evaluations": _policy_evaluations_schema,
    "task_state": _task_state_schema,
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
    "list_all",
    "artifact",
    "reason",
)

EVIDENCE_QUERY_REQUIRED_TEXT_FIELDS = ("name", "resource", "source", "status")
EVIDENCE_QUERY_SOURCE_VALUES = (
    "endorctl_agent_api",
    "endor_mcp",
    "local_repository",
    "user_input",
    "public_docs",
)
# Must stay identical to the taught ledger vocabulary in compilers/rendering.py.
EVIDENCE_QUERY_STATUS_VALUES = ("succeeded", "failed", "skipped", "unavailable")
EVIDENCE_QUERY_SUCCESS_STATUSES = frozenset({"succeeded"})
EVIDENCE_QUERY_GAP_STATUSES = frozenset({"failed", "skipped", "unavailable"})
EVIDENCE_QUERY_ARTIFACT_FIELDS = (
    "artifact_ref",
    "sha256",
    "format",
    "bytes",
    "row_count",
)
LARGE_RESULT_ARTIFACT_QUERY_IDS = frozenset(
    {
        "ai-sast-list",
        "finding-browser-complete-counts",
        "tenant-package-inventory",
    }
)
ARTIFACT_METADATA_RE = re.compile(
    r"artifact_ref=[^;\s]+;sha256=[0-9a-f]{64};"
    r"format=[A-Za-z0-9._+-]+;bytes=[1-9][0-9]*"
)
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_LEGACY_LIST_ALL_NEGATION_RE = re.compile(
    r"(?:\b(?:no|not|without|omit\w*|skip\w*)\b[^.;]{0,40}list-all)"
    r"|(?:list-all\s*(?:==|=|:)\s*false\b)"
    r"|(?:list-all[^.;]{0,20}\bnot\b)"
)


def _evidence_query_ledger_errors(
    payload: dict[str, Any],
    *,
    allowed_query_template_ids: frozenset[str] | set[str] | None = None,
) -> list[str]:
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
                errors.append(
                    f"evidence_queries[{index}].{field}: unsupported ledger field; "
                    f"supported fields are {', '.join(EVIDENCE_QUERY_LEDGER_FIELDS)}"
                )
        for field in EVIDENCE_QUERY_REQUIRED_TEXT_FIELDS:
            if not _text(item.get(field)):
                errors.append(
                    f"evidence_queries[{index}].{field}: must be a non-empty string"
                )
        source = _text(item.get("source"))
        if source and source not in EVIDENCE_QUERY_SOURCE_VALUES:
            errors.append(
                f"evidence_queries[{index}].source: must be one of "
                f"{', '.join(EVIDENCE_QUERY_SOURCE_VALUES)} (received {source!r})"
            )
        for field in EVIDENCE_QUERY_LEDGER_FIELDS:
            if (
                field in {"result_count", "list_all", "artifact"}
                or field not in item
                or item[field] is None
            ):
                continue
            if not isinstance(item[field], str):
                errors.append(f"evidence_queries[{index}].{field}: must be a string or null")
        if "result_count" in item and item["result_count"] is not None:
            if isinstance(item["result_count"], bool) or not isinstance(item["result_count"], int):
                errors.append(f"evidence_queries[{index}].result_count: must be an integer or null")
        list_all = item.get("list_all")
        if "list_all" in item and list_all is not None and not isinstance(list_all, bool):
            errors.append(
                f"evidence_queries[{index}].list_all: must be true, false, or null"
            )
            list_all = None
        artifact = item.get("artifact")
        artifact_valid = False
        if "artifact" in item and artifact is not None:
            artifact_errors = _artifact_metadata_errors(index, artifact)
            errors.extend(artifact_errors)
            artifact_valid = not artifact_errors
        status = _text(item.get("status"))
        if status and status not in EVIDENCE_QUERY_STATUS_VALUES:
            errors.append(
                f"evidence_queries[{index}].status: must be one of "
                f"{', '.join(EVIDENCE_QUERY_STATUS_VALUES)} (received {status!r})"
            )
        if status in EVIDENCE_QUERY_GAP_STATUSES:
            if status == "skipped":
                if not _text(item.get("reason")):
                    errors.append(
                        f"evidence_queries[{index}].reason: required when status is skipped"
                    )
            elif not _text(item.get("reason")) and not data_gaps:
                errors.append(f"evidence_queries[{index}].reason: required for unavailable or failed evidence")
        query_template_id = _text(item.get("query_template_id"))
        if (
            allowed_query_template_ids is not None
            and query_template_id
            and query_template_id not in allowed_query_template_ids
        ):
            errors.append(
                f"evidence_queries[{index}].query_template_id: "
                f"{query_template_id!r} is not a known query recipe id for this "
                "workflow; copy the id of the recipe that was actually executed "
                "or set it to null"
            )
        complete_route = (
            list_all is True
            or query_template_id in LARGE_RESULT_ARTIFACT_QUERY_IDS
            or (list_all is None and _legacy_list_all_delivery(item.get("filter_summary")))
        )
        if (
            status in EVIDENCE_QUERY_SUCCESS_STATUSES
            and complete_route
            and not artifact_valid
            and "artifact" not in item
            and not ARTIFACT_METADATA_RE.search(_text(item.get("reason")))
        ):
            errors.append(
                f"evidence_queries[{index}].artifact: required for a successful "
                "complete-inventory route; copy the artifact summarizer output "
                "into artifact {artifact_ref, sha256, format, bytes, row_count} "
                "or into reason as "
                '"artifact_ref=<path>;sha256=<64-hex>;format=<format>;bytes=<bytes>"'
            )
    return errors


def _legacy_list_all_delivery(filter_summary: Any) -> bool:
    """Prose fallback for rows that predate the structured `list_all` boolean."""

    summary = _text(filter_summary).lower()
    if "list-all" not in summary:
        return False
    return not _LEGACY_LIST_ALL_NEGATION_RE.search(summary)


def _artifact_metadata_errors(index: int, artifact: Any) -> list[str]:
    if not isinstance(artifact, dict):
        return [f"evidence_queries[{index}].artifact: must be an object or null"]
    errors: list[str] = []
    for field in artifact:
        if field not in EVIDENCE_QUERY_ARTIFACT_FIELDS:
            errors.append(
                f"evidence_queries[{index}].artifact.{field}: unsupported artifact "
                f"field; supported fields are {', '.join(EVIDENCE_QUERY_ARTIFACT_FIELDS)}"
            )
    if not _text(artifact.get("artifact_ref")):
        errors.append(
            f"evidence_queries[{index}].artifact.artifact_ref: must be a non-empty string"
        )
    sha256 = artifact.get("sha256")
    if not isinstance(sha256, str) or not _SHA256_HEX_RE.fullmatch(sha256):
        errors.append(
            f"evidence_queries[{index}].artifact.sha256: must be a 64-character lowercase hex digest"
        )
    if not _text(artifact.get("format")):
        errors.append(
            f"evidence_queries[{index}].artifact.format: must be a non-empty string"
        )
    size = artifact.get("bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        errors.append(
            f"evidence_queries[{index}].artifact.bytes: must be a positive integer"
        )
    row_count = artifact.get("row_count")
    if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count < 0:
        errors.append(
            f"evidence_queries[{index}].artifact.row_count: must be a non-negative integer"
        )
    return errors


def _project_scope_resolution_errors(payload: dict[str, Any]) -> list[str]:
    """A claimed resolution must carry the identifiers that prove it."""

    errors: list[str] = []
    for field in ("project_resolution", "report_scope"):
        value = payload.get(field)
        if not isinstance(value, dict):
            continue
        if _text(value.get("status")).lower() != "resolved":
            continue
        if not _text(value.get("project_uuid")):
            errors.append(f"{field}.project_uuid: required when status is resolved")
        if not _text(value.get("namespace")) and not _text(value.get("endor_namespace")):
            errors.append(
                f"{field}.namespace: required when status is resolved; record "
                "the namespace the project was found in (namespace or endor_namespace)"
            )
    return errors


_AVAILABLE_CLAIM_RE = re.compile(r"\bavailable\b")
_AVAILABLE_NEGATION_RE = re.compile(
    r"\b(?:no|not|none|never|without|isn't|aren't|wasn't|weren't)\b[^.;:!?]{0,40}$"
)


def _summary_count_errors(payload: dict[str, Any]) -> list[str]:
    """An availability claim in the summary needs at least one integer count."""

    summary = payload.get("summary")
    evidence_queries = payload.get("evidence_queries")
    if not isinstance(summary, str) or not isinstance(evidence_queries, list):
        return []
    rows = [row for row in evidence_queries if isinstance(row, dict)]
    if not rows:
        return []
    for row in rows:
        count = row.get("result_count")
        if isinstance(count, int) and not isinstance(count, bool):
            return []
    lowered = summary.lower()
    for match in _AVAILABLE_CLAIM_RE.finditer(lowered):
        prefix = lowered[max(0, match.start() - 40) : match.start()]
        if not _AVAILABLE_NEGATION_RE.search(prefix):
            return [
                "summary: claims available evidence but no evidence_queries row "
                "records an integer result_count; copy the integer counts from "
                "the executed queries or describe the gap in data_gaps"
            ]
    return []


EVIDENCE_CLAIM_LIST_FIELDS = (
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
    "affected_package_set",
    "finding_results",
    "github_evidence",
    "impacted_projects",
    "manifests",
)
VERDICT_CLAIM_FIELDS = (
    "posture_verdict",
    "troubleshooting_verdict",
    "findings_verdict",
    "incident_verdict",
    "onboarding_verdict",
    "upgrade_recommendation",
    "risk_delta",
    "verdict",
    "action",
)
NONDECISIVE_VERDICT_VALUES = frozenset({"INSUFFICIENT_DATA", "UNKNOWN"})


def _claims_current_evidence(payload: dict[str, Any]) -> bool:
    for field in EVIDENCE_CLAIM_LIST_FIELDS:
        if isinstance(payload.get(field), list) and payload[field]:
            return True
    for field in VERDICT_CLAIM_FIELDS:
        value = payload.get(field)
        if (
            isinstance(value, str)
            and value.strip()
            and value.strip() not in NONDECISIVE_VERDICT_VALUES
        ):
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

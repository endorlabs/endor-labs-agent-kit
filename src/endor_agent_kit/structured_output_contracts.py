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
        StructuredOutputField("data_gaps", "list[string]"),
    ),
    "sca-remediation": (
        StructuredOutputField("summary", "string"),
        StructuredOutputField("remediation_candidates", "list[object]"),
        StructuredOutputField("project_resolution", "object"),
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
        StructuredOutputField("data_gaps", "list[string]"),
    ),
}


def known_structured_agent_ids() -> tuple[str, ...]:
    """Return agent ids with structured output contracts."""

    return tuple(sorted(STRUCTURED_OUTPUT_CONTRACTS))


def required_fields_for(agent_id: str) -> tuple[str, ...]:
    """Return required top-level output fields for an agent."""

    return tuple(field.name for field in STRUCTURED_OUTPUT_CONTRACTS.get(agent_id, ()) if field.required)


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
    errors.extend(_evidence_gap_contract_errors(contract, payload))
    return errors


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
    return []

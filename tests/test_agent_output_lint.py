from __future__ import annotations

import json

from endor_agent_kit.agent_output_lint import extract_json_object, lint_agent_output
from endor_agent_kit.cli import main
from endor_agent_kit.structured_output_contracts import (
    STRUCTURED_OUTPUT_CONTRACTS,
    known_structured_agent_ids,
)


def test_lint_rejects_failed_sca_qa_patterns():
    output = """
I remembered the namespace from a prior session and will use that repo.

```bash
cat ~/.endorctl/config.yaml
```

Assuming the repository is https://github.com/endorlabs/death-star.

{
  "summary": "Planning a fix from local notes.",
  "project_resolution": {
    "status": "resolved",
    "project_uuid": "proj-123",
    "namespace": "death-star",
    "namespace_provenance": "prior session"
  },
  "risk_decision": {
    "status": "approved_low_risk"
  },
  "selected_remediation": {
    "branch_name": "remediation/sca/netty-4.1.118"
  },
  "data_gaps": []
}
"""

    errors = lint_agent_output("sca-remediation", output)

    assert "unsafe Endor config read: do not use cat on Endor config files" in errors
    assert "invalid provenance: memory or older sessions cannot prove namespace, repository, or project scope" in errors
    assert "invalid provenance: repository URLs and repo_full_name values must not be guessed" in errors
    assert "data_gaps: cannot be empty when Finding or VersionUpgrade/UIA evidence is absent" in errors
    assert "data_gaps: missing Finding evidence gap" in errors
    assert "data_gaps: missing VersionUpgrade/UIA evidence gap" in errors


def test_lint_allows_explicit_memory_non_provenance_wording():
    output = """
Namespace: `auri`, from your explicit prompt, not memory.

Prior context applied: only procedural memory that Probe Droid is read-only and
Agent Kit QA must use live tenant/runtime evidence. I did not use it as proof.

Resolved the repository to a live Endor Project without remembered identifiers.
No remembered project UUID or finding count was used.
Resolved current live Endor project without using remembered project UUID or namespace evidence.
"""

    assert lint_agent_output("unknown-agent", output) == []


def test_lint_requires_json_object_for_every_structured_agent():
    for agent_id in known_structured_agent_ids():
        errors = lint_agent_output(agent_id, "I checked this and found no issues.")

        assert f"{agent_id} output must include a JSON object" in errors


def test_lint_rejects_missing_required_structured_fields():
    output = json.dumps(
        {
            "verdict": "allow",
            "conditions": [],
            "alternatives": [],
            "summary": "Missing data gaps.",
        }
    )

    assert "data_gaps: required" in lint_agent_output("dependency-decision-helper", output)


def test_lint_rejects_remediation_planner_unproven_counts_and_selection():
    output = json.dumps(
        {
            "summary": "Local docs say there are 17 SCA findings.",
            "project_resolution": {
                "status": "resolved",
                "project_uuid": "proj-123",
                "namespace": "bailey",
                "namespace_provenance": "ENDOR_NAMESPACE",
            },
            "remediation_options": [],
            "selected_remediation": {
                "package": "lodash",
                "findings_fixed": 17,
            },
            "data_gaps": [],
        }
    )

    errors = lint_agent_output("remediation-planner", output)

    assert "selected_remediation: cannot select remediation without verified remediation_options" in errors
    assert "data_gaps: cannot be empty when Finding or VersionUpgrade/UIA evidence is absent" in errors
    assert "data_gaps: missing Finding evidence gap" in errors
    assert "data_gaps: missing VersionUpgrade/UIA evidence gap" in errors


def test_lint_accepts_remediation_planner_insufficient_evidence_payload():
    output = json.dumps(
        {
            "summary": "Insufficient verified Endor evidence to choose a remediation.",
            "project_resolution": {
                "status": "unresolved",
                "namespace": "bailey",
                "namespace_provenance": "user_request.namespace",
            },
            "evidence_queries": [
                _evidence_query(
                    "Project",
                    status="failed",
                    query_template_id="project-resolution",
                    reason="No matching project found in selected namespace",
                )
            ],
            "remediation_options": [],
            "selected_remediation": None,
            "data_gaps": [
                "Missing Endor Finding evidence for the selected repository",
                "Missing VersionUpgrade/UIA evidence for remediation risk and fixed counts",
            ],
        }
    )

    assert lint_agent_output("remediation-planner", output) == []


def test_lint_accepts_structured_data_gap_objects():
    output = json.dumps(
        {
            "summary": "Live evidence was unavailable.",
            "project_resolution": {
                "status": "unresolved",
                "namespace": "auri",
                "namespace_provenance": "current_request",
            },
            "evidence_queries": [],
            "remediation_options": [],
            "selected_remediation": None,
            "data_gaps": [
                {
                    "id": "main_context_findings_unavailable",
                    "reason": "Finding evidence was not queried because project_uuid is unresolved.",
                },
                {
                    "id": "version_upgrade_uia_unavailable",
                    "reason": "VersionUpgrade/UIA evidence was not queried because project_uuid is unresolved.",
                },
            ],
        }
    )

    assert lint_agent_output("remediation-planner", output) == []


def test_lint_rejects_non_array_sca_uia_evidence():
    output = json.dumps(
        {
            "summary": "Selected remediation.",
            "project_resolution": {
                "status": "resolved",
                "project_uuid": "proj-123",
                "namespace": "auri",
                "namespace_provenance": "current_request",
            },
            "evidence_queries": [
                _evidence_query("Finding", query_template_id="finding-detail"),
                _evidence_query("VersionUpgrade", query_template_id="version-upgrade-summary"),
            ],
            "selected_remediation": {
                "package": "mvn://example:demo",
                "from_version": "1.0.0",
                "to_version": "1.0.1",
                "branch_name": "remediation/sca/demo-1.0.1",
            },
            "uia_evidence": {"uuid": "version-upgrade-123"},
            "risk_decision": {
                "status": "approved_low_risk",
            },
            "data_gaps": [
                "Finding evidence was not included in this fixture.",
                "VersionUpgrade/UIA evidence was malformed.",
            ],
        }
    )

    assert "uia_evidence: must be an array" in lint_agent_output("sca-remediation", output)


def test_lint_accepts_uia_fixed_finding_evidence_as_sca_evidence():
    output = json.dumps(
        {
            "summary": "Selected a UIA-backed remediation.",
            "remediation_candidates": [],
            "project_resolution": {
                "status": "resolved",
                "project_uuid": "proj-123",
                "namespace": "auri",
                "namespace_provenance": "current_request",
            },
            "evidence_queries": [
                _evidence_query("Finding", query_template_id="finding-detail"),
                _evidence_query("VersionUpgrade", query_template_id="version-upgrade-summary"),
            ],
            "selected_remediation": {
                "package": "mvn://example:demo",
                "from_version": "1.0.0",
                "to_version": "1.0.1",
                "branch_name": "remediation/sca/demo-1.0.1",
                "upgrade_risk": "low",
                "cia_status": "no breaking changes",
                "findings_introduced": 0,
            },
            "uia_evidence": [
                {
                    "resource": "VersionUpgrade",
                    "uuid": "version-upgrade-123",
                    "upgrade_risk": "low",
                    "cia_status": "no breaking changes",
                    "total_findings_fixed": 18,
                    "total_findings_introduced": 0,
                    "sample_fixed_findings": ["GHSA-1234-5678-9012"],
                }
            ],
            "risk_decision": {
                "status": "approved_with_validation_required",
                "source_usage_summary": "Source usage was inspected.",
                "validation_requirements": ["mvn test"],
            },
            "patch_plan": [],
            "validation": [{"command": "mvn test", "status": "planned"}],
            "change_requests": [
                {
                    "status": "not_created",
                    "proposed_branch": "remediation/sca/demo-1.0.1",
                }
            ],
            "tickets": [],
            "data_gaps": [],
        }
    )

    assert lint_agent_output("sca-remediation", output) == []


def test_lint_rejects_broad_finding_inventory_for_sca_selection_plan():
    output = json.dumps(
        {
            "summary": "Selected a remediation.",
            "remediation_candidates": [],
            "project_resolution": {
                "status": "resolved",
                "project_uuid": "proj-123",
                "namespace": "auri",
                "namespace_provenance": "current_request",
            },
            "evidence_queries": [
                _evidence_query(
                    "Finding",
                    status="completed",
                    query_template_id="finding-summary",
                    filter_summary="Broad namespace Finding inventory.",
                    result_count=10025,
                ),
                _evidence_query(
                    "VersionUpgrade",
                    status="completed",
                    query_template_id="version-upgrade-summary",
                    result_count=20,
                ),
            ],
            "selected_remediation": {
                "package": "mvn://example:demo",
                "from_version": "1.0.0",
                "to_version": "1.0.1",
                "branch_name": "remediation/sca/demo-1.0.1",
            },
            "uia_evidence": [
                {
                    "resource": "VersionUpgrade",
                    "uuid": "version-upgrade-123",
                    "total_findings_fixed": 18,
                }
            ],
            "risk_decision": {
                "status": "blocked_needs_compatibility_analysis",
                "source_usage_summary": "Source usage was inspected.",
                "validation_requirements": ["mvn test"],
            },
            "patch_plan": [],
            "validation": [],
            "change_requests": [],
            "tickets": [],
            "data_gaps": ["Full Finding detail was skipped."],
        }
    )

    errors = lint_agent_output("sca-remediation", output, task_profile="selection-plan")

    assert "evidence_queries: selection-plan must not enumerate broad Finding inventories before VersionUpgrade/UIA narrowing" in errors
    assert "evidence_queries: selection-plan must query VersionUpgrade/UIA before Finding detail expansion" in errors


def test_lint_allows_selection_plan_after_version_upgrade_narrowing():
    output = json.dumps(
        {
            "summary": "Selected a remediation.",
            "remediation_candidates": [],
            "project_resolution": {
                "status": "resolved",
                "project_uuid": "proj-123",
                "namespace": "auri",
                "namespace_provenance": "current_request",
            },
            "evidence_queries": [
                _evidence_query(
                    "VersionUpgrade",
                    status="completed",
                    query_template_id="version-upgrade-summary",
                    result_count=20,
                ),
                _evidence_query(
                    "Finding",
                    status="completed",
                    query_template_id="selected-finding-detail",
                    result_count=18,
                    reason="Selected-candidate advisory mapping only.",
                ),
            ],
            "selected_remediation": {
                "package": "mvn://example:demo",
                "from_version": "1.0.0",
                "to_version": "1.0.1",
                "branch_name": "remediation/sca/demo-1.0.1",
                "upgrade_risk": "medium",
                "cia_status": "indeterminate",
                "findings_introduced": 0,
            },
            "uia_evidence": [
                {
                    "resource": "VersionUpgrade",
                    "uuid": "version-upgrade-123",
                    "total_findings_fixed": 18,
                }
            ],
            "risk_decision": {
                "status": "blocked_needs_compatibility_analysis",
                "source_usage_summary": "Source usage was inspected.",
                "validation_requirements": ["mvn test"],
            },
            "patch_plan": [],
            "validation": [],
            "change_requests": [],
            "tickets": [],
            "data_gaps": ["Full Finding detail was skipped."],
        }
    )

    assert lint_agent_output("sca-remediation", output, task_profile="selection-plan") == []


def test_lint_blocks_default_scan_recommendation_for_read_only_agents():
    errors = lint_agent_output(
        "vulnerability-explainer",
        "Run a new Endor scan, then I can explain the vulnerability.",
    )

    assert "read-only workflow must not recommend running a new Endor scan as the default next step" in errors


def test_lint_rejects_unsafe_endorctl_query_recipe_shapes():
    output = """
```bash
endorctl api list -r Project --field-mask "uuid,meta.name" -o json
endorctl api list -r Project -n auri -o json
endorctl api get -r Finding -n auri --filter 'uuid=="finding-123"' -o json
endorctl api list -r Finding -n auri --field-mask "uuid" --list-all -o json
```
"""

    errors = lint_agent_output("unknown-agent", output)

    assert "endorctl query recipe: api commands must include explicit namespace" in errors
    assert "endorctl query recipe: api list commands must include --field-mask" in errors
    assert "endorctl query recipe: api get must not use filters; use --uuid or api list" in errors
    assert "endorctl query recipe: broad Finding --list-all is not allowed" in errors


def test_lint_accepts_safe_endorctl_query_recipe_shapes():
    output = """
```bash
endorctl api list -r Project -n auri --field-mask "uuid,meta.name,spec.git" -o json
endorctl api get -r Finding -n auri --uuid finding-123 -o json
endorctl api list -r VersionUpgrade -n auri --filter 'spec.project_uuid=="proj-123"' --field-mask "uuid,spec.upgrade_info" -o json
```
"""

    assert lint_agent_output("unknown-agent", output) == []


def test_extract_json_object_returns_last_json_object():
    assert extract_json_object('{"first": true}\nthen\n{"second": true}') == {"second": True}


def test_lint_agent_output_cli_reports_errors(tmp_path, capsys):
    output = tmp_path / "agent-output.txt"
    output.write_text("cat ~/.config/endorctl/config.yaml\n", encoding="utf-8")

    status = main(["lint-agent-output", "--agent", "sca-remediation", str(output)])
    captured = capsys.readouterr().out

    assert status == 1
    assert "unsafe Endor config read" in captured


def test_lint_agent_output_cli_accepts_task_profile(tmp_path, capsys):
    output = tmp_path / "agent-output.txt"
    output.write_text(
        json.dumps(
            {
                "summary": "Selected a remediation.",
                "remediation_candidates": [],
                "project_resolution": {
                    "status": "resolved",
                    "project_uuid": "proj-123",
                    "namespace": "auri",
                    "namespace_provenance": "current_request",
                },
                "evidence_queries": [
                    _evidence_query(
                        "Finding",
                        status="completed",
                        query_template_id="finding-summary",
                        result_count=10025,
                    ),
                    _evidence_query(
                        "VersionUpgrade",
                        status="completed",
                        query_template_id="version-upgrade-summary",
                        result_count=20,
                    ),
                ],
                "selected_remediation": {
                    "package": "mvn://example:demo",
                    "from_version": "1.0.0",
                    "to_version": "1.0.1",
                    "branch_name": "remediation/sca/demo-1.0.1",
                },
                "uia_evidence": [
                    {
                        "resource": "VersionUpgrade",
                        "uuid": "version-upgrade-123",
                        "total_findings_fixed": 18,
                    }
                ],
                "risk_decision": {
                    "status": "blocked_needs_compatibility_analysis",
                    "source_usage_summary": "Source usage was inspected.",
                    "validation_requirements": ["mvn test"],
                },
                "patch_plan": [],
                "validation": [],
                "change_requests": [],
                "tickets": [],
                "data_gaps": ["Full Finding detail was skipped."],
            }
        ),
        encoding="utf-8",
    )

    status = main(["lint-agent-output", "--agent", "sca-remediation", "--task-profile", "selection-plan", str(output)])
    captured = capsys.readouterr().out

    assert status == 1
    assert "broad Finding inventories" in captured


def test_lint_accepts_minimal_structured_payloads_for_non_project_gate_agents():
    for agent_id, fields in STRUCTURED_OUTPUT_CONTRACTS.items():
        if agent_id in {"sca-remediation", "remediation-planner"}:
            continue
        payload = {
            field.name: _placeholder_value(field.kind)
            for field in fields
            if field.required
        }
        if "evidence_queries" in payload:
            payload["evidence_queries"] = [
                _evidence_query(
                    "Fixture",
                    status="skipped",
                    source="user_input",
                    query_template_id=None,
                    reason="No live evidence required for fixture.",
                )
            ]

        assert lint_agent_output(agent_id, json.dumps(payload)) == []


def _placeholder_value(kind: str):
    if kind.startswith("list["):
        return []
    if kind == "object":
        return {}
    if kind == "integer":
        return 0
    return "fixture"


def _evidence_query(
    resource: str,
    *,
    name: str | None = None,
    source: str = "endorctl_api",
    status: str = "succeeded",
    query_template_id: str | None = None,
    filter_summary: str | None = "fixture selector",
    field_mask_summary: str | None = "fixture fields",
    result_count: int | None = 1,
    reason: str = "Fixture evidence.",
) -> dict:
    return {
        "name": name or f"{resource} evidence",
        "resource": resource,
        "source": source,
        "status": status,
        "query_template_id": query_template_id,
        "filter_summary": filter_summary,
        "field_mask_summary": field_mask_summary,
        "result_count": result_count,
        "reason": reason,
    }

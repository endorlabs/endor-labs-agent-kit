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


def test_lint_accepts_remediation_planner_version_upgrade_backed_options():
    output = json.dumps(
        {
            "summary": "Selected a UIA-backed remediation option.",
            "project_resolution": {
                **_resolved_project_resolution(),
            },
            "evidence_queries": [
                _evidence_query("Project", query_template_id="project-by-git"),
                _evidence_query("VersionUpgrade", query_template_id="version-upgrade-summary"),
                _evidence_query("Finding", query_template_id="selected-finding-detail"),
            ],
            "remediation_options": [
                {
                    "rank": 1,
                    "version_upgrade_uuid": "version-upgrade-123",
                    "package": "pypi://urllib3",
                    "from_version": "1.25.11",
                    "to_version": "2.7.0",
                    "upgrade_risk": "low",
                    "cia_status": "no breaking changes",
                    "total_findings_fixed": 11,
                    "total_findings_introduced": 0,
                }
            ],
            "selected_remediation": {
                "version_upgrade_uuid": "version-upgrade-123",
                "package": "pypi://urllib3",
                "from_version": "1.25.11",
                "to_version": "2.7.0",
                "findings_fixed": 11,
                "findings_introduced": 0,
            },
            "data_gaps": [],
        }
    )

    assert lint_agent_output("remediation-planner", output, task_profile="selection-plan") == []


def test_lint_accepts_remediation_planner_evidence_check_without_selected_options():
    output = json.dumps(
        {
            "summary": "Finding and VersionUpgrade evidence lanes are confirmed.",
            "project_resolution": {
                **_resolved_project_resolution(),
            },
            "evidence_queries": [
                _evidence_query(
                    "Project",
                    query_template_id="project-by-list",
                    filter_summary="namespace=auri; list all projects; matched on repository URL",
                ),
                _evidence_query(
                    "VersionUpgrade",
                    query_template_id="version-upgrade-summary",
                    filter_summary="context.type=CONTEXT_TYPE_MAIN; project_uuid=proj-123; list-all",
                    result_count=339,
                ),
                _evidence_query(
                    "Finding",
                    query_template_id="finding-availability",
                    filter_summary="context.type=CONTEXT_TYPE_MAIN; project_uuid=proj-123; list-all",
                    result_count=10025,
                ),
            ],
            "remediation_options": [],
            "selected_remediation": None,
            "data_gaps": [],
        }
    )

    assert lint_agent_output("remediation-planner", output, task_profile="evidence-check") == []


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
                **_resolved_project_resolution(),
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
                **_resolved_project_resolution(),
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
                **_resolved_project_resolution(),
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
            "project_resolution": _resolved_project_resolution(),
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


def test_lint_accepts_sca_evidence_check_without_selection_or_branch():
    output = json.dumps(
        {
            "summary": "Evidence-check stopped after confirming scoped Finding and VersionUpgrade availability.",
            "remediation_candidates": [],
            "project_resolution": {
                "status": "resolved",
                "project_uuid": "proj-123",
                "namespace": "auri",
                "namespace_provenance": "current_request",
                "repo_full_name": "endor-matt/death-star",
                "default_branch": None,
                "branch_provenance": "not queried; out of scope for evidence-check profile",
                "traverse_attempted": True,
            },
            "evidence_queries": [
                _evidence_query(
                    "Finding",
                    query_template_id="finding-availability",
                    filter_summary="context.type=CONTEXT_TYPE_MAIN; project_uuid=proj-123; list-all",
                    result_count=10025,
                ),
                _evidence_query(
                    "VersionUpgrade",
                    query_template_id="version-upgrade-summary",
                    filter_summary="context.type=CONTEXT_TYPE_MAIN; project_uuid=proj-123; list-all",
                    result_count=339,
                ),
            ],
            "selected_remediation": None,
            "uia_evidence": [
                {
                    "resource": "VersionUpgrade",
                    "uuid": "version-upgrade-123",
                    "total_findings_fixed": 5,
                    "total_findings_introduced": 0,
                }
            ],
            "risk_decision": None,
            "patch_plan": [],
            "validation": [],
            "change_requests": [],
            "tickets": [],
            "data_gaps": [
                "risk_decision=null: evidence-check profile does not select or rank candidates",
                "default_branch: not queried; out of scope for evidence-check profile",
            ],
        }
    )

    assert lint_agent_output("sca-remediation", output, task_profile="evidence-check") == []


def test_lint_blocks_default_scan_recommendation_for_read_only_agents():
    errors = lint_agent_output(
        "vulnerability-explainer",
        "Run a new Endor scan, then I can explain the vulnerability.",
    )

    assert "read-only workflow must not recommend running a new Endor scan as the default next step" in errors


def test_lint_rejects_resolved_project_without_normalized_scope_fields():
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
                _evidence_query("VersionUpgrade", query_template_id="version-upgrade-summary"),
                _evidence_query("Finding", query_template_id="selected-finding-detail"),
            ],
            "selected_remediation": {},
            "uia_evidence": [{"resource": "VersionUpgrade", "total_findings_fixed": 1}],
            "risk_decision": {
                "status": "blocked_needs_compatibility_analysis",
                "source_usage_summary": "Source usage was inspected.",
                "validation_requirements": [],
            },
            "patch_plan": [],
            "validation": [],
            "change_requests": [],
            "tickets": [],
            "data_gaps": [],
        }
    )

    errors = lint_agent_output("sca-remediation", output)

    assert "project_resolution.repo_full_name: normalized repository identity required when status is resolved" in errors
    assert "project_resolution.default_branch: branch provenance required when status is resolved" in errors
    assert "project_resolution.traverse_attempted: required when status is resolved" in errors


def test_lint_rejects_read_only_payload_with_unconfirmed_mutation_command():
    output = json.dumps(
        {
            "troubleshooting_verdict": "PARTIAL_DIAGNOSIS",
            "executive_summary": {
                "issue_title": "Scan failed",
                "impact": "No current scan result",
                "likely_owner": "repo_admin",
                "confidence": "MEDIUM",
                "next_best_action": "Run endorctl scan",
                "confirmation_required": False,
            },
            "intake_classification": {
                "issue_lanes": ["SCAN_EXECUTION_FAILURE"],
                "affected_product_area": "scan",
                "affected_ecosystem": None,
                "affected_integration_type": None,
                "resource_selectors_used": [],
            },
            "issue_lanes": [],
            "affected_resources": [],
            "evidence_queries": [
                _evidence_query("user_input", source="user_input", query_template_id=None)
            ],
            "evidence_summary": {},
            "root_cause_hypotheses": [],
            "recommended_actions": [
                {
                    "action": "Run endorctl scan --languages=java",
                    "validation": "Check ScanResult",
                    "confirmation_required": False,
                }
            ],
            "validation_plan": [],
            "support_escalation_packet": {
                "include": [],
                "redactions_applied": [],
                "reason_to_escalate": "",
            },
            "data_gaps": [],
            "future_action_contracts": [],
            "future_scope": [],
        }
    )

    errors = lint_agent_output("endor-troubleshooter", output)

    assert "$.recommended_actions[0]: mutation command requires confirmation_required=true and must remain a future action" in errors


def test_lint_accepts_troubleshooter_future_action_contract_for_mutation():
    output = json.dumps(_valid_troubleshooter_output())

    assert lint_agent_output("endor-troubleshooter", output) == []


def test_lint_does_not_join_fields_into_synthetic_mutation_command():
    payload = _valid_troubleshooter_output()
    payload["recommended_actions"] = [
        {
            "priority": 1,
            "owner_role": "Developer using endorctl API",
            "action": "Update Finding list filters to use spec.project_uuid.",
            "why": "Finding resources are project-scoped by spec.project_uuid.",
            "friction": "LOW",
            "validation": "Confirm the corrected Finding query returns expected results.",
            "confidence": "HIGH",
            "confirmation_required": False,
        }
    ]

    assert lint_agent_output("endor-troubleshooter", json.dumps(payload)) == []


def test_lint_rejects_probe_droid_rows_without_branch_and_project_normalization():
    output = json.dumps(_valid_probe_droid_output())
    payload = json.loads(output)
    payload["report_scope"].pop("namespace_provenance")
    payload["onboarded_repositories_with_gaps"][0].pop("endor_monitored_branch")
    payload["onboarded_repositories_with_gaps"][0]["endor_project"].pop("project_uuid")

    errors = lint_agent_output("probe-droid", json.dumps(payload))

    assert "report_scope.namespace_provenance: required when Endor project evidence is queried" in errors
    assert "onboarded_repositories_with_gaps[0].endor_project.project_uuid: required for onboarded repositories" in errors
    assert "onboarded_repositories_with_gaps[0].endor_monitored_branch: required for onboarded repositories" in errors


def test_lint_accepts_probe_droid_normalized_output():
    assert lint_agent_output("probe-droid", json.dumps(_valid_probe_droid_output())) == []


def test_lint_accepts_probe_droid_aliases_for_gap_rows():
    payload = _valid_probe_droid_output()
    payload["report_scope"].pop("namespace")
    payload["report_scope"]["endor_namespace"] = "auri"
    row = payload["onboarded_repositories_with_gaps"][0]
    row["full_name"] = row.pop("repository")
    row["github_default_branch"] = row.pop("default_branch")
    row["endor_project_uuid"] = row["endor_project"].pop("project_uuid")
    row["endor_monitored_branch"] = None
    row["monitored_branch_note"] = "Cannot confirm monitored branch from current Project field evidence."
    row["statuses"].append("MONITORED_BRANCH_EVIDENCE_UNAVAILABLE")
    row["data_gaps"] = ["monitored_branch evidence unavailable"]

    assert lint_agent_output("probe-droid", json.dumps(payload)) == []


def test_lint_rejects_probe_droid_healthy_rows_with_branch_gaps():
    payload = _valid_probe_droid_output()
    row = payload["onboarded_repositories_with_gaps"].pop()
    row["github_default_branch"] = row.pop("default_branch")
    row["endor_project_uuid"] = row["endor_project"].pop("project_uuid")
    row["endor_monitored_branch"] = None
    row["monitored_branch_note"] = "Cannot confirm monitored branch from current Project field evidence."
    payload["onboarded_healthy_repositories"].append(row)

    errors = lint_agent_output("probe-droid", json.dumps(payload))

    assert (
        "onboarded_healthy_repositories[0]: repositories with monitored-branch gaps must be reported under onboarded_repositories_with_gaps"
        in errors
    )


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
endorctl api list -r Finding -n auri --filter 'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="proj-123" and spec.method=="SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"' --field-mask "uuid,context.type,spec.project_uuid,spec.method" --list-all -o json
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
        if agent_id in {"sca-remediation", "remediation-planner", "probe-droid", "endor-troubleshooter"}:
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


def _resolved_project_resolution() -> dict:
    return {
        "status": "resolved",
        "project_uuid": "proj-123",
        "namespace": "auri",
        "namespace_provenance": "current_request",
        "repo_full_name": "endor-matt/death-star",
        "default_branch": "main",
        "branch_provenance": "git_remote_default_branch",
        "traverse_attempted": True,
    }


def _valid_troubleshooter_output() -> dict:
    return {
        "troubleshooting_verdict": "PARTIAL_DIAGNOSIS",
        "executive_summary": {
            "issue_title": "Scan failed",
            "impact": "No current scan result",
            "likely_owner": "repo_admin",
            "confidence": "MEDIUM",
            "next_best_action": "Human-approved scan rerun",
            "confirmation_required": True,
        },
        "intake_classification": {
            "issue_lanes": ["SCAN_EXECUTION_FAILURE"],
            "affected_product_area": "scan",
            "affected_ecosystem": None,
            "affected_integration_type": None,
            "resource_selectors_used": [],
        },
        "issue_lanes": [],
        "affected_resources": [],
        "evidence_queries": [
            _evidence_query("user_input", source="user_input", query_template_id=None)
        ],
        "evidence_summary": {},
        "root_cause_hypotheses": [],
        "recommended_actions": [
            {
                "action": "Review the redacted scan error and confirm whether to rerun the scan.",
                "validation": "A later ScanResult reaches a terminal status.",
                "confirmation_required": True,
            }
        ],
        "validation_plan": [],
        "support_escalation_packet": {
            "include": [],
            "redactions_applied": [],
            "reason_to_escalate": "",
        },
        "data_gaps": [],
        "future_action_contracts": [
            {
                "action": "Run endorctl scan after user approval.",
                "owner": "repo_admin",
                "reason": "Need fresh scan evidence.",
                "expected_effect": "New ScanResult.",
                "confirmation_required": True,
                "validation": "Check ScanResult status.",
            }
        ],
        "future_scope": [],
    }


def _valid_probe_droid_output() -> dict:
    return {
        "onboarding_verdict": "PARTIAL_COVERAGE",
        "executive_report": {
            "verdict": "PARTIAL_COVERAGE",
            "headline": "One repository has onboarding gaps.",
            "top_counts": {"github_repositories_in_scope": 1},
            "top_blockers": ["Monitored branch mismatch."],
            "top_actions": [],
            "drill_down_sections": ["onboarded_repositories_with_gaps"],
        },
        "report_scope": {
            "github_org": "endor-matt",
            "repositories_requested": ["endor-matt/death-star"],
            "mode": "single-repo",
            "namespace": "auri",
            "namespace_provenance": "current_request",
            "monitored_branch_policy": "github_default_branch",
            "sampling_mode": "none",
            "sample_size": 0,
            "coverage_limitations": [],
            "v1_exclusions": [],
        },
        "coverage_summary": {
            "github_repositories_in_scope": 1,
            "github_repositories_sampled": 0,
            "endor_projects_matched": 1,
            "repositories_not_onboarded": 0,
            "repositories_with_dependency_resolution_gaps": 0,
            "repositories_with_reachability_gaps": 0,
            "repositories_with_github_app_gaps": 1,
            "repositories_healthy": 0,
            "repositories_ambiguous": 0,
            "excluded_repositories": 0,
            "top_repeated_blockers": [],
        },
        "github_inventory_summary": {
            "source": "user_input",
            "pagination_complete": True,
            "inventory_limit": 1,
            "archived_count": 0,
            "inactive_count": 0,
            "manifest_families_seen": [],
            "data_gaps": [],
        },
        "github_app_coverage": {
            "status": "APP_INSTALLED_SELECTED_REPOS",
            "selected_repo_count": 1,
            "selected_project_uuids": ["proj-123"],
            "selected_repositories": ["endor-matt/death-star"],
            "repositories_not_selected": [],
            "selection_mapping_gaps": [],
            "scanner_status": "enabled",
            "sync_errors": [],
            "evidence": [],
        },
        "not_onboarded_repositories": [],
        "onboarded_repositories_with_gaps": [
            {
                "repository": "endor-matt/death-star",
                "url": "https://github.com/endor-matt/death-star",
                "default_branch": "main",
                "endor_project": {
                    "matched": True,
                    "project_uuid": "proj-123",
                    "project_name": "endor-matt/death-star",
                    "namespace": "auri",
                    "match_method": "owner_repo",
                },
                "endor_monitored_branch": "release",
                "statuses": ["BRANCH_MISMATCH"],
                "evidence": [],
            }
        ],
        "onboarded_healthy_repositories": [],
        "ambiguous_matches": [],
        "excluded_repositories": [],
        "recommended_actions": [],
        "confirmed_org_wide_actions": [],
        "sampled_prescription_hypotheses": [],
        "requires_full_inventory_validation": [],
        "validation_plan": [],
        "evidence_queries": [
            _evidence_query("Project", query_template_id="project-branch-coverage")
        ],
        "data_gaps": [],
        "future_scope": [],
    }


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

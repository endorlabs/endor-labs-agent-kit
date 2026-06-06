from __future__ import annotations

import json

from endor_agent_kit.agent_output_lint import extract_json_object, lint_agent_output
from endor_agent_kit.cli import main


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
"""

    assert lint_agent_output("probe-droid", output) == []


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
                {
                    "resource": "Project",
                    "status": "failed",
                    "reason": "No matching project found in selected namespace",
                }
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
            "project_resolution": {
                "status": "resolved",
                "project_uuid": "proj-123",
                "namespace": "auri",
                "namespace_provenance": "current_request",
            },
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
            "validation": [{"command": "mvn test", "status": "planned"}],
            "change_requests": [
                {
                    "status": "not_created",
                    "proposed_branch": "remediation/sca/demo-1.0.1",
                }
            ],
            "data_gaps": [],
        }
    )

    assert lint_agent_output("sca-remediation", output) == []


def test_lint_blocks_default_scan_recommendation_for_read_only_agents():
    errors = lint_agent_output(
        "vulnerability-explainer",
        "Run a new Endor scan, then I can explain the vulnerability.",
    )

    assert "read-only workflow must not recommend running a new Endor scan as the default next step" in errors


def test_extract_json_object_returns_last_json_object():
    assert extract_json_object('{"first": true}\nthen\n{"second": true}') == {"second": True}


def test_lint_agent_output_cli_reports_errors(tmp_path, capsys):
    output = tmp_path / "agent-output.txt"
    output.write_text("cat ~/.config/endorctl/config.yaml\n", encoding="utf-8")

    status = main(["lint-agent-output", "--agent", "sca-remediation", str(output)])
    captured = capsys.readouterr().out

    assert status == 1
    assert "unsafe Endor config read" in captured

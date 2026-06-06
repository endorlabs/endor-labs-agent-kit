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

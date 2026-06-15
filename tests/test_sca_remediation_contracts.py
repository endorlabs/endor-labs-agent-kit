from __future__ import annotations

import json

from endor_agent_kit.cli import main
from endor_agent_kit.sca_remediation import (
    lint_sca_pr_body,
    normalize_sca_branch,
    render_sca_pr_body,
    validate_sca_gate_payload,
)


def _valid_netty_payload() -> dict:
    return {
        "summary": "Gate 1 selection plan for netty-all.",
        "selected_remediation": {
            "package": "io.netty:netty-all",
            "from_version": "4.1.42.Final",
            "to_version": "4.2.13.Final",
            "upgrade_risk": "low",
            "cia_status": "indeterminate",
            "findings_fixed": 25,
            "findings_introduced": 0,
            "conflicts": 0,
            "uia_uuid": "version-upgrade-fixture-001",
            "project_uuid": "project-fixture-webapp-001",
            "namespace": "tenant-a",
            "manifests": ["services/api-gateway/pom.xml"],
            "reachability_tags": ["REACHABLE_DEPENDENCY", "REACHABLE_FUNCTION"],
            "advisories": [
                {
                    "cve": "CVE-2019-20444",
                    "ghsa": "GHSA-cqqj-4p63-rrmm",
                    "severity": "critical",
                    "title": "HTTP Request Smuggling in Netty",
                    "advisory_source": "Endor VersionUpgrade vuln_finding_info.fixed_findings",
                    "cve_mapping_source": "GitHub Advisory Database aliases",
                    "link_source": "GitHub Advisory Database",
                },
                {
                    "cve": "CVE-2021-21290",
                    "ghsa": "GHSA-5mcr-gq6c-3hq2",
                    "severity": "medium",
                    "title": "Local Information Disclosure in Netty",
                    "advisory_source": "Endor VersionUpgrade vuln_finding_info.fixed_findings",
                    "cve_mapping_source": "GitHub Advisory Database aliases",
                    "link_source": "GitHub Advisory Database",
                },
            ],
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-001",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Endor CIA is indeterminate; source usage is limited to declared netty-all dependency and requires dependency resolution plus service tests before PR.",
            "source_usage_summary": "Local source scan found no direct use of removed Netty 4.2 APIs; dependency is declared through netty.version.",
            "validation_requirements": [
                "mvn dependency:tree -Dincludes=io.netty:netty-all",
                "mvn test",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-001",
                "upgrade_risk": "low",
                "cia_status": "indeterminate",
                "findings_fixed": 25,
                "findings_introduced": 0,
            }
        ],
        "patch_plan": [
            {
                "file": "services/api-gateway/pom.xml",
                "branch_name": "remediation/sca/netty-all-4.2.13.Final",
            }
        ],
        "validation": [
            {
                "command": "mvn dependency:tree -Dincludes=io.netty:netty-all",
                "status": "planned",
                "purpose": "Confirm io.netty:netty-all resolves to 4.2.13.Final",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "branch": "not_created",
                "proposed_branch": "remediation/sca/netty-all-4.2.13.Final",
            }
        ],
    }


def test_sca_gate_validator_rejects_bad_netty_gate_one_output():
    payload = {
        "summary": "Low risk, zero conflicts, single property edit. AWAITING APPROVAL TO APPLY",
        "selected_remediation": {
            "package": "io.netty:netty-all",
            "from_version": "4.1.42.Final",
            "to_version": "4.2.13.Final",
            "upgrade_risk": "low",
            "cia_status": "indeterminate",
            "findings_fixed": 25,
            "findings_introduced": 0,
            "conflicts": 0,
        },
        "patch_plan": [{"branch_name": "endor/fix/netty-all-4.2.13.Final"}],
        "validation": [{"command": "mvn dependency:tree", "status": "planned"}],
    }

    errors = validate_sca_gate_payload(payload)

    assert "risk_decision: required object" in errors
    assert any("source_usage_summary" in error for error in errors)
    assert any("endor/fix" in error for error in errors)
    assert any("await apply approval" in error for error in errors)


def test_sca_gate_validator_requires_namespace_provenance():
    payload = _valid_netty_payload()
    payload["project_resolution"].pop("namespace_provenance")

    errors = validate_sca_gate_payload(payload)

    assert "project_resolution.namespace_provenance: required for SCA workflow gates" in errors


def test_sca_gate_validator_requires_project_resolution():
    payload = _valid_netty_payload()
    payload.pop("project_resolution")
    payload["selected_remediation"].pop("project_uuid")
    payload["selected_remediation"].pop("namespace")

    errors = validate_sca_gate_payload(payload)

    assert "project_resolution.status: required for SCA workflow gates" in errors
    assert "project_resolution.project_uuid: required for SCA workflow gates" in errors
    assert "project_resolution.namespace: required for SCA workflow gates" in errors
    assert "project_resolution.namespace_provenance: required for SCA workflow gates" in errors


def test_sca_gate_validator_requires_project_resolution_status():
    payload = _valid_netty_payload()
    payload["project_resolution"].pop("status")

    errors = validate_sca_gate_payload(payload)

    assert "project_resolution.status: required for SCA workflow gates" in errors


def test_sca_gate_validator_requires_branch_provenance_for_resolved_project():
    payload = _valid_netty_payload()
    payload["project_resolution"].pop("default_branch")

    errors = validate_sca_gate_payload(payload)

    assert (
        "project_resolution.default_branch: branch provenance required for SCA workflow gates"
        in errors
    )


def test_sca_gate_validator_accepts_explicit_unknown_branch_provenance():
    payload = _valid_netty_payload()
    payload["project_resolution"].pop("default_branch")
    payload["project_resolution"]["branch_provenance"] = "branch unknown: Project spec.git omitted"

    errors = validate_sca_gate_payload(payload)

    assert (
        "project_resolution.default_branch: branch provenance required for SCA workflow gates"
        not in errors
    )


def test_sca_gate_validator_requires_traverse_attempted_for_resolved_project():
    payload = _valid_netty_payload()
    payload["project_resolution"].pop("traverse_attempted")

    errors = validate_sca_gate_payload(payload)

    assert "project_resolution.traverse_attempted: required for SCA workflow gates" in errors


def test_sca_gate_validator_rejects_non_array_uia_evidence():
    payload = _valid_netty_payload()
    payload["uia_evidence"] = {"uuid": "version-upgrade-fixture-001"}

    errors = validate_sca_gate_payload(payload)

    assert "uia_evidence: must be an array" in errors


def test_sca_gate_validator_accepts_deterministic_netty_gate_one_output():
    assert validate_sca_gate_payload(_valid_netty_payload()) == []


def test_sca_gate_validator_accepts_unresolved_project_without_candidate():
    payload = {
        "summary": "Selection-plan gate blocked because no Endor project matched the repository.",
        "remediation_candidates": [],
        "project_resolution": {
            "status": "lookup_unavailable",
            "project_uuid": None,
            "namespace": "auri",
            "namespace_provenance": "current request",
            "repo_full_name": "endor-matt/ktor",
            "traverse_attempted": True,
        },
        "evidence_queries": [
            {
                "name": "project-lookup-traverse-fallback",
                "resource": "Project",
                "source": "endorctl_api",
                "status": "succeeded",
                "query_template_id": "project-by-repository",
                "filter_summary": "namespace=auri with child namespace traversal",
                "field_mask_summary": "uuid, meta.name, tenant_meta.namespace, spec.git",
                "result_count": 0,
                "reason": "No matching Project resources were returned.",
            }
        ],
        "selected_remediation": {
            "package": None,
            "from_version": None,
            "to_version": None,
            "branch_name": None,
            "manifest_files": [],
            "version_upgrade_uuid": None,
        },
        "uia_evidence": [],
        "risk_decision": {
            "status": "blocked_needs_compatibility_analysis",
            "source_usage_summary": "Not assessed because no UIA-backed package candidate was selected.",
            "validation_requirements": [],
            "reason": "Cannot select a remediation without resolved project scope.",
        },
        "patch_plan": [],
        "validation": [],
        "change_requests": [],
        "data_gaps": ["project_uuid_unavailable"],
    }

    assert validate_sca_gate_payload(payload) == []


def test_sca_gate_validator_ignores_runtime_base_branch_metadata():
    payload = _valid_netty_payload()
    payload["runtime_qa"] = {"branch": "main"}
    payload["change_requests"][0]["branch"] = "not_created"

    assert validate_sca_gate_payload(payload) == []


def test_sca_gate_validator_accepts_pr_e2e_change_request_branch_evidence():
    payload = _valid_netty_payload()
    payload["patch_plan"] = [{"file": "services/api-gateway/pom.xml"}]
    payload["change_requests"][0] = {
        "status": "reused",
        "base_branch": "main",
        "branch": "remediation/sca/netty-all-4.2.13.Final",
    }

    assert validate_sca_gate_payload(payload) == []


def test_sca_gate_validator_rejects_bad_pr_e2e_change_request_branch():
    payload = _valid_netty_payload()
    payload["patch_plan"] = [{"file": "services/api-gateway/pom.xml"}]
    payload["change_requests"][0] = {
        "status": "opened",
        "base_branch": "main",
        "branch": "endor/fix/netty-all-4.2.13.Final",
    }

    errors = validate_sca_gate_payload(payload)

    assert any("endor/fix" in error for error in errors)


def test_sca_pr_renderer_outputs_auri_style_body_and_lints_cleanly():
    body = render_sca_pr_body(_valid_netty_payload())

    assert "<!-- endor-agent-kit:sca-remediation-agent -->" in body
    assert "⚠️ Compatibility requires validation:" in body
    assert "### At a Glance" in body
    assert "📦 What changed?" in body
    assert "### 🧠 Why This Matters" in body
    assert "### 📦 Upgrade Applied" in body
    assert "<details><summary>Advisories This Upgrade Fixes (2)</summary>" in body
    assert "[CVE-2019-20444](https://github.com/advisories/GHSA-cqqj-4p63-rrmm): HTTP Request Smuggling in Netty (C) 🔴" in body
    assert "[CVE-2021-21290](https://github.com/advisories/GHSA-5mcr-gq6c-3hq2): Local Information Disclosure in Netty (M) 🟡" in body
    assert "#### Advisory Provenance" in body
    assert "- CVE-2019-20444: cve=CVE-2019-20444; ghsa=GHSA-cqqj-4p63-rrmm; advisory_source=Endor VersionUpgrade vuln_finding_info.fixed_findings; cve_mapping_source=GitHub Advisory Database aliases; link_source=GitHub Advisory Database" in body
    assert "### 🧪 Developer Validation" in body
    assert "### 🛡️ AppSec Validation" in body
    assert "### 📝 Reviewer Notes" in body
    assert "Generated by [Endor Labs SCA Remediation Agent](https://endor.ai)." in body
    assert "### Rollback" not in body
    assert "### Endor Evidence" not in body
    assert "**Critical**" not in body
    assert "**High**" not in body
    assert lint_sca_pr_body(body) == []


def test_sca_pr_linter_rejects_missing_suffix_and_ghsa_visible_text_when_cve_present():
    body = """<!-- endor-agent-kit:sca-remediation-agent -->
### At a Glance
### 🔎 Advisories This Upgrade Fixes
<details><summary>Advisories This Upgrade Fixes (1)</summary>

- [GHSA-cqqj-4p63-rrmm](https://github.com/advisories/GHSA-cqqj-4p63-rrmm): CVE-2019-20444 HTTP Request Smuggling in Netty

</details>
### 🧪 Developer Validation
### 🛡️ AppSec Validation
### 📝 Reviewer Notes
Generated by [Endor Labs SCA Remediation Agent](https://endor.ai).
### Rollback
### Endor Evidence
"""

    errors = lint_sca_pr_body(body)

    assert any("invalid format" in error for error in errors)


def test_sca_pr_linter_rejects_unfolded_or_open_advisory_details():
    body = """<!-- endor-agent-kit:sca-remediation-agent -->
### At a Glance
### 🔎 Advisories This Upgrade Fixes
<details open>
<summary>Advisories (1)</summary>

- [CVE-2019-20444](https://github.com/advisories/GHSA-cqqj-4p63-rrmm): HTTP Request Smuggling in Netty (C) 🔴

#### Advisory Provenance
- CVE-2019-20444: cve=CVE-2019-20444; ghsa=GHSA-cqqj-4p63-rrmm; advisory_source=Endor; cve_mapping_source=GitHub Advisory Database; link_source=GitHub Advisory Database

</details>
### 🧪 Developer Validation
### 🛡️ AppSec Validation
### 📝 Reviewer Notes
Generated by [Endor Labs SCA Remediation Agent](https://endor.ai).
### Rollback
### Endor Evidence
"""

    errors = lint_sca_pr_body(body)

    assert any("<details>, not <details open>" in error for error in errors)
    assert any("Advisories This Upgrade Fixes" in error for error in errors)


def test_sca_pr_linter_rejects_unclosed_fenced_blocks_and_missing_footer():
    body = """<!-- endor-agent-kit:sca-remediation-agent -->
### At a Glance
```diff
- old
+ new
### 🔎 Advisories This Upgrade Fixes
<details><summary>Advisories This Upgrade Fixes (1)</summary>

- [CVE-2019-20444](https://github.com/advisories/GHSA-cqqj-4p63-rrmm): HTTP Request Smuggling in Netty (C) 🔴

#### Advisory Provenance
- CVE-2019-20444: cve=CVE-2019-20444; ghsa=GHSA-cqqj-4p63-rrmm; advisory_source=Endor; cve_mapping_source=GitHub Advisory Database; link_source=GitHub Advisory Database

</details>
### 🧪 Developer Validation
### 🛡️ AppSec Validation
### 📝 Reviewer Notes
### Rollback
### Endor Evidence
"""

    errors = lint_sca_pr_body(body)

    assert "unclosed fenced code block" in errors
    assert "missing generated-by footer" in errors


def test_sca_pr_linter_requires_advisory_provenance():
    body = """<!-- endor-agent-kit:sca-remediation-agent -->
### At a Glance
### 🔎 Advisories This Upgrade Fixes
<details><summary>Advisories This Upgrade Fixes (1)</summary>

- [CVE-2019-20444](https://github.com/advisories/GHSA-cqqj-4p63-rrmm): HTTP Request Smuggling in Netty (C) 🔴

</details>
### 🧪 Developer Validation
### 🛡️ AppSec Validation
### 📝 Reviewer Notes
Generated by [Endor Labs SCA Remediation Agent](https://endor.ai).
### Rollback
### Endor Evidence
"""

    errors = lint_sca_pr_body(body)

    assert "advisory provenance section required" in errors


def test_sca_cli_validate_output_and_render_pr_body(tmp_path, capsys):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(_valid_netty_payload()), encoding="utf-8")

    assert main(["validate-sca-output", str(payload_path)]) == 0
    output = capsys.readouterr().out
    assert f"OK: {payload_path}" in output

    assert main(["render-sca-pr-body", str(payload_path)]) == 0
    body = capsys.readouterr().out
    assert "Security Remediation: 25 Endor finding instances fixed" in body
    assert lint_sca_pr_body(body) == []


def test_sca_branch_normalizer_uses_remediation_sca_prefix():
    assert normalize_sca_branch("io.netty:netty-all", "4.2.13.Final") == "remediation/sca/netty-all-4.2.13.Final"
    assert normalize_sca_branch("npm://axios", "1.16.1") == "remediation/sca/axios-1.16.1"

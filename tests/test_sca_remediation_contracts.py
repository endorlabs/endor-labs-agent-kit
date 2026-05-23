from __future__ import annotations

import json

from endor_agent_kit.cli import main
from endor_agent_kit.install import check_claude_code_install
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
            "uia_uuid": "69fcb3fb719017e91f35c5ff",
            "project_uuid": "69d31cfb4d93d8d6a8408210",
            "namespace": "auri",
            "manifests": ["services/imperial-gateway/pom.xml"],
            "reachability_tags": ["REACHABLE_DEPENDENCY", "REACHABLE_FUNCTION"],
            "advisories": [
                {
                    "cve": "CVE-2019-20444",
                    "ghsa": "GHSA-cqqj-4p63-rrmm",
                    "severity": "critical",
                    "title": "HTTP Request Smuggling in Netty",
                },
                {
                    "cve": "CVE-2021-21290",
                    "ghsa": "GHSA-5mcr-gq6c-3hq2",
                    "severity": "medium",
                    "title": "Local Information Disclosure in Netty",
                },
            ],
        },
        "project_resolution": {
            "project_uuid": "69d31cfb4d93d8d6a8408210",
            "namespace": "auri",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "endor-matt/death-star",
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
        "patch_plan": [
            {
                "file": "services/imperial-gateway/pom.xml",
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

    assert "project_resolution.project_uuid: required for SCA workflow gates" in errors
    assert "project_resolution.namespace: required for SCA workflow gates" in errors
    assert "project_resolution.namespace_provenance: required for SCA workflow gates" in errors


def test_sca_gate_validator_accepts_deterministic_netty_gate_one_output():
    assert validate_sca_gate_payload(_valid_netty_payload()) == []


def test_sca_pr_renderer_outputs_auri_style_body_and_lints_cleanly():
    body = render_sca_pr_body(_valid_netty_payload())

    assert "<!-- endor-agent-kit:sca-remediation-agent -->" in body
    assert "### At a Glance" in body
    assert "<details><summary>Advisories This Upgrade Fixes (2)</summary>" in body
    assert "[CVE-2019-20444](https://github.com/advisories/GHSA-cqqj-4p63-rrmm): HTTP Request Smuggling in Netty (C) 🔴" in body
    assert "[CVE-2021-21290](https://github.com/advisories/GHSA-5mcr-gq6c-3hq2): Local Information Disclosure in Netty (M) 🟡" in body
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
### Validation Plan
### Rollback
### Endor Evidence
"""

    errors = lint_sca_pr_body(body)

    assert any("invalid format" in error for error in errors)


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


def test_check_install_detects_stale_repo_level_agent(tmp_path):
    catalog_agent = tmp_path / "catalog" / "claude-code" / "sca-remediation-agent"
    catalog_agent.mkdir(parents=True)
    (catalog_agent / "sca-remediation-agent.md").write_text("current", encoding="utf-8")
    installed_agent = tmp_path / "repo" / ".claude" / "agents"
    installed_agent.mkdir(parents=True)
    (installed_agent / "sca-remediation-agent.md").write_text("old", encoding="utf-8")

    errors = check_claude_code_install(
        "sca-remediation-agent",
        tmp_path / "repo",
        catalog_root=tmp_path / "catalog",
    )

    assert any("is stale" in error for error in errors)

    (installed_agent / "sca-remediation-agent.md").write_text("current", encoding="utf-8")
    assert check_claude_code_install(
        "sca-remediation-agent",
        tmp_path / "repo",
        catalog_root=tmp_path / "catalog",
    ) == []


def test_sca_cli_check_install(tmp_path, capsys):
    catalog_agent = tmp_path / "catalog" / "claude-code" / "sca-remediation-agent"
    catalog_agent.mkdir(parents=True)
    (catalog_agent / "sca-remediation-agent.md").write_text("current", encoding="utf-8")
    installed_agent = tmp_path / "repo" / ".claude" / "agents"
    installed_agent.mkdir(parents=True)
    (installed_agent / "sca-remediation-agent.md").write_text("current", encoding="utf-8")

    assert main([
        "check-install",
        "--agent",
        "sca-remediation-agent",
        "--repo",
        str(tmp_path / "repo"),
        "--catalog-root",
        str(tmp_path / "catalog"),
    ]) == 0
    assert "OK:" in capsys.readouterr().out

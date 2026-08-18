from __future__ import annotations

import json

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.policy_pack import (
    evaluate_policy_pack_file,
    load_policy_pack,
    policy_pack_sha256,
)
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
            "finding_instances_fixed": 25,
            "unique_advisories_fixed": 2,
            "fixed_finding_uuids": [
                "6a60c9445beb5fb713450060",
                "6a60c944ecffc5da2e6ab9ff",
            ],
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
                "finding_instances_fixed": 25,
                "unique_advisories_fixed": 2,
                "fixed_finding_uuids": [
                    "6a60c9445beb5fb713450060",
                    "6a60c944ecffc5da2e6ab9ff",
                ],
                "findings_introduced": 0,
            }
        ],
        "dependency_graph_audit": {
            "package_manager": "maven",
            "status": "clear",
            "manifest": "services/api-gateway/pom.xml",
            "dependency_path": ["io.netty:netty-all"],
            "manipulations": [
                {
                    "type": "version_property",
                    "coordinate": "io.netty:netty-all",
                    "classification": "version_control",
                    "replacement": None,
                    "evidence": ["netty.version controls the selected package"],
                }
            ],
            "validation_requirements": [],
        },
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
                "inventory": {
                    "status": "none_found",
                    "lookup_method": "source provider branch and change-request inventory",
                    "checked_at": "2026-07-20T12:00:00Z",
                    "fresh_recheck": False,
                    "key": {
                        "repository": "example/webapp",
                        "base_branch": "main",
                        "ecosystem": "maven",
                        "normalized_package": "io.netty-netty-all",
                        "manifest": "services/api-gateway/pom.xml",
                        "current_version": "4.1.42.Final",
                        "target_version": "4.2.13.Final",
                        "finding_set": [],
                    },
                    "candidates": [],
                    "reconciliation": {
                        "status": "not_needed",
                        "reason": "No existing candidate found.",
                        "selected_target_version": "4.2.13.Final",
                        "uia_evidence_checked_at": "2026-07-20T12:00:00Z",
                        "upstream_evidence_checked_at": "2026-07-20T12:00:00Z",
                        "operator_choice_required": False,
                    },
                },
            }
        ],
        "policy_context": {
            "status": "not_configured",
            "pack_id": None,
            "pack_version": None,
            "sha256": None,
            "source": None,
        },
        "policy_evaluations": [],
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


def test_sca_selection_requires_maven_dependency_graph_audit():
    payload = _valid_netty_payload()
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected Maven remediations"
        in errors
    )


def test_sca_maven_dependency_graph_audit_must_match_selected_manifest():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["manifest"] = "services/unrelated/pom.xml"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.manifest: must match a selected remediation manifest"
        in errors
    )


def test_sca_maven_unverified_exclusion_blocks_approved_decision():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "blocked",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "unverified",
                "replacement": None,
                "evidence": ["excluded on the selected dependency path"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: blocked Maven dependency graph audit cannot accompany an approved decision"
        in errors
    )


def test_sca_maven_audit_status_cannot_hide_unverified_exclusion():
    payload = _valid_netty_payload()
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "clear",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "unverified",
                "replacement": None,
                "evidence": ["excluded on the selected dependency path"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Maven exclusions require blocked"
        in errors
    )


def test_sca_maven_declared_replacement_requires_validation_before_low_risk():
    payload = _valid_netty_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "validation_required",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "replacement_declared",
                "replacement": "org.slf4j:jcl-over-slf4j",
                "evidence": ["replacement dependency declared in the affected module"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }
    payload["validation"] = [
        {"kind": "resolved_graph", "status": "passed", "command": "mvn dependency:tree"},
        {"kind": "runtime_linkage", "status": "passed", "command": "mvn test"},
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: Maven graph manipulation awaiting validation cannot be approved_low_risk"
        in errors
    )


def test_sca_maven_declared_replacement_requires_validation_required_status():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "clear",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "replacement_declared",
                "replacement": "org.slf4j:jcl-over-slf4j",
                "evidence": ["replacement dependency declared in the affected module"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared Maven replacements require validation_required"
        in errors
    )


def test_sca_maven_declared_replacement_requires_graph_and_runtime_validation_plan():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "validation_required",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "replacement_declared",
                "replacement": "org.slf4j:jcl-over-slf4j",
                "evidence": ["replacement dependency declared in the affected module"],
            }
        ],
        "validation_requirements": ["resolved_graph"],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.validation_requirements: Maven exclusions require resolved_graph and runtime_linkage"
        in errors
    )


def test_sca_maven_audit_identifies_maven_package_manager():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["package_manager"] = "gradle"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert "dependency_graph_audit.package_manager: must be maven" in errors


def test_sca_maven_direct_override_cannot_masquerade_as_native_version_control():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        {
            "type": "direct_dependency_override",
            "coordinate": "io.netty:netty-all",
            "classification": "version_control",
            "replacement": None,
            "evidence": ["direct parent dependency forces the transitive version"],
        }
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.manipulations[0].classification: direct Maven overrides require mediation evidence"
        in errors
    )


def test_sca_maven_declared_direct_override_requires_validation():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "clear",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all"],
        "manipulations": [
            {
                "type": "direct_dependency_override",
                "coordinate": "io.netty:netty-all",
                "classification": "mediation_declared",
                "replacement": None,
                "evidence": ["no project-native version control exists"],
            }
        ],
        "validation_requirements": [],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared Maven graph mediation requires validation_required"
        in errors
    )
    assert (
        "dependency_graph_audit.validation_requirements: Maven graph manipulations require resolved_graph and runtime_linkage"
        in errors
    )


def test_sca_maven_verified_direct_override_requires_validated_status():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "clear",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all"],
        "manipulations": [
            {
                "type": "direct_dependency_override",
                "coordinate": "io.netty:netty-all",
                "classification": "mediation_verified",
                "replacement": None,
                "evidence": ["filtered graph and targeted runtime validation passed"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: verified Maven graph mediation requires validated"
        in errors
    )


def test_sca_maven_declared_replacement_requires_exact_coordinate():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "validation_required",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "replacement_declared",
                "replacement": None,
                "evidence": ["manifest comment says logging is replaced"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.manipulations[0].replacement: required for replacement_declared"
        in errors
    )


def test_sca_maven_validated_replacement_requires_graph_and_runtime_evidence():
    payload = _valid_netty_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "validated",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "replacement_verified",
                "replacement": "org.slf4j:jcl-over-slf4j",
                "evidence": ["replacement dependency declared in the affected module"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }
    payload["validation"] = [
        {"kind": "resolved_graph", "status": "passed", "command": "mvn dependency:tree"},
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: validated Maven exclusions require passed resolved_graph and runtime_linkage validation"
        in errors
    )


def test_sca_maven_dependency_graph_audit_is_bounded():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "clear",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all"],
        "manipulations": [
            {
                "type": "version_property",
                "coordinate": f"io.netty:netty-module-{index}",
                "classification": "version_control",
                "replacement": None,
                "evidence": ["managed by the selected version property"],
            }
            for index in range(9)
        ],
        "validation_requirements": [],
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert "dependency_graph_audit.manipulations: must contain at most 8 entries" in errors


def test_sca_maven_unavailable_audit_cannot_be_low_risk():
    payload = _valid_netty_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "unavailable",
        "manifest": None,
        "dependency_path": [],
        "manipulations": [],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }
    payload["validation"] = [
        {"kind": "resolved_graph", "status": "passed", "command": "mvn dependency:tree"},
        {"kind": "runtime_linkage", "status": "passed", "command": "mvn test"},
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable Maven dependency graph audit cannot be approved_low_risk"
        in errors
    )


def test_sca_maven_verified_replacement_accepts_low_risk_after_graph_and_runtime_validation():
    payload = _valid_netty_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"] = {
        "package_manager": "maven",
        "status": "validated",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": "replacement_verified",
                "replacement": "org.slf4j:jcl-over-slf4j",
                "evidence": ["replacement dependency declared in the affected module"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }
    payload["validation"] = [
        {"kind": "resolved_graph", "status": "passed", "command": "mvn dependency:tree"},
        {"kind": "runtime_linkage", "status": "passed", "command": "mvn test"},
    ]

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_sca_selection_gate_accepts_profile_projected_plan_without_apply_fields():
    payload = _valid_netty_payload()
    payload.pop("patch_plan")
    payload.pop("validation")

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_sca_duplicate_inventory_allows_plan_but_fails_closed_before_pr_when_unavailable():
    payload = _valid_netty_payload()
    inventory = payload["change_requests"][0]["inventory"]
    inventory["status"] = "unavailable"
    inventory["reconciliation"]["status"] = "lookup_unavailable"

    assert not any(
        "fails closed before push/open" in error
        for error in validate_sca_gate_payload(payload, gate="selection-plan")
    )

    payload["pr_body"] = render_sca_pr_body(payload)
    errors = validate_sca_gate_payload(payload, gate="pr")
    assert "change_requests[0].inventory: unavailable inventory fails closed before push/open" in errors


def test_sca_duplicate_inventory_reuses_exact_duplicate_and_blocks_new_creation():
    payload = _valid_netty_payload()
    request = payload["change_requests"][0]
    inventory = request["inventory"]
    inventory["status"] = "exact_duplicate"
    inventory["candidates"] = [
        {
            "author": "dependabot[bot]",
            "author_type": "bot",
            "branch": "remediation/sca/netty-all-4.2.13.Final",
            "state": "open",
            "files": ["services/api-gateway/pom.xml"],
            "url": "https://example.invalid/pr/42",
            "current_version": "4.1.42.Final",
            "target_version": "4.2.13.Final",
            "exact_duplicate": True,
        }
    ]
    inventory["reconciliation"]["status"] = "reuse_existing"
    request["status"] = "created"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")
    assert "change_requests[0].inventory: exact duplicate must be reused or block creation" in errors


def test_sca_duplicate_inventory_allows_unknown_versions_only_on_non_exact_overlap():
    payload = _valid_netty_payload()
    request = payload["change_requests"][0]
    inventory = request["inventory"]
    inventory["status"] = "exact_duplicate"
    inventory["candidates"] = [
        {
            "author": "dependabot[bot]",
            "author_type": "bot",
            "branch": "remediation/sca/netty-all-4.2.13.Final",
            "state": "open",
            "files": ["services/api-gateway/pom.xml"],
            "url": "https://example.invalid/pr/42",
            "current_version": "4.1.42.Final",
            "target_version": "4.2.13.Final",
            "exact_duplicate": True,
        },
        {
            "author": "renovate[bot]",
            "author_type": "bot",
            "branch": "renovate/other-manifest-change",
            "state": "open",
            "files": ["services/api-gateway/pom.xml"],
            "url": "https://example.invalid/pr/43",
            "current_version": None,
            "target_version": None,
            "exact_duplicate": False,
        },
    ]
    inventory["reconciliation"]["status"] = "reuse_existing"
    request["status"] = "not_created"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert not any("candidates[1]" in error for error in errors)

    inventory["candidates"][0]["current_version"] = None
    errors = validate_sca_gate_payload(payload, gate="selection-plan")
    assert (
        "change_requests[0].inventory.candidates[0].current_version: required for exact duplicate"
        in errors
    )


def test_sca_inventory_rejects_candidate_without_selected_manifest_overlap():
    payload = _valid_netty_payload()
    inventory = payload["change_requests"][0]["inventory"]
    inventory["status"] = "exact_duplicate"
    inventory["candidates"] = [
        {
            "author": "dependabot[bot]",
            "author_type": "bot",
            "branch": "remediation/sca/netty-all-4.2.13.Final",
            "state": "open",
            "files": ["services/api-gateway/pom.xml"],
            "url": "https://example.invalid/pr/42",
            "current_version": "4.1.42.Final",
            "target_version": "4.2.13.Final",
            "exact_duplicate": True,
        },
        {
            "author": "security-team",
            "author_type": "human",
            "branch": "fix/unrelated-sast",
            "state": "open",
            "files": ["src/main/java/example/Controller.java"],
            "url": "https://example.invalid/pr/99",
            "current_version": None,
            "target_version": None,
            "exact_duplicate": False,
        },
    ]
    inventory["reconciliation"]["status"] = "reuse_existing"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.candidates[1].files: must overlap a selected remediation manifest"
        in errors
    )


def test_sca_different_target_requires_fresh_reconciliation_or_operator_choice():
    payload = _valid_netty_payload()
    inventory = payload["change_requests"][0]["inventory"]
    inventory["status"] = "different_target"
    inventory["candidates"] = [
        {
            "author": "dependabot[bot]",
            "author_type": "bot",
            "branch": "dependabot/cryptography-49",
            "state": "open",
            "files": ["requirements.txt"],
            "url": "https://example.invalid/pr/49",
            "current_version": "47.0.0",
            "target_version": "49.0.0",
            "exact_duplicate": False,
        }
    ]
    inventory["reconciliation"] = {
        "status": "operator_choice_required",
        "reason": "Agent selected 47.0.0 while the bot proposed 49.0.0.",
        "selected_target_version": "4.2.13.Final",
        "uia_evidence_checked_at": None,
        "upstream_evidence_checked_at": None,
        "operator_choice_required": True,
    }

    errors = validate_sca_gate_payload(payload, gate="selection-plan")
    assert "change_requests[0].inventory.reconciliation: unresolved target divergence requires operator choice" in errors


def test_sca_gate_validator_rejects_approved_remediation_blocked_by_policy():
    payload = _valid_netty_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["policy_context"] = {
        "status": "loaded",
        "pack_id": "websphere-traditional-java8",
        "pack_version": "2026.07.02",
        "sha256": "abc123",
        "source": "runtime",
    }
    payload["policy_evaluations"] = [
        {
            "policy_id": "was-traditional-java-max-8",
            "effect": "deny",
            "decision": "blocked",
            "message": "Do not recommend Java 9+.",
            "facts_used": ["proposed.runtime.java.major"],
            "missing_facts": [],
        }
    ]

    errors = validate_sca_gate_payload(payload)

    assert (
        "policy_evaluations: blocking policy decision cannot accompany approved risk_decision"
        in errors
    )


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


def test_sca_gate_validator_rejects_non_array_validation():
    payload = _valid_netty_payload()
    payload["validation"] = {"status": "not_run"}

    errors = validate_sca_gate_payload(payload)

    assert "validation: must be an array" in errors


def test_sca_gate_validator_accepts_deterministic_netty_gate_one_output():
    assert validate_sca_gate_payload(_valid_netty_payload()) == []


def test_sca_selection_gate_requires_distinct_instance_and_advisory_counts():
    payload = _valid_netty_payload()
    payload["selected_remediation"].pop("unique_advisories_fixed")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "selected_remediation.unique_advisories_fixed: required non-negative integer"
        in errors
    )


def test_sca_selection_gate_rejects_count_or_uuid_drift_from_uia_evidence():
    payload = _valid_netty_payload()
    payload["uia_evidence"][0]["finding_instances_fixed"] = 26
    payload["uia_evidence"][0]["fixed_finding_uuids"] = ["different-finding"]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert "uia_evidence[0].finding_instances_fixed: must match selected remediation" in errors
    assert "uia_evidence[0].fixed_finding_uuids: must match selected remediation" in errors


def test_sca_selection_gate_rejects_malformed_or_duplicate_fixed_uuid():
    payload = _valid_netty_payload()
    payload["selected_remediation"]["fixed_finding_uuids"][0] = "not-an-endor-uuid"
    payload["uia_evidence"][0]["fixed_finding_uuids"][0] = "not-an-endor-uuid"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("24 lowercase hexadecimal" in error for error in errors)

    payload = _valid_netty_payload()
    repeated = payload["selected_remediation"]["fixed_finding_uuids"][0]
    payload["selected_remediation"]["fixed_finding_uuids"] = [repeated, repeated]
    payload["uia_evidence"][0]["fixed_finding_uuids"] = [repeated, repeated]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert "selected_remediation.fixed_finding_uuids: UUIDs must be unique" in errors


def test_sca_low_risk_approval_requires_successful_targeted_validation():
    payload = _valid_netty_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("approved_low_risk requires successful targeted validation" in error for error in errors)

    payload["validation"][0]["status"] = "passed"
    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_sca_inventory_status_matches_candidate_classification():
    payload = _valid_netty_payload()
    inventory = payload["change_requests"][0]["inventory"]
    inventory["status"] = "different_target"
    inventory["candidates"] = [
        {
            "author": "renovate[bot]",
            "author_type": "bot",
            "branch": "renovate/netty-all-4.2.13.Final",
            "state": "open",
            "files": ["services/api-gateway/pom.xml"],
            "url": "https://example.invalid/pr/51",
            "current_version": "4.1.42.Final",
            "target_version": "4.2.13.Final",
            "exact_duplicate": True,
        }
    ]
    inventory["reconciliation"]["status"] = "resolved"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert "change_requests[0].inventory.status: exact matching candidate must use exact_duplicate" in errors


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
                "source": "endorctl_agent_api",
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
    inventory = payload["change_requests"][0]["inventory"]
    payload["change_requests"][0] = {
        "status": "reused",
        "base_branch": "main",
        "branch": "remediation/sca/netty-all-4.2.13.Final",
        "inventory": inventory,
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


def test_sca_pr_linter_accepts_endor_labs_site_footer_variant():
    body = render_sca_pr_body(_valid_netty_payload()).replace(
        "Generated by [Endor Labs SCA Remediation Agent](https://endor.ai).",
        "Generated by the [Endor Labs SCA Remediation Agent](https://www.endorlabs.com/) via Endor Agent Kit.",
    )

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


def test_sca_cli_recomputes_policy_decisions_from_trusted_facts(tmp_path, capsys):
    policy_path = repo_root() / "policy-packs" / "examples" / "was-traditional-java8.yaml"
    policy_pack = load_policy_pack(policy_path)
    facts_path = tmp_path / "policy-facts.json"
    facts = {
        "agent": {"id": "sca-remediation"},
        "ecosystem": "maven",
        "platform": {"websphere": {"family": "traditional", "present": True}},
        "proposed": {"runtime": {"java": {"major": 17}}},
    }
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    payload = _valid_netty_payload()
    payload["policy_context"] = {
        "status": "loaded",
        "pack_id": policy_pack["id"],
        "pack_version": policy_pack["version"],
        "sha256": policy_pack_sha256(policy_path),
        "source": "runtime",
    }
    payload["policy_evaluations"] = [
        {
            "policy_id": "was-traditional-java-max-8",
            "effect": "deny",
            "decision": "passed",
            "message": policy_pack["policies"][0]["message"],
            "facts_used": [
                "platform.websphere.family",
                "platform.websphere.present",
                "proposed.runtime.java.major",
            ],
            "missing_facts": [],
        }
    ]
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(
        [
            "validate-sca-output",
            str(payload_path),
            "--gate",
            "apply",
            "--policy-pack",
            str(policy_path),
            "--policy-facts",
            str(facts_path),
        ]
    ) == 1
    output = capsys.readouterr().out

    assert "decision: must match trusted policy evaluation 'blocked'" in output

    facts["proposed"]["runtime"]["java"]["major"] = 8
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    payload["policy_evaluations"] = evaluate_policy_pack_file(policy_path, facts)
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(
        [
            "validate-sca-output",
            str(payload_path),
            "--gate",
            "apply",
            "--policy-pack",
            str(policy_path),
            "--policy-facts",
            str(facts_path),
        ]
    ) == 0


def test_sca_cli_rejects_policy_facts_without_policy_pack(tmp_path, capsys):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(_valid_netty_payload()), encoding="utf-8")
    facts_path = tmp_path / "policy-facts.json"
    facts_path.write_text("{}", encoding="utf-8")

    assert main(
        [
            "validate-sca-output",
            str(payload_path),
            "--policy-facts",
            str(facts_path),
        ]
    ) == 1

    assert "--policy-facts requires --policy-pack" in capsys.readouterr().out


def test_sca_cli_reports_malformed_policy_yaml_without_traceback(tmp_path, capsys):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(_valid_netty_payload()), encoding="utf-8")
    policy_path = tmp_path / "bad-policy.yaml"
    policy_path.write_text("policies: [", encoding="utf-8")
    facts_path = tmp_path / "policy-facts.json"
    facts_path.write_text("{}", encoding="utf-8")

    status = main(
        [
            "validate-sca-output",
            str(payload_path),
            "--gate",
            "apply",
            "--policy-pack",
            str(policy_path),
            "--policy-facts",
            str(facts_path),
        ]
    )

    assert status == 1
    assert "ERROR: policy_pack: invalid YAML:" in capsys.readouterr().out


def test_sca_cli_preflights_policy_applicability_facts(tmp_path, capsys):
    policy_path = repo_root() / "policy-packs" / "examples" / "was-traditional-java8.yaml"
    policy_pack = load_policy_pack(policy_path)
    facts = {
        "agent": {"id": "sca-remediation"},
        "ecosystem": "maven",
        "proposed": {"runtime": {"java": {"major": 17}}},
    }
    facts_path = tmp_path / "policy-facts.json"
    facts_path.write_text(json.dumps(facts), encoding="utf-8")
    payload = _valid_netty_payload()
    payload["policy_context"] = {
        "status": "loaded",
        "pack_id": policy_pack["id"],
        "pack_version": policy_pack["version"],
        "sha256": policy_pack_sha256(policy_path),
        "source": "runtime",
    }
    payload["policy_evaluations"] = evaluate_policy_pack_file(policy_path, facts)
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")

    status = main(
        [
            "validate-sca-output",
            str(payload_path),
            "--gate",
            "apply",
            "--policy-pack",
            str(policy_path),
            "--policy-facts",
            str(facts_path),
        ]
    )

    assert status == 1
    assert "applicability: missing trusted facts" in capsys.readouterr().out


def _bare_exclusion_audit(classification: str | None) -> dict:
    return {
        "package_manager": "maven",
        "status": "clear",
        "manifest": "services/api-gateway/pom.xml",
        "dependency_path": ["io.netty:netty-all", "commons-logging:commons-logging"],
        "manipulations": [
            {
                "type": "exclusion",
                "coordinate": "commons-logging:commons-logging",
                "classification": classification,
                "replacement": None,
                "evidence": ["excluded on the selected dependency path"],
            }
        ],
        "validation_requirements": ["resolved_graph", "runtime_linkage"],
    }


def test_sca_maven_exclusion_rejects_relabeled_classifications():
    for classification in ("version_control", "mediation_declared", "mediation_verified", None):
        payload = _valid_netty_payload()
        payload["dependency_graph_audit"] = _bare_exclusion_audit(classification)

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "classification: Maven exclusions require" in error for error in errors
        ), f"exclusion classification {classification!r} escaped the whitelist"


def test_sca_maven_not_needed_verified_exclusion_requires_validated_evidence():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = _bare_exclusion_audit("not_needed_verified")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: verified not-needed Maven exclusions require validated"
        in errors
    )

    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = _bare_exclusion_audit("not_needed_verified")
    payload["dependency_graph_audit"]["status"] = "validated"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: validated Maven exclusions require passed resolved_graph and runtime_linkage validation"
        in errors
    )


def test_sca_maven_audit_status_must_be_recognized():
    for status in (None, "Unavailable", "ok", ""):
        payload = _valid_netty_payload()
        payload["dependency_graph_audit"]["status"] = status

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            error.startswith("dependency_graph_audit.status: must be one of")
            for error in errors
        ), f"audit status {status!r} was not rejected"


def test_sca_maven_audit_required_when_ecosystem_token_drifts():
    for ecosystem in ("java", "mvn", "ECOSYSTEM_MAVEN", "Maven Central"):
        payload = _valid_netty_payload()
        payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = ecosystem
        payload.pop("dependency_graph_audit")

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert (
            "dependency_graph_audit: required for selected Maven remediations" in errors
        ), f"ecosystem {ecosystem!r} silently disabled the Maven audit"


def test_sca_maven_ecosystem_token_must_be_canonical():
    payload = _valid_netty_payload()
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "mvn"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be maven for Maven remediations"
        in errors
    )


def test_sca_maven_manipulation_type_must_be_recognized():
    for manipulation_type in (None, "resolution_strategy", ""):
        payload = _valid_netty_payload()
        payload["dependency_graph_audit"]["manipulations"][0]["type"] = manipulation_type

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].type: must be one of" in error for error in errors
        ), f"manipulation type {manipulation_type!r} was not rejected"


def test_sca_maven_native_manipulation_requires_version_control_classification():
    for manipulation_type in ("version_property", "dependency_management", "bom"):
        payload = _valid_netty_payload()
        manipulation = payload["dependency_graph_audit"]["manipulations"][0]
        manipulation["type"] = manipulation_type
        manipulation["classification"] = "mediation_declared"

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "classification: native Maven controls require version_control" in error
            for error in errors
        ), f"native type {manipulation_type!r} accepted a mediation classification"


def test_sca_maven_audit_caps_enforced_at_gate():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["dependency_path"] = [
        f"group:artifact-{index}" for index in range(13)
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert "dependency_graph_audit.dependency_path: must contain at most 12 entries" in errors

    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["evidence"] = [
        f"evidence item {index}" for index in range(4)
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].evidence: must contain at most 3 entries" in error for error in errors
    )

    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
        "mvn_test",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.validation_requirements: must contain at most 2 entries drawn from resolved_graph and runtime_linkage"
        in errors
    )


def test_sca_maven_listed_manipulation_counts_even_if_claimed_off_path():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = _bare_exclusion_audit("unverified")
    payload["dependency_graph_audit"]["dependency_path"] = ["io.netty:netty-all"]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Maven exclusions require blocked"
        in errors
    )


def test_sca_selection_blocked_flow_accepts_null_target_without_branch_or_counts():
    payload = _valid_netty_payload()
    payload["selected_remediation"] = {
        "package": "org.apache.httpcomponents:httpclient",
        "from_version": "4.3.6",
        "to_version": None,
        "selection_blocked": True,
    }
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["patch_plan"] = []
    payload["validation"] = []
    payload["change_requests"][0]["proposed_branch"] = "not_created"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert not any("branch_name" in error for error in errors)
    assert not any("finding_instances_fixed" in error for error in errors)
    assert not any("target_version" in error for error in errors)


def test_sca_selection_blocked_cannot_accompany_approval_or_created_change_request():
    payload = _valid_netty_payload()
    payload["selected_remediation"]["selection_blocked"] = True

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: selection_blocked cannot accompany an approved decision"
        in errors
    )

    payload = _valid_netty_payload()
    payload["selected_remediation"]["selection_blocked"] = True
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["change_requests"][0]["status"] = "created"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests: selection_blocked cannot accompany a created or reused change request"
        in errors
    )


def test_sca_selection_blocked_audit_is_still_validated_when_present():
    payload = _valid_netty_payload()
    payload["selected_remediation"] = {
        "package": None,
        "from_version": None,
        "to_version": None,
        "selection_blocked": True,
    }
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"] = _bare_exclusion_audit("unverified")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Maven exclusions require blocked"
        in errors
    )


def test_sca_maven_audit_containers_must_be_arrays():
    for field_name, value in (
        ("manipulations", {"0": {"type": "exclusion"}}),
        ("dependency_path", "io.netty:netty-all -> commons-logging"),
        ("validation_requirements", "resolved_graph"),
    ):
        payload = _valid_netty_payload()
        payload["dependency_graph_audit"][field_name] = value

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            f"dependency_graph_audit.{field_name}: must be an array" in error
            for error in errors
        ), f"non-list {field_name} was coerced silently"

    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["evidence"] = "prose evidence"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].evidence: must be an array" in error for error in errors)


def test_sca_maven_ecosystem_case_and_prefix_variants_are_not_canonical():
    for token in ("Maven", "MAVEN", "ECOSYSTEM_MAVEN"):
        payload = _valid_netty_payload()
        payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = token

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert (
            "change_requests[0].inventory.key.ecosystem: must be maven for Maven remediations"
            in errors
        ), f"ecosystem variant {token!r} passed as canonical"


def test_sca_selected_option_maven_signals_require_audit():
    payload = _valid_netty_payload()
    payload["selected_option"] = payload.pop("selected_remediation")
    payload.pop("dependency_graph_audit")
    key = payload["change_requests"][0]["inventory"]["key"]
    key["ecosystem"] = "java"
    key["manifest"] = "services/api-gateway/build.txt"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected Maven remediations" in errors
    ), "pom.xml manifests in selected_option escaped Maven detection"


def test_sca_inventory_non_dict_candidates_produce_clean_errors():
    payload = _valid_netty_payload()
    inventory = payload["change_requests"][0]["inventory"]
    inventory["status"] = "exact_duplicate"
    inventory["candidates"] = ["not-an-object", 7]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("candidates[0]: must be an object" in error for error in errors)


def test_sca_deeply_nested_payload_does_not_hit_recursion_limit():
    payload = _valid_netty_payload()
    deep: dict = {}
    node = deep
    for _ in range(5000):
        node["child"] = {}
        node = node["child"]
    payload["metadata_blob"] = deep

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert isinstance(errors, list)


def test_sca_text_coercion_survives_non_serializable_values():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["manifest"] = {1: "x", "a": object()}

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert isinstance(errors, list)


def test_sca_maven_semantic_effect_must_match_manipulation_type():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "forced_version_mediation"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].semantic_effect: must be native_version_control" in error for error in errors
    )

    payload = _valid_netty_payload()
    payload["dependency_graph_audit"] = _bare_exclusion_audit("unverified")
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "native_version_control"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].semantic_effect: must be dependency_removal or dependency_substitution"
        in error
        for error in errors
    )


def test_sca_maven_mechanism_must_match_manipulation_type():
    payload = _valid_netty_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "maven.bom"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: must be maven.version_property" in error for error in errors
    )


def test_sca_maven_valid_semantic_effect_and_mechanism_are_accepted():
    payload = _valid_netty_payload()
    manipulation = payload["dependency_graph_audit"]["manipulations"][0]
    manipulation["semantic_effect"] = "native_version_control"
    manipulation["mechanism"] = "maven.version_property"

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_sca_branch_normalizer_uses_remediation_sca_prefix():
    assert normalize_sca_branch("io.netty:netty-all", "4.2.13.Final") == "remediation/sca/netty-all-4.2.13.Final"
    assert normalize_sca_branch("npm://axios", "1.16.1") == "remediation/sca/axios-1.16.1"

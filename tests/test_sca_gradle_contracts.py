from __future__ import annotations

from endor_agent_kit.sca_remediation import validate_sca_gate_payload


def _valid_gradle_payload() -> dict:
    return {
        "summary": "Gate 1 selection plan for netty-all in a Gradle service.",
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
            "uia_uuid": "version-upgrade-fixture-002",
            "project_uuid": "project-fixture-webapp-002",
            "namespace": "tenant-a",
            "manifests": ["services/api-gateway/build.gradle.kts"],
            "affected_manifests": [
                "services/api-gateway/build.gradle.kts",
                "gradle/libs.versions.toml",
            ],
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-002",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp-gradle",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Endor CIA is indeterminate; requires dependencyInsight and service tests before PR.",
            "source_usage_summary": "Local source scan found no direct use of removed Netty 4.2 APIs; version is controlled through the shared version catalog.",
            "validation_requirements": [
                "./gradlew :services:api-gateway:dependencyInsight --dependency io.netty:netty-all --configuration runtimeClasspath",
                "./gradlew :services:api-gateway:test",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-002",
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
            "package_manager": "gradle",
            "status": "clear",
            "manifest": "gradle/libs.versions.toml",
            "dependency_path": ["io.netty:netty-all"],
            "manipulations": [
                {
                    "type": None,
                    "coordinate": "io.netty:netty-all",
                    "classification": "version_control",
                    "semantic_effect": "native_version_control",
                    "mechanism": "gradle.version_catalog",
                    "replacement": None,
                    "evidence": ["netty version pinned in gradle/libs.versions.toml"],
                }
            ],
            "validation_requirements": [],
        },
        "patch_plan": [
            {
                "file": "gradle/libs.versions.toml",
                "branch_name": "remediation/sca/netty-all-4.2.13.Final",
            }
        ],
        "validation": [
            {
                "command": "./gradlew :services:api-gateway:dependencyInsight --dependency io.netty:netty-all",
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
                        "repository": "example/webapp-gradle",
                        "base_branch": "main",
                        "ecosystem": "gradle",
                        "normalized_package": "mvn://io.netty:netty-all",
                        "manifest": "services/api-gateway/build.gradle.kts",
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


def _gradle_manipulation(mechanism: str, classification: str, **overrides) -> dict:
    manipulation = {
        "type": None,
        "coordinate": "commons-logging:commons-logging",
        "classification": classification,
        "semantic_effect": overrides.pop("semantic_effect", None),
        "mechanism": mechanism,
        "replacement": overrides.pop("replacement", None),
        "evidence": ["observed in services/api-gateway/build.gradle.kts"],
    }
    manipulation.update(overrides)
    return manipulation


def test_gradle_selection_requires_dependency_graph_audit():
    payload = _valid_gradle_payload()
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected Gradle remediations" in errors
    ), "Gradle signals (ecosystem + build.gradle manifests) did not engage the audit"


def test_gradle_native_controls_are_accepted():
    for mechanism in ("gradle.version_catalog", "gradle.constraint", "gradle.platform"):
        payload = _valid_gradle_payload()
        manipulation = payload["dependency_graph_audit"]["manipulations"][0]
        manipulation["mechanism"] = mechanism
        manipulation["semantic_effect"] = "native_version_control"

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert errors == [], f"native mechanism {mechanism} was rejected: {errors}"


def test_gradle_mvn_coordinate_does_not_create_maven_ambiguity():
    payload = _valid_gradle_payload()

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert not any("ambiguous package-manager signals" in error for error in errors)
    assert not any("must be maven" in error for error in errors)


def test_gradle_ecosystem_token_must_be_canonical():
    payload = _valid_gradle_payload()
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "Gradle"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be gradle for Gradle remediations"
        in errors
    )


def test_gradle_manipulations_require_mechanism_and_semantic_effect():
    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: required for Gradle manipulations" in error for error in errors
    )

    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].semantic_effect: required for Gradle manipulations" in error
        for error in errors
    )

    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "gradle.magic"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_gradle_manipulations_reject_maven_type_tokens():
    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["type"] = "version_property"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].type: must be null for Gradle manipulations" in error for error in errors
    )


def test_gradle_force_and_enforced_platform_require_mediation_evidence():
    for mechanism in (
        "gradle.resolution_strategy_force",
        "gradle.enforced_platform",
        "gradle.direct_dependency_override",
        "gradle.rich_version_rule",
    ):
        payload = _valid_gradle_payload()
        payload["dependency_graph_audit"]["manipulations"] = [
            _gradle_manipulation(
                mechanism,
                "version_control",
                semantic_effect="forced_version_mediation",
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "classification: direct Gradle overrides require mediation evidence" in error
            for error in errors
        ), f"{mechanism} masqueraded as version_control"

    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.resolution_strategy_force",
            "mediation_declared",
            semantic_effect="forced_version_mediation",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared Gradle graph mediation requires validation_required"
        in errors
    )


def test_gradle_bare_exclusion_blocks_and_rejects_relabels():
    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.exclusion", "unverified", semantic_effect="dependency_removal"
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Gradle exclusions require blocked"
        in errors
    )

    for classification in ("version_control", "mediation_declared"):
        payload = _valid_gradle_payload()
        payload["dependency_graph_audit"]["manipulations"] = [
            _gradle_manipulation(
                "gradle.exclusion",
                classification,
                semantic_effect="dependency_removal",
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "classification: Gradle exclusions require" in error for error in errors
        ), f"exclusion relabel {classification!r} escaped"


def test_gradle_substitution_requires_exact_replacement_and_validation():
    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.dependency_substitution",
            "replacement_declared",
            semantic_effect="dependency_substitution",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].replacement: required for replacement_declared" in error for error in errors)

    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.dependency_substitution",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            replacement="org.slf4j:jcl-over-slf4j:1.7.36",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []

    payload["dependency_graph_audit"]["status"] = "clear"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared Gradle substitutions require validation_required"
        in errors
    )

    payload["dependency_graph_audit"]["status"] = "validated"
    payload["dependency_graph_audit"]["manipulations"][0]["classification"] = (
        "replacement_verified"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: validated Gradle substitutions require passed resolved_graph and runtime_linkage validation"
        in errors
    )

    payload["validation"] = [
        {"kind": "resolved_graph", "status": "passed", "command": "./gradlew dependencyInsight"},
        {"kind": "runtime_linkage", "status": "passed", "command": "./gradlew test"},
    ]

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_gradle_semantic_effect_must_match_mechanism_kind():
    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.exclusion",
            "unverified",
            semantic_effect="native_version_control",
        )
    ]
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].semantic_effect: must be dependency_removal or dependency_substitution"
        in error
        for error in errors
    )


def test_gradle_self_declared_audit_is_validated_when_signals_are_scrubbed():
    payload = _valid_gradle_payload()
    key = payload["change_requests"][0]["inventory"]["key"]
    key["ecosystem"] = "jvm"
    key["manifest"] = "services/api-gateway/build.txt"
    key["normalized_package"] = "io.netty:netty-all"
    payload["selected_remediation"]["manifests"] = ["services/api-gateway/build.txt"]
    payload["selected_remediation"]["affected_manifests"] = [
        "services/api-gateway/build.txt"
    ]
    payload["dependency_graph_audit"]["manifest"] = "services/api-gateway/build.txt"
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.exclusion", "unverified", semantic_effect="dependency_removal"
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Gradle exclusions require blocked"
        in errors
    ), "scrubbing every detection signal skipped validation of a self-declared audit"


def test_gradle_replacement_must_be_exact_coordinate():
    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.dependency_substitution",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            replacement="use the slf4j bridge instead",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].replacement: must be an exact group:artifact coordinate" in error
        for error in errors
    )


def test_gradle_deeply_nested_audit_field_does_not_crash():
    payload = _valid_gradle_payload()
    deep: dict = {}
    node = deep
    for _ in range(2000):
        node["child"] = {}
        node = node["child"]
    payload["dependency_graph_audit"]["manifest"] = deep

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert isinstance(errors, list)


def test_gradle_caps_and_risk_coupling_are_shared():
    payload = _valid_gradle_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _gradle_manipulation(
            "gradle.constraint",
            "version_control",
            semantic_effect="native_version_control",
            coordinate=f"io.netty:netty-module-{index}",
        )
        for index in range(9)
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert "dependency_graph_audit.manipulations: must contain at most 8 entries" in errors

    payload = _valid_gradle_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable Gradle dependency graph audit cannot be approved_low_risk"
        in errors
    )

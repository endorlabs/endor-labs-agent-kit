from __future__ import annotations

from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    CARGO_PROFILE,
    SUPPORTED_PROFILES,
    detect_package_managers,
)


def _valid_cargo_payload() -> dict:
    return {
        "summary": "Gate 1 selection plan for regex in a Rust service.",
        "selected_remediation": {
            "package": "regex",
            "from_version": "1.5.4",
            "to_version": "1.5.5",
            "upgrade_risk": "low",
            "cia_status": "indeterminate",
            "findings_fixed": 1,
            "finding_instances_fixed": 1,
            "unique_advisories_fixed": 1,
            "fixed_finding_uuids": ["6a60c9445beb5fb713450084"],
            "findings_introduced": 0,
            "conflicts": 0,
            "uia_uuid": "version-upgrade-fixture-008",
            "project_uuid": "project-fixture-webapp-008",
            "namespace": "tenant-a",
            "manifests": ["Cargo.toml"],
            "affected_manifests": ["Cargo.toml", "Cargo.lock"],
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-008",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp-rust",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Patch bump governed by the manifest requirement; build and test before PR.",
            "source_usage_summary": "Local source compiles patterns with regex directly; no graph manipulations beyond the manifest requirement.",
            "validation_requirements": [
                "cargo tree -i regex",
                "cargo test",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-008",
                "upgrade_risk": "low",
                "cia_status": "indeterminate",
                "findings_fixed": 1,
                "finding_instances_fixed": 1,
                "unique_advisories_fixed": 1,
                "fixed_finding_uuids": ["6a60c9445beb5fb713450084"],
                "findings_introduced": 0,
            }
        ],
        "dependency_graph_audit": {
            "package_manager": "cargo",
            "status": "clear",
            "manifest": "Cargo.toml",
            "dependency_path": [
                "cargo://example-webapp@1.0.0",
                "cargo://regex@1.5.5",
            ],
            "manipulations": [
                {
                    "type": None,
                    "coordinate": "regex",
                    "classification": "version_control",
                    "semantic_effect": "native_version_control",
                    "mechanism": "cargo.manifest_requirement",
                    "replacement": None,
                    "evidence": [
                        "regex requirement declared directly in Cargo.toml [dependencies]"
                    ],
                }
            ],
            "validation_requirements": [],
        },
        "patch_plan": [
            {
                "file": "Cargo.toml",
                "branch_name": "remediation/sca/regex-1.5.5",
            }
        ],
        "validation": [
            {
                "command": "cargo tree -i regex",
                "status": "planned",
                "purpose": "Confirm regex resolves to 1.5.5",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "branch": "not_created",
                "proposed_branch": "remediation/sca/regex-1.5.5",
                "inventory": {
                    "status": "none_found",
                    "lookup_method": "source provider branch and change-request inventory",
                    "checked_at": "2026-08-19T12:00:00Z",
                    "fresh_recheck": False,
                    "key": {
                        "repository": "example/webapp-rust",
                        "base_branch": "main",
                        "ecosystem": "cargo",
                        "normalized_package": "cargo://regex",
                        "manifest": "Cargo.toml",
                        "current_version": "1.5.4",
                        "target_version": "1.5.5",
                        "finding_set": [],
                    },
                    "candidates": [],
                    "reconciliation": {
                        "status": "not_needed",
                        "reason": "No existing candidate found.",
                        "selected_target_version": "1.5.5",
                        "uia_evidence_checked_at": "2026-08-19T12:00:00Z",
                        "upstream_evidence_checked_at": "2026-08-19T12:00:00Z",
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


def _cargo_manipulation(mechanism: str, classification: str, **overrides) -> dict:
    manipulation = {
        "type": None,
        "coordinate": "regex",
        "classification": classification,
        "semantic_effect": overrides.pop("semantic_effect", None),
        "mechanism": mechanism,
        "replacement": overrides.pop("replacement", None),
        "evidence": ["observed in Cargo.toml"],
    }
    manipulation.update(overrides)
    return manipulation


def _detect(**signals):
    return detect_package_managers(
        SUPPORTED_PROFILES,
        ecosystem_tokens=signals.get("ecosystem_tokens", ()),
        manifests=signals.get("manifests", ()),
        coordinates=signals.get("coordinates", ()),
    )


def test_cargo_profile_registered_as_single_manager_family():
    # The newest profile file pins the exact registry so accidental
    # additions or removals surface here.
    names = {profile.name for profile in SUPPORTED_PROFILES}
    assert names == {
        "maven",
        "gradle",
        "npm",
        "yarn",
        "pnpm",
        "pip",
        "poetry",
        "pipenv",
        "uv",
        "go",
        "nuget",
        "bundler",
        "cargo",
    }

    assert CARGO_PROFILE.type_driven is False
    assert CARGO_PROFILE.semantic_effect_required is True
    # Cargo is the only manager for the crates.io registry: no
    # registry-family split, no shared weak signals, and the canonical
    # inventory ecosystem is the manager name itself.
    assert CARGO_PROFILE.canonical_ecosystem == "cargo"
    assert CARGO_PROFILE.shared_ecosystem_aliases == frozenset()
    assert CARGO_PROFILE.shared_manifest_basenames == frozenset()

    # First single-manager family carrying BOTH a removal and a
    # substitution bucket (Gradle is the only other family with both).
    kinds = set(CARGO_PROFILE.mechanisms.values())
    assert "removal" in kinds
    assert "substitution" in kinds


def test_cargo_manifest_and_ecosystem_detection_is_strong():
    for manifest in ("Cargo.toml", "Cargo.lock", "services/api/Cargo.toml"):
        detections = _detect(manifests=(manifest,))
        assert [d.profile.name for d in detections] == ["cargo"], (
            f"{manifest} should identify exactly cargo: "
            f"{[d.profile.name for d in detections]}"
        )

    for token in ("cargo", "crates", "crates.io", "rust", "ECOSYSTEM_CARGO"):
        detections = _detect(ecosystem_tokens=(token,))
        assert [d.profile.name for d in detections] == ["cargo"], (
            f"ecosystem token {token!r} should identify exactly cargo"
        )

    # The canonical inventory token is exactly `cargo`; aliases are detection
    # signals but non-canonical.
    assert _detect(ecosystem_tokens=("cargo",))[0].ecosystem_is_canonical is True
    assert _detect(ecosystem_tokens=("rust",))[0].ecosystem_is_canonical is False


def test_cargo_config_toml_is_not_a_detection_signal():
    # `.cargo/config.toml` carries the source-replacement mechanism, but its
    # basename is too generic to identify the family: many tools ship a
    # config.toml, so it must never register as a strong Cargo signal.
    detections = _detect(manifests=(".cargo/config.toml",))
    assert [d.profile.name for d in detections] == [], (
        "config.toml wrongly registered as a package-manager signal"
    )


def test_cargo_coordinates_are_weak_signals_only():
    detections = _detect(coordinates=("cargo://regex@1.5.5",))
    cargo_detections = [d for d in detections if d.profile.name == "cargo"]
    assert len(cargo_detections) == 1
    assert set(cargo_detections[0].signals) == {"coordinate"}


def test_cargo_manifests_do_not_bleed_into_other_families():
    detections = _detect(manifests=("Cargo.toml", "poetry.lock"))
    assert {d.profile.name for d in detections} == {"cargo", "poetry"}

    payload = _valid_cargo_payload()
    payload["selected_remediation"]["affected_manifests"] = [
        "Cargo.toml",
        "poetry.lock",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "conflicting cargo and poetry manifests did not fail closed"


def test_cargo_package_manager_schema_enum_includes_cargo():
    contract = compile_profile_contract("sca-remediation", "selection-plan")
    audit = contract.provider_neutral_schema["properties"]["dependency_graph_audit"]
    assert set(audit["properties"]["package_manager"]["enum"]) == {
        "maven",
        "gradle",
        "npm",
        "yarn",
        "pnpm",
        "pip",
        "poetry",
        "pipenv",
        "uv",
        "go",
        "nuget",
        "bundler",
        "cargo",
        None,
    }


def test_cargo_selection_requires_dependency_graph_audit():
    payload = _valid_cargo_payload()
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected Cargo remediations" in errors
    ), "Cargo signals (cargo ecosystem + Cargo.toml) did not engage the audit"


def test_cargo_native_manifest_requirement_is_accepted():
    payload = _valid_cargo_payload()

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"Cargo native manifest requirement rejected: {errors}"


def test_cargo_workspace_dependency_is_native():
    # [workspace.dependencies] is the sanctioned central version channel,
    # the Cargo analog of Maven dependencyManagement.
    payload = _valid_cargo_payload()
    payload["selected_remediation"]["affected_manifests"] = [
        "Cargo.toml",
        "Cargo.lock",
        "services/api/Cargo.toml",
    ]
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.workspace_dependency",
            "version_control",
            semantic_effect="native_version_control",
            evidence=["regex pinned centrally in [workspace.dependencies]"],
        )
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"workspace dependency rejected as native control: {errors}"


def test_cargo_manipulations_are_mechanism_driven():
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["type"] = "exclusion"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].type: must be null for Cargo manipulations" in error for error in errors
    )

    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: required for Cargo manipulations" in error for error in errors
    )

    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "cargo.magic"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    # Cross-manager mechanism smuggling fails closed in both directions.
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "bundler.lockfile_edit"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_cargo_overrides_require_mediation_evidence():
    # An exact `=` requirement added only to constrain a transitive's
    # unified resolution and a same-crate [patch]/[replace] version redirect
    # both mediate resolution outside the native requirement channel.
    for mechanism in ("cargo.transitive_pin", "cargo.patch_version"):
        payload = _valid_cargo_payload()
        payload["dependency_graph_audit"]["manipulations"] = [
            _cargo_manipulation(
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
            "classification: direct Cargo overrides require mediation evidence"
            in error
            for error in errors
        ), f"{mechanism} masqueraded as version_control"

    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.patch_version",
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
        "dependency_graph_audit.status: declared Cargo graph mediation requires validation_required"
        in errors
    )


def test_cargo_unverified_override_blocks():
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.lockfile_pin",
            "unverified",
            semantic_effect="lockfile_override",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Cargo direct overrides require blocked"
        in errors
    )


def test_cargo_lockfile_pin_requires_lockfile_override_effect():
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.lockfile_pin",
            "mediation_declared",
            semantic_effect="forced_version_mediation",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "semantic_effect: must be lockfile_override" in error for error in errors
    ), "a Cargo.lock hold accepted a mediation-only semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "lockfile_override"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_cargo_source_redirections_require_source_override_effect():
    # A [patch]/[replace] git or path redirect keeps the crate's name and
    # swaps where its code comes from; a .cargo/config.toml source
    # replacement redirects the registry itself. Both are source overrides.
    for mechanism in ("cargo.patch_source", "cargo.source_replacement"):
        payload = _valid_cargo_payload()
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _cargo_manipulation(
                mechanism,
                "mediation_declared",
                semantic_effect="forced_version_mediation",
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "semantic_effect: must be source_override" in error for error in errors
        ), f"{mechanism} accepted a non-source semantic effect"

        payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
            "source_override"
        )

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"{mechanism} with source_override rejected"


def test_cargo_feature_suppression_allows_both_removal_effects():
    # Disabling default features suppresses feature-gated code paths, and
    # because optional dependencies are feature-activated it can also drop
    # whole dependency nodes from the resolved graph — so both removal
    # effects are legitimate, chosen by what actually left the graph.
    for effect in ("asset_or_feature_suppression", "dependency_removal"):
        payload = _valid_cargo_payload()
        payload["dependency_graph_audit"]["status"] = "blocked"
        payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
        payload["dependency_graph_audit"]["manipulations"] = [
            _cargo_manipulation(
                "cargo.feature_suppression", "unverified", semantic_effect=effect
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"feature_suppression rejected legitimate effect {effect}"

    # But never mediation or substitution effects.
    for effect in ("forced_version_mediation", "dependency_substitution"):
        payload = _valid_cargo_payload()
        payload["dependency_graph_audit"]["status"] = "blocked"
        payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
        payload["dependency_graph_audit"]["manipulations"] = [
            _cargo_manipulation(
                "cargo.feature_suppression", "unverified", semantic_effect=effect
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "semantic_effect: must be asset_or_feature_suppression or "
            "dependency_removal for Cargo feature_suppression" in error
            for error in errors
        ), f"feature_suppression accepted {effect}"


def test_cargo_unverified_removal_blocks():
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.feature_suppression",
            "unverified",
            semantic_effect="asset_or_feature_suppression",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Cargo exclusions require blocked"
        in errors
    )


def test_cargo_removals_require_graph_and_runtime_validation():
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.feature_suppression",
            "unverified",
            semantic_effect="dependency_removal",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "Cargo exclusions require resolved_graph and runtime_linkage" in error
        for error in errors
    )


def test_cargo_package_rename_requires_exact_crate_replacement():
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.package_rename",
            "replacement_declared",
            semantic_effect="dependency_substitution",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].replacement: required for replacement_declared" in error for error in errors
    )

    for bad_replacement in (
        "cargo://serde_json@1.0.68",
        "serde_json",
        "serde_json@^1.0",
        "serde_json@1.0",
        "serde_json@1.0.*",
        "serde_json@=1.0.68",
        "use the maintained crate",
        "github.com/serde-rs/json@v1.0.68",
        "org.example:thing:1.0",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            bad_replacement
        )

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].replacement: must be an exact crate@version coordinate" in error
            for error in errors
        ), f"Cargo replacement accepted non-canonical form {bad_replacement!r}"

    for good_replacement in (
        "serde_json@1.0.68",
        "regex@1.5.5",
        "chrono@0.4.20-rc.1",
        "tokio@1.2.3+build.5",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            good_replacement
        )

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"exact Cargo replacement {good_replacement!r} rejected"


def test_cargo_substitution_status_coupling():
    payload = _valid_cargo_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _cargo_manipulation(
            "cargo.package_rename",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            replacement="serde_json@1.0.68",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared Cargo substitutions require "
        "validation_required" in errors
    )

    payload["dependency_graph_audit"]["manipulations"][0]["classification"] = (
        "unverified"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Cargo substitutions require blocked"
        in errors
    )


def test_cargo_inventory_ecosystem_must_be_exactly_cargo():
    payload = _valid_cargo_payload()
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "rust"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be cargo for Cargo remediations"
        in errors
    )


def test_cargo_unavailable_audit_cannot_be_low_risk():
    payload = _valid_cargo_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable Cargo dependency graph audit cannot be approved_low_risk"
        in errors
    )


def test_disguised_cargo_manifests_still_count_as_strong_signals():
    # Inherited red-team hardening: padded, zero-width-embellished,
    # trailing-dot, Windows dot-and-space, and fullwidth-lookalike manifest
    # names keep their strong signals.
    for disguised in (
        "Cargo.toml ",
        " Cargo.lock",
        "Cargo.toml​",
        "Cargo.lock.",
        "Cargo.toml .",
        "services/api/Cargo.toml  ..  ",
        "Ｃargo.toml",
    ):
        detections = _detect(manifests=(disguised,))
        assert [d.profile.name for d in detections] == ["cargo"], (
            f"disguised manifest {disguised!r} lost its strong cargo signal"
        )

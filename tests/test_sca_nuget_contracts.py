from __future__ import annotations

from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    NUGET_PROFILE,
    SUPPORTED_PROFILES,
    detect_package_managers,
)


def _valid_nuget_payload() -> dict:
    return {
        "summary": "Gate 1 selection plan for Newtonsoft.Json in a .NET service.",
        "selected_remediation": {
            "package": "Newtonsoft.Json",
            "from_version": "12.0.2",
            "to_version": "13.0.1",
            "upgrade_risk": "low",
            "cia_status": "no breaking changes",
            "findings_fixed": 1,
            "finding_instances_fixed": 1,
            "unique_advisories_fixed": 1,
            "fixed_finding_uuids": ["6a60c9445beb5fb713450082"],
            "findings_introduced": 0,
            "conflicts": 0,
            "uia_uuid": "version-upgrade-fixture-006",
            "project_uuid": "project-fixture-webapp-006",
            "namespace": "tenant-a",
            "manifests": ["src/Service/Service.csproj"],
            "affected_manifests": [
                "src/Service/Service.csproj",
                "src/Service/packages.lock.json",
            ],
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-006",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp-dotnet",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Major-line bump declared directly in the project file; build and test before PR.",
            "source_usage_summary": "Local source deserializes DTOs with Newtonsoft.Json directly; no graph manipulations beyond the PackageReference.",
            "validation_requirements": [
                "dotnet list src/Service/Service.csproj package --include-transitive",
                "dotnet test",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-006",
                "upgrade_risk": "low",
                "cia_status": "no breaking changes",
                "findings_fixed": 1,
                "finding_instances_fixed": 1,
                "unique_advisories_fixed": 1,
                "fixed_finding_uuids": ["6a60c9445beb5fb713450082"],
                "findings_introduced": 0,
            }
        ],
        "dependency_graph_audit": {
            "package_manager": "nuget",
            "status": "clear",
            "manifest": "src/Service/Service.csproj",
            "dependency_path": [
                "nuget://Example.WebApp@1.0.0",
                "nuget://Newtonsoft.Json@13.0.1",
            ],
            "manipulations": [
                {
                    "type": None,
                    "coordinate": "Newtonsoft.Json",
                    "classification": "version_control",
                    "semantic_effect": "native_version_control",
                    "mechanism": "nuget.package_reference",
                    "replacement": None,
                    "evidence": [
                        "Newtonsoft.Json version declared directly on the PackageReference"
                    ],
                }
            ],
            "validation_requirements": [],
        },
        "patch_plan": [
            {
                "file": "src/Service/Service.csproj",
                "branch_name": "remediation/sca/newtonsoft.json-13.0.1",
            }
        ],
        "validation": [
            {
                "command": "dotnet list src/Service/Service.csproj package --include-transitive",
                "status": "planned",
                "purpose": "Confirm Newtonsoft.Json resolves to 13.0.1",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "branch": "not_created",
                "proposed_branch": "remediation/sca/newtonsoft.json-13.0.1",
                "inventory": {
                    "status": "none_found",
                    "lookup_method": "source provider branch and change-request inventory",
                    "checked_at": "2026-08-19T12:00:00Z",
                    "fresh_recheck": False,
                    "key": {
                        "repository": "example/webapp-dotnet",
                        "base_branch": "main",
                        "ecosystem": "nuget",
                        "normalized_package": "nuget://Newtonsoft.Json",
                        "manifest": "src/Service/Service.csproj",
                        "current_version": "12.0.2",
                        "target_version": "13.0.1",
                        "finding_set": [],
                    },
                    "candidates": [],
                    "reconciliation": {
                        "status": "not_needed",
                        "reason": "No existing candidate found.",
                        "selected_target_version": "13.0.1",
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


def _nuget_manipulation(mechanism: str, classification: str, **overrides) -> dict:
    manipulation = {
        "type": None,
        "coordinate": "Newtonsoft.Json",
        "classification": classification,
        "semantic_effect": overrides.pop("semantic_effect", None),
        "mechanism": mechanism,
        "replacement": overrides.pop("replacement", None),
        "evidence": ["observed in src/Service/Service.csproj"],
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


def test_nuget_profile_registered_as_single_manager_family():
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
    }

    assert NUGET_PROFILE.type_driven is False
    assert NUGET_PROFILE.semantic_effect_required is True
    # NuGet is a single-manager family: MSBuild project files, props/targets
    # layers, and NuGet lock/config files are all unambiguous, so the
    # canonical inventory ecosystem is the manager name itself and there are
    # no shared weak signals.
    assert NUGET_PROFILE.canonical_ecosystem == "nuget"
    assert NUGET_PROFILE.shared_ecosystem_aliases == frozenset()
    assert NUGET_PROFILE.shared_manifest_basenames == frozenset()


def test_nuget_manifest_and_ecosystem_detection_is_strong():
    for manifest in (
        "packages.lock.json",
        "packages.config",
        "nuget.config",
        "src/Service/Service.csproj",
        "src/Compiler/App.fsproj",
        "legacy/Legacy.vbproj",
        "Directory.Packages.props",
        "Directory.Build.props",
        "Directory.Build.targets",
    ):
        detections = _detect(manifests=(manifest,))
        assert [d.profile.name for d in detections] == ["nuget"], (
            f"{manifest} should identify exactly nuget: "
            f"{[d.profile.name for d in detections]}"
        )

    for token in ("nuget", "dotnet", "ECOSYSTEM_NUGET", ".net", "dot_net"):
        detections = _detect(ecosystem_tokens=(token,))
        assert [d.profile.name for d in detections] == ["nuget"], (
            f"ecosystem token {token!r} should identify exactly nuget"
        )

    # The canonical inventory token is exactly `nuget`; aliases are detection
    # signals but non-canonical for the duplicate-inventory key.
    assert _detect(ecosystem_tokens=("nuget",))[0].ecosystem_is_canonical is True
    assert _detect(ecosystem_tokens=("dotnet",))[0].ecosystem_is_canonical is False


def test_nuget_coordinates_are_weak_signals_only():
    detections = _detect(coordinates=("nuget://Newtonsoft.Json@13.0.1",))
    nuget_detections = [d for d in detections if d.profile.name == "nuget"]
    assert len(nuget_detections) == 1
    assert set(nuget_detections[0].signals) == {"coordinate"}


def test_nuget_manifests_do_not_bleed_into_other_families():
    detections = _detect(manifests=("src/Service/Service.csproj", "poetry.lock"))
    assert {d.profile.name for d in detections} == {"nuget", "poetry"}

    payload = _valid_nuget_payload()
    payload["selected_remediation"]["affected_manifests"] = [
        "src/Service/Service.csproj",
        "poetry.lock",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "conflicting nuget and poetry manifests did not fail closed"


def test_nuget_package_manager_schema_enum_includes_nuget():
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
        None,
    }


def test_nuget_selection_requires_dependency_graph_audit():
    payload = _valid_nuget_payload()
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected NuGet remediations" in errors
    ), "NuGet signals (nuget ecosystem + .csproj) did not engage the audit"


def test_nuget_native_package_reference_is_accepted():
    payload = _valid_nuget_payload()

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"NuGet native PackageReference rejected: {errors}"


def test_nuget_central_package_version_is_native():
    # Central Package Management's PackageVersion for a project's own direct
    # dependency is the sanctioned first-party version channel, not a graph
    # manipulation.
    payload = _valid_nuget_payload()
    payload["selected_remediation"]["affected_manifests"] = [
        "src/Service/Service.csproj",
        "Directory.Packages.props",
    ]
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.central_package_version",
            "version_control",
            semantic_effect="native_version_control",
            evidence=["PackageVersion pinned centrally in Directory.Packages.props"],
        )
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"central PackageVersion rejected as native control: {errors}"


def test_nuget_manipulations_are_mechanism_driven():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["type"] = "exclusion"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].type: must be null for NuGet manipulations" in error for error in errors
    )

    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: required for NuGet manipulations" in error for error in errors
    )

    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "nuget.magic"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    # Cross-manager mechanism smuggling fails closed in both directions.
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "go.replace_version"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_nuget_overrides_require_mediation_evidence():
    # A direct pin of a transitive (direct-wins), a centrally pinned
    # transitive (CentralPackageTransitivePinningEnabled), a VersionOverride
    # defeating the central pin, and a Directory.Build.props/.targets layer
    # all mediate NuGet version resolution outside the project's own
    # declaration: none may masquerade as version_control.
    for mechanism in (
        "nuget.transitive_pin",
        "nuget.central_transitive_pin",
        "nuget.version_override",
        "nuget.build_props_layer",
    ):
        payload = _valid_nuget_payload()
        payload["dependency_graph_audit"]["manipulations"] = [
            _nuget_manipulation(
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
            "classification: direct NuGet overrides require mediation evidence"
            in error
            for error in errors
        ), f"{mechanism} masqueraded as version_control"

    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.build_props_layer",
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
        "dependency_graph_audit.status: declared NuGet graph mediation requires validation_required"
        in errors
    )


def test_nuget_unverified_override_blocks():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.build_props_layer",
            "unverified",
            semantic_effect="forced_version_mediation",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified NuGet direct overrides require blocked"
        in errors
    )


def test_nuget_lockfile_edit_requires_lockfile_override_effect():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.lockfile_edit",
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
    ), "a hand-edited packages.lock.json accepted a mediation-only semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "lockfile_override"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_nuget_restore_source_requires_source_override_effect():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.restore_source",
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
    ), "a nuget.config source redirect accepted a non-source semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "source_override"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_nuget_exclude_assets_requires_asset_suppression_effect():
    # ExcludeAssets/PrivateAssets never removes the graph node — the package
    # stays resolved and listed in packages.lock.json while its compile or
    # runtime assets silently stop flowing. The effect is asset suppression,
    # not dependency_removal, and the removal safety machinery still applies.
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.exclude_assets",
            "unverified",
            semantic_effect="dependency_removal",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "semantic_effect: must be asset_or_feature_suppression for NuGet "
        "exclude_assets manipulations" in error
        for error in errors
    ), "ExcludeAssets accepted a dependency_removal semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "asset_or_feature_suppression"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_nuget_package_remove_requires_dependency_removal_effect():
    # An MSBuild `<PackageReference Remove="..."/>` drops the reference item
    # itself: that IS a graph-node removal, never mere asset suppression.
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.package_remove",
            "unverified",
            semantic_effect="asset_or_feature_suppression",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "semantic_effect: must be dependency_removal for NuGet "
        "package_remove manipulations" in error
        for error in errors
    ), "PackageReference Remove accepted an asset-suppression semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "dependency_removal"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_nuget_unverified_removal_blocks():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.exclude_assets",
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
        "dependency_graph_audit.status: unverified NuGet exclusions require blocked"
        in errors
    )


def test_nuget_removals_require_graph_and_runtime_validation():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.package_remove",
            "unverified",
            semantic_effect="dependency_removal",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "NuGet exclusions require resolved_graph and runtime_linkage" in error
        for error in errors
    )


def test_nuget_removal_replacement_requires_exact_package_coordinate():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.package_remove",
            "replacement_declared",
            semantic_effect="dependency_removal",
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
        "nuget://BouncyCastle.Cryptography@2.3.1",
        "BouncyCastle.Cryptography",
        "BouncyCastle.Cryptography@2.*",
        "BouncyCastle.Cryptography@[2.3.1,3.0.0)",
        "BouncyCastle.Cryptography@2.3",
        "BouncyCastle.Cryptography@2.3.1-*",
        "use the maintained package",
        "org.bouncycastle:bcprov-jdk18on:1.78",
        "github.com/golang-jwt/jwt@v3.2.1",
        "BouncyCastle.Cryptography@２.３.１",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            bad_replacement
        )

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].replacement: must be an exact package@version coordinate" in error
            for error in errors
        ), f"NuGet replacement accepted non-canonical form {bad_replacement!r}"

    for good_replacement in (
        "BouncyCastle.Cryptography@2.3.1",
        "Newtonsoft.Json@13.0.1",
        "Legacy.Package@1.0.0.4",
        "Preview.Pkg@4.0.0-preview.1",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            good_replacement
        )

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"exact NuGet replacement {good_replacement!r} rejected"


def test_nuget_replacement_declared_status_coupling():
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.package_remove",
            "replacement_declared",
            semantic_effect="dependency_removal",
            replacement="BouncyCastle.Cryptography@2.3.1",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared NuGet replacements require "
        "validation_required" in errors
    )


def test_nuget_substitution_never_claimable():
    # NuGet has no module-path redirect: swapping to a different package ID
    # is a manifest edit, not a resolution-graph construct, so
    # dependency_substitution must not be claimable through NuGet mechanisms.
    payload = _valid_nuget_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _nuget_manipulation(
            "nuget.exclude_assets",
            "unverified",
            semantic_effect="dependency_substitution",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].semantic_effect: must be" in error for error in errors)

    kinds = set(NUGET_PROFILE.mechanisms.values())
    assert "substitution" not in kinds, "the NuGet profile claims a substitution construct"
    assert "removal" in kinds, "the NuGet profile lost its removal constructs"


def test_nuget_inventory_ecosystem_must_be_exactly_nuget():
    payload = _valid_nuget_payload()
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "dotnet"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be nuget for NuGet remediations"
        in errors
    )


def test_nuget_unavailable_audit_cannot_be_low_risk():
    payload = _valid_nuget_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable NuGet dependency graph audit cannot be approved_low_risk"
        in errors
    )


def test_disguised_nuget_manifests_still_count_as_strong_signals():
    # Inherited red-team hardening: padded, zero-width-embellished, and
    # trailing-dot manifest names keep their strong signals — and the suffix
    # channel folds fullwidth lookalike extensions the same way.
    for disguised in (
        "packages.lock.json ",
        " Directory.Build.props",
        "packages.config​",
        "Service.csproj.",
        "src/Service/Service.ｃｓｐｒｏｊ",
    ):
        detections = _detect(manifests=(disguised,))
        assert [d.profile.name for d in detections] == ["nuget"], (
            f"disguised manifest {disguised!r} lost its strong nuget signal"
        )


def test_windows_trailing_dot_and_space_manifest_does_not_dodge_ambiguity_gate():
    # Red-team finding (engine-wide): _manifest_basename stripped a leading/
    # trailing whitespace once up front and trailing dots once at the end, so
    # a Windows-equivalent name that interleaves trailing dots and spaces
    # ('Service.csproj .', 'Service.csproj  ..  ') kept a residual space, lost
    # its suffix signal, and let a smuggled second-family manifest dodge the
    # ambiguity fail-closed gate. Windows path resolution folds trailing dots
    # and spaces together in any order.
    for disguised in (
        "src/Service/Service.csproj .",
        "src/Service/Service.csproj  ..  ",
        "Directory.Packages.props. ",
    ):
        detections = _detect(manifests=(disguised,))
        assert [d.profile.name for d in detections] == ["nuget"], (
            f"windows-disguised manifest {disguised!r} lost its strong nuget signal"
        )

    payload = _valid_nuget_payload()
    conflicting = {
        "repository": "example/webapp-dotnet",
        "base_branch": "main",
        "ecosystem": "pypi",
        "normalized_package": "pypi://requests",
        "manifest": "poetry.lock",
        "current_version": "2.25.1",
        "target_version": "2.32.0",
        "finding_set": [],
    }
    conflicting_cr = {
        "status": "not_created",
        "base_branch": "main",
        "branch": "not_created",
        "proposed_branch": "remediation/sca/requests-2.32.0",
        "inventory": {
            "status": "none_found",
            "lookup_method": "source provider branch and change-request inventory",
            "checked_at": "2026-08-19T12:00:00Z",
            "fresh_recheck": False,
            "key": conflicting,
            "candidates": [],
            "reconciliation": {
                "status": "not_needed",
                "reason": "No existing candidate found.",
                "selected_target_version": "2.32.0",
                "uia_evidence_checked_at": "2026-08-19T12:00:00Z",
                "upstream_evidence_checked_at": "2026-08-19T12:00:00Z",
                "operator_choice_required": False,
            },
        },
    }
    # Primary family is NuGet; a poetry manifest is smuggled into the second
    # change request, disguised Windows-style so detection would drop it.
    conflicting_cr["inventory"]["key"]["manifest"] = "poetry.lock ."
    payload["change_requests"].append(conflicting_cr)
    payload["selected_remediation"]["affected_manifests"] = [
        "src/Service/Service.csproj",
        "src/Service/packages.lock.json",
        "poetry.lock .",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "a Windows dot-and-space-disguised conflicting manifest dodged the ambiguity gate"


def test_patch_plan_manifest_engages_the_audit_when_other_signals_are_scrubbed():
    # Red-team finding (engine-wide): detection read change-request inventory
    # keys and selected/affected manifests but never patch_plan[].file — the
    # very manifest the plan intends to edit. Scrubbing every other channel to
    # a non-NuGet value while pointing patch_plan at the real .csproj and
    # omitting dependency_graph_audit let a NuGet manifest edit skip the audit
    # entirely.
    payload = _valid_nuget_payload()
    payload.pop("dependency_graph_audit")
    key = payload["change_requests"][0]["inventory"]["key"]
    key["ecosystem"] = "binaries"
    key["manifest"] = "build/artifacts.bin"
    key["normalized_package"] = "opaque-blob"
    payload["selected_remediation"]["manifests"] = ["build/artifacts.bin"]
    payload["selected_remediation"]["affected_manifests"] = ["build/artifacts.bin"]
    payload["selected_remediation"]["package"] = "opaque-blob"
    payload["patch_plan"] = [
        {"file": "src/Service/Service.csproj", "branch_name": "remediation/sca/x-1"}
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected NuGet remediations" in errors
    ), "a .csproj present only in patch_plan.file dodged the audit-required gate"

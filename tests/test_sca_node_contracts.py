from __future__ import annotations

from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    GRADLE_PROFILE,
    MAVEN_PROFILE,
    NPM_PROFILE,
    PNPM_PROFILE,
    SUPPORTED_PROFILES,
    YARN_PROFILE,
    detect_package_managers,
)


def _valid_node_payload(manager: str = "npm") -> dict:
    lockfile = {
        "npm": "package-lock.json",
        "yarn": "yarn.lock",
        "pnpm": "pnpm-lock.yaml",
    }[manager]
    return {
        "summary": f"Gate 1 selection plan for lodash in a {manager}-managed service.",
        "selected_remediation": {
            "package": "lodash",
            "from_version": "4.17.20",
            "to_version": "4.17.21",
            "upgrade_risk": "low",
            "cia_status": "no breaking changes",
            "findings_fixed": 1,
            "finding_instances_fixed": 1,
            "unique_advisories_fixed": 1,
            "fixed_finding_uuids": ["6a60c9445beb5fb713450061"],
            "findings_introduced": 0,
            "conflicts": 0,
            "uia_uuid": "version-upgrade-fixture-003",
            "project_uuid": "project-fixture-webapp-003",
            "namespace": "tenant-a",
            "manifests": ["package.json"],
            "affected_manifests": ["package.json", lockfile],
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-003",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp-node",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Patch-level bump governed by the manifest range; install and test before PR.",
            "source_usage_summary": "Local source imports lodash directly; no graph manipulations beyond the manifest range.",
            "validation_requirements": [
                "npm ls lodash",
                "npm test",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-003",
                "upgrade_risk": "low",
                "cia_status": "no breaking changes",
                "findings_fixed": 1,
                "finding_instances_fixed": 1,
                "unique_advisories_fixed": 1,
                "fixed_finding_uuids": ["6a60c9445beb5fb713450061"],
                "findings_introduced": 0,
            }
        ],
        "dependency_graph_audit": {
            "package_manager": manager,
            "status": "clear",
            "manifest": "package.json",
            "dependency_path": ["npm://example-webapp@1.0.0", "npm://lodash@4.17.21"],
            "manipulations": [
                {
                    "type": None,
                    "coordinate": "lodash",
                    "classification": "version_control",
                    "semantic_effect": "native_version_control",
                    "mechanism": f"{manager}.manifest_range",
                    "replacement": None,
                    "evidence": ["lodash range declared directly in package.json"],
                }
            ],
            "validation_requirements": [],
        },
        "patch_plan": [
            {
                "file": "package.json",
                "branch_name": "remediation/sca/lodash-4.17.21",
            }
        ],
        "validation": [
            {
                "command": "npm ls lodash",
                "status": "planned",
                "purpose": "Confirm lodash resolves to 4.17.21",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "branch": "not_created",
                "proposed_branch": "remediation/sca/lodash-4.17.21",
                "inventory": {
                    "status": "none_found",
                    "lookup_method": "source provider branch and change-request inventory",
                    "checked_at": "2026-08-18T12:00:00Z",
                    "fresh_recheck": False,
                    "key": {
                        "repository": "example/webapp-node",
                        "base_branch": "main",
                        "ecosystem": "npm",
                        "normalized_package": "npm://lodash",
                        "manifest": "package.json",
                        "current_version": "4.17.20",
                        "target_version": "4.17.21",
                        "finding_set": [],
                    },
                    "candidates": [],
                    "reconciliation": {
                        "status": "not_needed",
                        "reason": "No existing candidate found.",
                        "selected_target_version": "4.17.21",
                        "uia_evidence_checked_at": "2026-08-18T12:00:00Z",
                        "upstream_evidence_checked_at": "2026-08-18T12:00:00Z",
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


def _node_manipulation(mechanism: str, classification: str, **overrides) -> dict:
    manipulation = {
        "type": None,
        "coordinate": "commons-logging-equivalent",
        "classification": classification,
        "semantic_effect": overrides.pop("semantic_effect", None),
        "mechanism": mechanism,
        "replacement": overrides.pop("replacement", None),
        "evidence": ["observed in package.json"],
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


def test_node_profiles_registered_with_registry_level_ecosystem():
    names = {profile.name for profile in SUPPORTED_PROFILES}
    assert names >= {"maven", "gradle", "npm", "yarn", "pnpm"}

    for profile in (NPM_PROFILE, YARN_PROFILE, PNPM_PROFILE):
        assert profile.type_driven is False
        assert profile.semantic_effect_required is True
        # Endor treats npm/Yarn/pnpm as one npm-registry family: the
        # duplicate-inventory key is manager-agnostic while the audit's
        # package_manager stays manager-specific.
        assert profile.canonical_ecosystem == "npm"

    assert MAVEN_PROFILE.canonical_ecosystem == "maven"
    assert GRADLE_PROFILE.canonical_ecosystem == "gradle"


def test_node_lockfile_detection_is_manager_specific():
    cases = {
        "package-lock.json": "npm",
        "npm-shrinkwrap.json": "npm",
        "yarn.lock": "yarn",
        ".yarnrc.yml": "yarn",
        "pnpm-lock.yaml": "pnpm",
        "pnpm-workspace.yaml": "pnpm",
    }
    for manifest, expected in cases.items():
        detections = _detect(manifests=(manifest,))
        assert [d.profile.name for d in detections] == [expected], (
            f"{manifest} should identify exactly {expected}: "
            f"{[d.profile.name for d in detections]}"
        )


def test_shared_node_signals_do_not_single_out_a_manager():
    # package.json, the npm-registry ecosystem token, and npm:// coordinates
    # are shared across npm/Yarn/pnpm — none may claim a single manager alone.
    for signals in (
        {"manifests": ("package.json",)},
        {"ecosystem_tokens": ("npm",)},
        {"coordinates": ("npm://lodash@4.17.21",)},
    ):
        detections = _detect(**signals)
        node_names = {
            d.profile.name for d in detections if d.profile.name in {"npm", "yarn", "pnpm"}
        }
        assert node_names != {"npm"} and len(node_names) != 1, (
            f"shared signal {signals} singled out {node_names}"
        )

    # A manager-specific lockfile resolves the shared signals.
    detections = _detect(
        ecosystem_tokens=("npm",), manifests=("package.json", "yarn.lock")
    )
    assert [d.profile.name for d in detections] == ["yarn"]
    # The npm-registry token is the canonical inventory ecosystem for Yarn.
    assert detections[0].ecosystem_is_canonical is True


def test_conflicting_node_lockfiles_are_ambiguous():
    detections = _detect(manifests=("package-lock.json", "yarn.lock"))
    assert {d.profile.name for d in detections} == {"npm", "yarn"}


def test_gradle_lockfile_is_not_a_node_signal():
    detections = _detect(manifests=("gradle.lockfile",))
    assert {d.profile.name for d in detections} == {"gradle"}


def test_registry_family_narrows_by_declared_manager_without_lockfile():
    # A library repo with no committed lockfile carries only registry-shared
    # signals (package.json, ecosystem npm, npm:// coordinates). The declared
    # audit manager narrows the family instead of failing closed as ambiguous.
    payload = _valid_node_payload("npm")
    payload["selected_remediation"]["affected_manifests"] = ["package.json"]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"lockfile-less npm repo failed: {errors}"

    # Two manager-specific lockfiles stay ambiguous — strong signals never narrow.
    payload = _valid_node_payload("npm")
    payload["selected_remediation"]["affected_manifests"] = [
        "package.json",
        "package-lock.json",
        "yarn.lock",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "conflicting npm and yarn lockfiles did not fail closed"


def test_node_package_manager_schema_enum_covers_node_managers():
    contract = compile_profile_contract("sca-remediation", "selection-plan")
    audit = contract.provider_neutral_schema["properties"]["dependency_graph_audit"]
    assert set(audit["properties"]["package_manager"]["enum"]) >= {
        "maven",
        "gradle",
        "npm",
        "yarn",
        "pnpm",
        None,
    }


def test_npm_selection_requires_dependency_graph_audit():
    payload = _valid_node_payload("npm")
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected npm remediations" in errors
    ), "npm signals (registry ecosystem + package-lock.json) did not engage the audit"


def test_node_native_manifest_range_is_accepted_per_manager():
    for manager in ("npm", "yarn", "pnpm"):
        payload = _valid_node_payload(manager)

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert errors == [], f"{manager} native manifest range rejected: {errors}"


def test_node_manipulations_are_mechanism_driven():
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["manipulations"][0]["type"] = "exclusion"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].type: must be null for npm manipulations" in error for error in errors
    )

    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: required for npm manipulations" in error for error in errors
    )

    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "npm.magic"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    # Cross-manager mechanism smuggling fails closed in both directions.
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "gradle.exclusion"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    payload = _valid_node_payload("yarn")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "npm.overrides"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_node_overrides_require_mediation_evidence():
    for manager, mechanism, display in (
        ("npm", "npm.overrides", "npm"),
        ("yarn", "yarn.resolutions", "Yarn"),
        ("pnpm", "pnpm.overrides", "pnpm"),
        ("pnpm", "pnpm.pnpmfile_hook", "pnpm"),
    ):
        payload = _valid_node_payload(manager)
        payload["dependency_graph_audit"]["manipulations"] = [
            _node_manipulation(
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
            f"classification: direct {display} overrides require mediation evidence"
            in error
            for error in errors
        ), f"{mechanism} masqueraded as version_control"

    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.overrides",
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
        "dependency_graph_audit.status: declared npm graph mediation requires validation_required"
        in errors
    )


def test_node_unverified_override_blocks():
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.overrides", "unverified", semantic_effect="forced_version_mediation"
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified npm direct overrides require blocked"
        in errors
    )


def test_node_lockfile_edit_requires_lockfile_override_effect():
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.lockfile_edit",
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
    ), "a hand-edited lockfile pin accepted a mediation-only semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "lockfile_override"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_node_source_specifier_requires_source_override_effect():
    for manager, mechanism in (
        ("npm", "npm.source_specifier"),
        ("yarn", "yarn.patch_protocol"),
        ("yarn", "yarn.source_protocol"),
        ("pnpm", "pnpm.source_specifier"),
    ):
        payload = _valid_node_payload(manager)
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _node_manipulation(
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


def test_node_alias_redirect_requires_exact_npm_replacement():
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.alias_redirect",
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
        "npm://left-pad@1.3.0",
        "org.slf4j:jcl-over-slf4j:1.7.36",
        "use lodash instead",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            bad_replacement
        )

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].replacement: must be an exact name@version coordinate" in error
            for error in errors
        ), f"npm replacement accepted non-canonical form {bad_replacement!r}"

    for good_replacement in ("left-pad@1.3.0", "@scope/pkg@1.2.3"):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            good_replacement
        )

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"exact npm replacement {good_replacement!r} rejected"


def test_node_semantic_effect_dependency_removal_is_rejected():
    # No npm/Yarn/pnpm construct removes a graph node the way a JVM exclusion
    # does; dependency_removal must not be claimable through Node mechanisms.
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.overrides", "unverified", semantic_effect="dependency_removal"
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].semantic_effect: must be" in error for error in errors)


def test_node_inventory_ecosystem_must_be_registry_npm():
    payload = _valid_node_payload("yarn")
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "yarn"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be npm for Yarn remediations"
        in errors
    )

    payload = _valid_node_payload("npm")
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "node"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be npm for npm remediations"
        in errors
    )


def test_node_unavailable_audit_cannot_be_low_risk():
    payload = _valid_node_payload("pnpm")
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable pnpm dependency graph audit cannot be approved_low_risk"
        in errors
    )


def test_unresolvable_declared_manager_fails_closed_when_audit_claims_content():
    # Red-team finding: with every detection signal scrubbed, the
    # self-declared fallback matched profiles by exact name only, so a
    # near-miss or null package_manager token skipped the entire audit
    # validation. A non-unavailable audit (or one listing manipulations)
    # whose declared manager resolves to no supported profile must fail
    # closed, not fail open.
    def scrubbed_payload(package_manager):
        payload = _valid_node_payload("npm")
        key = payload["change_requests"][0]["inventory"]["key"]
        key["ecosystem"] = "javascript-ish"
        key["manifest"] = "app/deps.txt"
        key["normalized_package"] = "lodash"
        payload["selected_remediation"]["manifests"] = ["app/deps.txt"]
        payload["selected_remediation"]["affected_manifests"] = ["app/deps.txt"]
        payload["patch_plan"][0]["file"] = "app/deps.txt"
        payload["dependency_graph_audit"]["manifest"] = "app/deps.txt"
        payload["dependency_graph_audit"]["package_manager"] = package_manager
        payload["dependency_graph_audit"]["manipulations"] = [
            _node_manipulation(
                "npm.overrides",
                "unverified",
                semantic_effect="forced_version_mediation",
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]
        return payload

    for token in (None, "NPM", "node", "npm8", ["npm"], {"name": "npm"}):
        errors = validate_sca_gate_payload(
            scrubbed_payload(token), gate="selection-plan"
        )

        assert any(
            "dependency_graph_audit.package_manager: must be one of" in error
            for error in errors
        ), f"unresolvable declared manager {token!r} skipped audit validation"

    # The honest unsupported-manager shape stays accepted: unavailable with
    # no manipulations and no supported-manager claim.
    payload = scrubbed_payload("cargo")
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []
    payload["dependency_graph_audit"]["validation_requirements"] = []
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_node_replacement_rejects_mutable_versions():
    # Red-team finding: dist-tags and x-ranges passed the "exact
    # name@version" check. Exact means a full, immutable semver.
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.alias_redirect",
            "replacement_declared",
            semantic_effect="dependency_substitution",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    for mutable in ("pkg@latest", "pkg@next", "pkg@x", "pkg@1.x", "pkg@1.2.x", "pkg@1"):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = mutable

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].replacement: must be an exact name@version coordinate" in error
            for error in errors
        ), f"mutable npm replacement {mutable!r} passed the exact-coordinate check"

    for exact in ("pkg@1.2.3", "@scope/pkg@1.2.3-beta.1", "left-pad@1.3.0"):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = exact

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"exact npm replacement {exact!r} rejected"


def test_whitespace_padded_lockfiles_still_count_as_strong_signals():
    # Red-team finding: 'yarn.lock ' failed basename matching, so a payload
    # with conflicting lockfiles dodged the ambiguity fail-closed gate.
    for padded in ("yarn.lock ", " yarn.lock", "yarn.lock\n", "yarn.lock\t"):
        detections = _detect(manifests=(padded,))
        assert [d.profile.name for d in detections] == ["yarn"], (
            f"padded manifest {padded!r} lost its strong yarn signal"
        )

    payload = _valid_node_payload("npm")
    payload["selected_remediation"]["affected_manifests"] = [
        "package.json",
        "package-lock.json",
        "yarn.lock ",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "whitespace-padded conflicting lockfile bypassed the ambiguity gate"


def test_node_self_declared_audit_is_validated_when_signals_are_scrubbed():
    payload = _valid_node_payload("npm")
    key = payload["change_requests"][0]["inventory"]["key"]
    key["ecosystem"] = "javascript-ish"
    key["manifest"] = "app/deps.txt"
    key["normalized_package"] = "lodash"
    payload["selected_remediation"]["manifests"] = ["app/deps.txt"]
    payload["selected_remediation"]["affected_manifests"] = ["app/deps.txt"]
    payload["dependency_graph_audit"]["manifest"] = "app/deps.txt"
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.overrides", "unverified", semantic_effect="forced_version_mediation"
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified npm direct overrides require blocked"
        in errors
    ), "scrubbing every detection signal skipped validation of a self-declared npm audit"

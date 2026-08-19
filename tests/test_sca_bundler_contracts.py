from __future__ import annotations

from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    BUNDLER_PROFILE,
    SUPPORTED_PROFILES,
    detect_package_managers,
)


def _valid_bundler_payload() -> dict:
    return {
        "summary": "Gate 1 selection plan for addressable in a Ruby service.",
        "selected_remediation": {
            "package": "addressable",
            "from_version": "2.7.0",
            "to_version": "2.8.0",
            "upgrade_risk": "low",
            "cia_status": "no breaking changes",
            "findings_fixed": 1,
            "finding_instances_fixed": 1,
            "unique_advisories_fixed": 1,
            "fixed_finding_uuids": ["6a60c9445beb5fb713450083"],
            "findings_introduced": 0,
            "conflicts": 0,
            "uia_uuid": "version-upgrade-fixture-007",
            "project_uuid": "project-fixture-webapp-007",
            "namespace": "tenant-a",
            "manifests": ["Gemfile"],
            "affected_manifests": ["Gemfile", "Gemfile.lock"],
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-007",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp-ruby",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Minor bump governed by the Gemfile requirement; bundle and test before PR.",
            "source_usage_summary": "Local source parses URIs with addressable directly; no graph manipulations beyond the Gemfile requirement.",
            "validation_requirements": [
                "bundle list addressable",
                "bundle exec rake test",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-007",
                "upgrade_risk": "low",
                "cia_status": "no breaking changes",
                "findings_fixed": 1,
                "finding_instances_fixed": 1,
                "unique_advisories_fixed": 1,
                "fixed_finding_uuids": ["6a60c9445beb5fb713450083"],
                "findings_introduced": 0,
            }
        ],
        "dependency_graph_audit": {
            "package_manager": "bundler",
            "status": "clear",
            "manifest": "Gemfile",
            "dependency_path": [
                "gem://example-webapp@1.0.0",
                "gem://addressable@2.8.0",
            ],
            "manipulations": [
                {
                    "type": None,
                    "coordinate": "addressable",
                    "classification": "version_control",
                    "semantic_effect": "native_version_control",
                    "mechanism": "bundler.gemfile_requirement",
                    "replacement": None,
                    "evidence": [
                        "addressable requirement declared directly in the Gemfile"
                    ],
                }
            ],
            "validation_requirements": [],
        },
        "patch_plan": [
            {
                "file": "Gemfile",
                "branch_name": "remediation/sca/addressable-2.8.0",
            }
        ],
        "validation": [
            {
                "command": "bundle list addressable",
                "status": "planned",
                "purpose": "Confirm addressable resolves to 2.8.0",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "branch": "not_created",
                "proposed_branch": "remediation/sca/addressable-2.8.0",
                "inventory": {
                    "status": "none_found",
                    "lookup_method": "source provider branch and change-request inventory",
                    "checked_at": "2026-08-19T12:00:00Z",
                    "fresh_recheck": False,
                    "key": {
                        "repository": "example/webapp-ruby",
                        "base_branch": "main",
                        "ecosystem": "gem",
                        "normalized_package": "gem://addressable",
                        "manifest": "Gemfile",
                        "current_version": "2.7.0",
                        "target_version": "2.8.0",
                        "finding_set": [],
                    },
                    "candidates": [],
                    "reconciliation": {
                        "status": "not_needed",
                        "reason": "No existing candidate found.",
                        "selected_target_version": "2.8.0",
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


def _bundler_manipulation(mechanism: str, classification: str, **overrides) -> dict:
    manipulation = {
        "type": None,
        "coordinate": "addressable",
        "classification": classification,
        "semantic_effect": overrides.pop("semantic_effect", None),
        "mechanism": mechanism,
        "replacement": overrides.pop("replacement", None),
        "evidence": ["observed in Gemfile"],
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


def test_bundler_profile_registered_as_single_manager_family():
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
    }

    assert BUNDLER_PROFILE.type_driven is False
    assert BUNDLER_PROFILE.semantic_effect_required is True
    # Bundler is the only manager for the RubyGems registry, so there is no
    # registry-family split and no shared weak signals — but the canonical
    # inventory ecosystem is the registry token `gem`, not the manager name.
    assert BUNDLER_PROFILE.canonical_ecosystem == "gem"
    assert BUNDLER_PROFILE.shared_ecosystem_aliases == frozenset()
    assert BUNDLER_PROFILE.shared_manifest_basenames == frozenset()


def test_bundler_manifest_and_ecosystem_detection_is_strong():
    for manifest in (
        "Gemfile",
        "Gemfile.lock",
        "gems.rb",
        "gems.locked",
        "lib/example.gemspec",
    ):
        detections = _detect(manifests=(manifest,))
        assert [d.profile.name for d in detections] == ["bundler"], (
            f"{manifest} should identify exactly bundler: "
            f"{[d.profile.name for d in detections]}"
        )

    for token in ("gem", "rubygems", "ruby", "bundler", "ECOSYSTEM_GEM"):
        detections = _detect(ecosystem_tokens=(token,))
        assert [d.profile.name for d in detections] == ["bundler"], (
            f"ecosystem token {token!r} should identify exactly bundler"
        )

    # The canonical inventory token is exactly `gem`; the manager name and
    # other aliases are detection signals but non-canonical.
    assert _detect(ecosystem_tokens=("gem",))[0].ecosystem_is_canonical is True
    assert _detect(ecosystem_tokens=("bundler",))[0].ecosystem_is_canonical is False
    assert _detect(ecosystem_tokens=("rubygems",))[0].ecosystem_is_canonical is False


def test_bundler_coordinates_are_weak_signals_only():
    detections = _detect(coordinates=("gem://addressable@2.8.0",))
    bundler_detections = [d for d in detections if d.profile.name == "bundler"]
    assert len(bundler_detections) == 1
    assert set(bundler_detections[0].signals) == {"coordinate"}


def test_bundler_manifests_do_not_bleed_into_other_families():
    detections = _detect(manifests=("Gemfile", "poetry.lock"))
    assert {d.profile.name for d in detections} == {"bundler", "poetry"}

    payload = _valid_bundler_payload()
    payload["selected_remediation"]["affected_manifests"] = [
        "Gemfile",
        "poetry.lock",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "conflicting bundler and poetry manifests did not fail closed"


def test_bundler_package_manager_schema_enum_includes_bundler():
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
        None,
    }


def test_bundler_selection_requires_dependency_graph_audit():
    payload = _valid_bundler_payload()
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected Bundler remediations" in errors
    ), "Bundler signals (gem ecosystem + Gemfile) did not engage the audit"


def test_bundler_native_gemfile_requirement_is_accepted():
    payload = _valid_bundler_payload()

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"Bundler native Gemfile requirement rejected: {errors}"


def test_bundler_gemspec_requirement_is_native():
    payload = _valid_bundler_payload()
    payload["selected_remediation"]["affected_manifests"] = [
        "Gemfile",
        "Gemfile.lock",
        "example.gemspec",
    ]
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.gemspec_requirement",
            "version_control",
            semantic_effect="native_version_control",
            evidence=["addressable declared via add_dependency in example.gemspec"],
        )
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"gemspec add_dependency rejected as native control: {errors}"


def test_bundler_manipulations_are_mechanism_driven():
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["type"] = "exclusion"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].type: must be null for Bundler manipulations" in error for error in errors
    )

    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: required for Bundler manipulations" in error for error in errors
    )

    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "bundler.magic"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    # Cross-manager mechanism smuggling fails closed in both directions.
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "nuget.transitive_pin"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_bundler_transitive_pin_requires_mediation_evidence():
    # Bundler unifies the whole graph: a Gemfile entry added only to force a
    # transitive's resolved version is mediation, never version control.
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.transitive_pin",
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
        "classification: direct Bundler overrides require mediation evidence" in error
        for error in errors
    ), "bundler.transitive_pin masqueraded as version_control"

    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.transitive_pin",
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
        "dependency_graph_audit.status: declared Bundler graph mediation requires validation_required"
        in errors
    )


def test_bundler_unverified_override_blocks():
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.transitive_pin",
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
        "dependency_graph_audit.status: unverified Bundler direct overrides require blocked"
        in errors
    )


def test_bundler_lockfile_edit_requires_lockfile_override_effect():
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.lockfile_edit",
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
    ), "a hand-edited Gemfile.lock accepted a mediation-only semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "lockfile_override"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_bundler_source_redirections_require_source_override_effect():
    # A per-gem git:/github:/path: redirect keeps the gem's name and swaps
    # where its code comes from; a source-block swap redirects the registry
    # itself. Both are source overrides, never substitutions.
    for mechanism in ("bundler.source_redirect", "bundler.gem_source"):
        payload = _valid_bundler_payload()
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _bundler_manipulation(
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


def test_bundler_require_false_requires_asset_suppression_effect():
    # `require: false` never removes the gem from the graph — it stays
    # resolved and pinned in Gemfile.lock while its auto-require at boot is
    # suppressed. The effect is asset suppression, not dependency_removal,
    # and the removal safety machinery still applies.
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.require_false",
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
        "semantic_effect: must be asset_or_feature_suppression for Bundler "
        "require_false manipulations" in error
        for error in errors
    ), "require: false accepted a dependency_removal semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "asset_or_feature_suppression"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_bundler_unverified_removal_blocks():
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.require_false",
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
        "dependency_graph_audit.status: unverified Bundler exclusions require blocked"
        in errors
    )


def test_bundler_removals_require_graph_and_runtime_validation():
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.require_false",
            "unverified",
            semantic_effect="asset_or_feature_suppression",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "Bundler exclusions require resolved_graph and runtime_linkage" in error
        for error in errors
    )


def test_bundler_removal_replacement_requires_exact_gem_coordinate():
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.require_false",
            "replacement_declared",
            semantic_effect="asset_or_feature_suppression",
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
        "gem://sanitize@6.0.0",
        "sanitize",
        "sanitize@6",
        "sanitize@~> 6.0",
        "sanitize@>=6.0.0",
        "sanitize@6.0.*",
        "use the maintained gem",
        "org.owasp:sanitizer:1.0",
        "github.com/rgrove/sanitize@v6.0.0",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            bad_replacement
        )

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].replacement: must be an exact gem@version coordinate" in error
            for error in errors
        ), f"Bundler replacement accepted non-canonical form {bad_replacement!r}"

    for good_replacement in (
        "sanitize@6.0.0",
        "rails-html-sanitizer@1.4.4",
        "activesupport@7.0.4.3",
        "rack@2.2",
        "some_gem@1.2.3.rc1",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            good_replacement
        )

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"exact Bundler replacement {good_replacement!r} rejected"


def test_bundler_replacement_declared_status_coupling():
    payload = _valid_bundler_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _bundler_manipulation(
            "bundler.require_false",
            "replacement_declared",
            semantic_effect="asset_or_feature_suppression",
            replacement="sanitize@6.0.0",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared Bundler replacements require "
        "validation_required" in errors
    )


def test_bundler_removal_and_substitution_effects_never_claimable():
    # Bundler has no construct that removes a graph node (deleting the gem
    # line is a manifest edit) and no rename construct (a git fork redirect
    # keeps the gem name): dependency_removal and dependency_substitution
    # must not be claimable through Bundler mechanisms.
    for effect in ("dependency_removal", "dependency_substitution"):
        payload = _valid_bundler_payload()
        payload["dependency_graph_audit"]["status"] = "blocked"
        payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
        payload["dependency_graph_audit"]["manipulations"] = [
            _bundler_manipulation(
                "bundler.require_false", "unverified", semantic_effect=effect
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].semantic_effect: must be" in error for error in errors
        ), f"require_false accepted {effect}"

    kinds = set(BUNDLER_PROFILE.mechanisms.values())
    assert "substitution" not in kinds, "the Bundler profile claims a substitution construct"
    assert "removal" in kinds, "the Bundler profile lost its suppression construct"
    # Every removal-kind mechanism is pinned to asset suppression.
    for mechanism, kind in BUNDLER_PROFILE.mechanisms.items():
        if kind == "removal":
            assert BUNDLER_PROFILE.mechanism_semantic_effects[mechanism] == frozenset(
                {"asset_or_feature_suppression"}
            )


def test_bundler_inventory_ecosystem_must_be_exactly_gem():
    payload = _valid_bundler_payload()
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "bundler"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be gem for Bundler remediations"
        in errors
    )


def test_bundler_unavailable_audit_cannot_be_low_risk():
    payload = _valid_bundler_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable Bundler dependency graph audit cannot be approved_low_risk"
        in errors
    )


def test_disguised_bundler_manifests_still_count_as_strong_signals():
    # Inherited red-team hardening: padded, zero-width-embellished,
    # trailing-dot, and Windows dot-and-space manifest names keep their
    # strong signals — including on the .gemspec suffix channel.
    for disguised in (
        "Gemfile ",
        " Gemfile.lock",
        "gems.rb​",
        "Gemfile.",
        "Gemfile .",
        "lib/example.gemspec  ..  ",
        "lib/example.ｇｅｍｓｐｅｃ",
    ):
        detections = _detect(manifests=(disguised,))
        assert [d.profile.name for d in detections] == ["bundler"], (
            f"disguised manifest {disguised!r} lost its strong bundler signal"
        )

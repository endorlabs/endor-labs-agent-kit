from __future__ import annotations

from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    GO_PROFILE,
    SUPPORTED_PROFILES,
    detect_package_managers,
)


def _valid_go_payload() -> dict:
    return {
        "summary": "Gate 1 selection plan for golang.org/x/text in a Go-modules service.",
        "selected_remediation": {
            "package": "golang.org/x/text",
            "from_version": "v0.3.5",
            "to_version": "v0.3.8",
            "upgrade_risk": "low",
            "cia_status": "no breaking changes",
            "findings_fixed": 1,
            "finding_instances_fixed": 1,
            "unique_advisories_fixed": 1,
            "fixed_finding_uuids": ["6a60c9445beb5fb713450081"],
            "findings_introduced": 0,
            "conflicts": 0,
            "uia_uuid": "version-upgrade-fixture-005",
            "project_uuid": "project-fixture-webapp-005",
            "namespace": "tenant-a",
            "manifests": ["go.mod"],
            "affected_manifests": ["go.mod", "go.sum"],
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-005",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp-go",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Patch-level bump governed by the require directive; build and test before PR.",
            "source_usage_summary": "Local source imports golang.org/x/text/language directly; no graph manipulations beyond the require directive.",
            "validation_requirements": [
                "go mod why golang.org/x/text",
                "go test ./...",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-005",
                "upgrade_risk": "low",
                "cia_status": "no breaking changes",
                "findings_fixed": 1,
                "finding_instances_fixed": 1,
                "unique_advisories_fixed": 1,
                "fixed_finding_uuids": ["6a60c9445beb5fb713450081"],
                "findings_introduced": 0,
            }
        ],
        "dependency_graph_audit": {
            "package_manager": "go",
            "status": "clear",
            "manifest": "go.mod",
            "dependency_path": [
                "go://example.com/webapp@v1.0.0",
                "go://golang.org/x/text@v0.3.8",
            ],
            "manipulations": [
                {
                    "type": None,
                    "coordinate": "golang.org/x/text",
                    "classification": "version_control",
                    "semantic_effect": "native_version_control",
                    "mechanism": "go.require_directive",
                    "replacement": None,
                    "evidence": ["golang.org/x/text version declared directly in go.mod"],
                }
            ],
            "validation_requirements": [],
        },
        "patch_plan": [
            {
                "file": "go.mod",
                "branch_name": "remediation/sca/golang.org-x-text-v0.3.8",
            }
        ],
        "validation": [
            {
                "command": "go mod why golang.org/x/text",
                "status": "planned",
                "purpose": "Confirm golang.org/x/text resolves to v0.3.8",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "branch": "not_created",
                "proposed_branch": "remediation/sca/golang.org-x-text-v0.3.8",
                "inventory": {
                    "status": "none_found",
                    "lookup_method": "source provider branch and change-request inventory",
                    "checked_at": "2026-08-19T12:00:00Z",
                    "fresh_recheck": False,
                    "key": {
                        "repository": "example/webapp-go",
                        "base_branch": "main",
                        "ecosystem": "go",
                        "normalized_package": "go://golang.org/x/text",
                        "manifest": "go.mod",
                        "current_version": "v0.3.5",
                        "target_version": "v0.3.8",
                        "finding_set": [],
                    },
                    "candidates": [],
                    "reconciliation": {
                        "status": "not_needed",
                        "reason": "No existing candidate found.",
                        "selected_target_version": "v0.3.8",
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


def _go_manipulation(mechanism: str, classification: str, **overrides) -> dict:
    manipulation = {
        "type": None,
        "coordinate": "golang.org/x/text",
        "classification": classification,
        "semantic_effect": overrides.pop("semantic_effect", None),
        "mechanism": mechanism,
        "replacement": overrides.pop("replacement", None),
        "evidence": ["observed in go.mod"],
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


def test_go_profile_registered_as_single_manager_family():
    # The newest profile file (NuGet) pins the exact registry; this asserts
    # the Go-era profiles all remain registered.
    names = {profile.name for profile in SUPPORTED_PROFILES}
    assert names >= {
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
    }

    assert GO_PROFILE.type_driven is False
    assert GO_PROFILE.semantic_effect_required is True
    # Go modules are a single-manager family: no registry-family split, so
    # the canonical inventory ecosystem is the manager name itself and there
    # are no shared weak signals.
    assert GO_PROFILE.canonical_ecosystem == "go"
    assert GO_PROFILE.shared_ecosystem_aliases == frozenset()
    assert GO_PROFILE.shared_manifest_basenames == frozenset()


def test_go_manifest_and_ecosystem_detection_is_strong():
    for manifest in ("go.mod", "go.sum", "go.work", "go.work.sum"):
        detections = _detect(manifests=(manifest,))
        assert [d.profile.name for d in detections] == ["go"], (
            f"{manifest} should identify exactly go: "
            f"{[d.profile.name for d in detections]}"
        )

    for token in ("go", "golang", "ECOSYSTEM_GO", "go-modules"):
        detections = _detect(ecosystem_tokens=(token,))
        assert [d.profile.name for d in detections] == ["go"], (
            f"ecosystem token {token!r} should identify exactly go"
        )

    # The canonical inventory token is exactly `go`; aliases are detection
    # signals but non-canonical for the duplicate-inventory key.
    assert _detect(ecosystem_tokens=("go",))[0].ecosystem_is_canonical is True
    assert _detect(ecosystem_tokens=("golang",))[0].ecosystem_is_canonical is False


def test_go_coordinates_are_weak_signals_only():
    detections = _detect(coordinates=("go://golang.org/x/text@v0.3.8",))
    go_detections = [d for d in detections if d.profile.name == "go"]
    assert len(go_detections) == 1
    assert set(go_detections[0].signals) == {"coordinate"}


def test_go_lockfiles_do_not_bleed_into_other_families():
    detections = _detect(manifests=("go.mod", "poetry.lock"))
    assert {d.profile.name for d in detections} == {"go", "poetry"}

    payload = _valid_go_payload()
    payload["selected_remediation"]["affected_manifests"] = [
        "go.mod",
        "go.sum",
        "poetry.lock",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "conflicting go and poetry manifests did not fail closed"


def test_go_package_manager_schema_enum_includes_go():
    contract = compile_profile_contract("sca-remediation", "selection-plan")
    audit = contract.provider_neutral_schema["properties"]["dependency_graph_audit"]
    assert set(audit["properties"]["package_manager"]["enum"]) >= {
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
        None,
    }


def test_go_selection_requires_dependency_graph_audit():
    payload = _valid_go_payload()
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected Go remediations" in errors
    ), "Go signals (go ecosystem + go.mod) did not engage the audit"


def test_go_native_require_directive_is_accepted():
    payload = _valid_go_payload()

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"Go native require directive rejected: {errors}"


def test_go_manipulations_are_mechanism_driven():
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["type"] = "exclusion"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].type: must be null for Go manipulations" in error for error in errors
    )

    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: required for Go manipulations" in error for error in errors
    )

    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "go.magic"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    # Cross-manager mechanism smuggling fails closed in both directions.
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "pip.constraints_pin"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_go_replace_version_and_exclude_require_mediation_evidence():
    # `replace` to another version of the same module and `exclude` both
    # mediate MVS version selection: exclude removes a version from the
    # candidate set, never the module node, so it is an override construct,
    # not a removal.
    for mechanism in ("go.replace_version", "go.exclude_directive"):
        payload = _valid_go_payload()
        payload["dependency_graph_audit"]["manipulations"] = [
            _go_manipulation(
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
            "classification: direct Go overrides require mediation evidence" in error
            for error in errors
        ), f"{mechanism} masqueraded as version_control"

    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.exclude_directive",
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
        "dependency_graph_audit.status: declared Go graph mediation requires validation_required"
        in errors
    )


def test_go_unverified_override_blocks():
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.exclude_directive",
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
        "dependency_graph_audit.status: unverified Go direct overrides require blocked"
        in errors
    )


def test_go_sum_edit_requires_lockfile_override_effect():
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.sum_edit",
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
    ), "a hand-edited go.sum accepted a mediation-only semantic effect"

    payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
        "lockfile_override"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_go_source_redirections_require_source_override_effect():
    for mechanism in ("go.replace_path", "go.work_replace", "go.vendor_override"):
        payload = _valid_go_payload()
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _go_manipulation(
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


def test_go_replace_module_requires_exact_module_replacement():
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
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
        "go://github.com/golang-jwt/jwt@v3.2.1+incompatible",
        "github.com/golang-jwt/jwt",
        "github.com/golang-jwt/jwt@latest",
        "github.com/golang-jwt/jwt@master",
        "github.com/golang-jwt/jwt@v3",
        "use the maintained fork",
        "org.slf4j:jcl-over-slf4j:1.7.36",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            bad_replacement
        )

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].replacement: must be an exact module@version coordinate" in error
            for error in errors
        ), f"Go replacement accepted non-canonical form {bad_replacement!r}"

    for good_replacement in (
        "github.com/golang-jwt/jwt@v3.2.1+incompatible",
        "github.com/golang-jwt/jwt/v4@v4.5.0",
        "golang.org/x/text@v0.3.8",
        "example.com/fork@v0.0.0-20260819120000-abcdef123456",
    ):
        payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
            good_replacement
        )

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"exact Go replacement {good_replacement!r} rejected"


def test_go_substitution_status_coupling():
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            replacement="github.com/golang-jwt/jwt/v4@v4.5.0",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: declared Go substitutions require validation_required"
        in errors
    )

    payload["dependency_graph_audit"]["manipulations"][0]["classification"] = (
        "unverified"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit.status: unverified Go substitutions require blocked"
        in errors
    )


def test_go_semantic_effect_dependency_removal_is_rejected():
    # `exclude` removes a version from MVS candidates, never the module
    # node, and no other Go construct removes a graph node either:
    # dependency_removal must not be claimable through Go mechanisms.
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["status"] = "blocked"
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.exclude_directive", "unverified", semantic_effect="dependency_removal"
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].semantic_effect: must be" in error for error in errors)

    kinds = set(GO_PROFILE.mechanisms.values())
    assert "removal" not in kinds, "the Go profile claims a removal construct"


def test_go_inventory_ecosystem_must_be_exactly_go():
    payload = _valid_go_payload()
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "golang"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be go for Go remediations"
        in errors
    )


def test_go_unavailable_audit_cannot_be_low_risk():
    payload = _valid_go_payload()
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable Go dependency graph audit cannot be approved_low_risk"
        in errors
    )


def test_disguised_go_manifests_still_count_as_strong_signals():
    # Inherited red-team hardening: padded, zero-width-embellished, and
    # trailing-dot manifest names keep their strong signals.
    for disguised in ("go.mod ", " go.sum", "go.mod​", "go.sum."):
        detections = _detect(manifests=(disguised,))
        assert [d.profile.name for d in detections] == ["go"], (
            f"disguised manifest {disguised!r} lost its strong go signal"
        )


def test_disguised_ecosystem_token_does_not_dodge_ambiguity_gate():
    # Red-team finding: _normalize_ecosystem lacked the NFKC/Cf hardening
    # _manifest_basename got, so a conflicting second-manager ecosystem token
    # disguised with a fullwidth lookalike or zero-width space was not
    # recognized, the second profile never detected, and the ambiguity gate
    # never fired — the payload validated as pure Go.
    import copy

    for disguised in ("ｐｏｅｔｒｙ", "poetry​"):
        payload = _valid_go_payload()
        conflicting = copy.deepcopy(payload["change_requests"][0])
        conflicting["inventory"]["key"]["ecosystem"] = disguised
        conflicting["inventory"]["key"]["manifest"] = "pyproject.toml"
        conflicting["inventory"]["key"]["normalized_package"] = "pypi://requests"
        payload["change_requests"].append(conflicting)

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "ambiguous package-manager signals" in error for error in errors
        ), f"disguised ecosystem token {disguised!r} dodged the ambiguity gate"


def test_non_list_manipulations_claim_content_and_fail_closed():
    # Red-team finding: the self-declared pass-through computed
    # claims_content with bool(_list(manipulations)), and _list() coerces a
    # dict or string to [], so a content-bearing manipulation emitted as a
    # non-list rode through unvalidated when the declared manager was
    # unresolvable and status was unavailable.
    def scrubbed_payload(manipulations):
        payload = _valid_go_payload()
        key = payload["change_requests"][0]["inventory"]["key"]
        key["ecosystem"] = "golang-ish"
        key["manifest"] = "app/deps.list"
        key["normalized_package"] = "golang.org/x/text"
        payload["selected_remediation"]["manifests"] = ["app/deps.list"]
        payload["selected_remediation"]["affected_manifests"] = ["app/deps.list"]
        payload["patch_plan"][0]["file"] = "app/deps.list"
        payload["dependency_graph_audit"]["package_manager"] = "golang"
        payload["dependency_graph_audit"]["status"] = "unavailable"
        payload["dependency_graph_audit"]["manifest"] = None
        payload["dependency_graph_audit"]["manipulations"] = manipulations
        return payload

    substitution_object = {
        "type": None,
        "mechanism": "go.replace_module",
        "classification": "unverified",
        "semantic_effect": "dependency_substitution",
        "replacement": "evil.example/pkg@v1.0.0",
    }
    for manipulations in (
        substitution_object,
        "go.replace_module -> evil.example/pkg@v1.0.0",
    ):
        errors = validate_sca_gate_payload(
            scrubbed_payload(manipulations), gate="selection-plan"
        )

        assert any(
            "dependency_graph_audit.package_manager: must be one of" in error
            for error in errors
        ), f"non-list manipulations {manipulations!r} skipped the fail-closed gate"

    # The honest shape stays accepted: unavailable, an empty manipulations
    # list, and a fail-closed risk decision.
    payload = scrubbed_payload([])
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_go_self_declared_audit_is_validated_when_signals_are_scrubbed():
    payload = _valid_go_payload()
    key = payload["change_requests"][0]["inventory"]["key"]
    key["ecosystem"] = "golang-ish"
    key["manifest"] = "app/deps.list"
    key["normalized_package"] = "golang.org/x/text"
    payload["selected_remediation"]["manifests"] = ["app/deps.list"]
    payload["selected_remediation"]["affected_manifests"] = ["app/deps.list"]
    payload["dependency_graph_audit"]["manifest"] = "app/deps.list"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_version",
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
        "dependency_graph_audit.status: unverified Go direct overrides require blocked"
        in errors
    ), "scrubbing every detection signal skipped validation of a self-declared Go audit"

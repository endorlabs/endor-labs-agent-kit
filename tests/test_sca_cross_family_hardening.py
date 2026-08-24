"""Phase-8 cross-family hardening: engine-wide seams found by per-family
red-teams but deferred because they predate the profile under review."""

from __future__ import annotations

import copy

from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    SUPPORTED_PROFILES,
)
from test_sca_go_contracts import _go_manipulation, _valid_go_payload
from test_sca_node_contracts import _node_manipulation, _valid_node_payload


def test_every_replacement_pattern_rejects_fullwidth_digits():
    # Deferred from the NuGet red-team: \d and \w are unicode-aware by
    # default, so a fullwidth lookalike digit slipped the "exact version"
    # pin on the pre-ASCII families. Every family's pattern must reject
    # non-ASCII lookalikes in both the name and version halves.
    lookalikes = {
        "maven": "org.slf4j:jcl-over-slf4j:1.7.3６",
        "gradle": "org.slf4j:jcl-over-slf4j:1.7.3６",
        "npm": "qs@6.11.０",
        "yarn": "qs@6.11.０",
        "pnpm": "qs@6.11.０",
        "pip": "jinja2==2.11.３",
        "poetry": "jinja2==2.11.３",
        "pipenv": "jinja2==2.11.３",
        "uv": "jinja2==2.11.３",
        "go": "github.com/golang-jwt/jwt@v3.2.１",
        "nuget": "Newtonsoft.Json@13.0.１",
        "bundler": "addressable@2.8.０",
        "cargo": "regex@1.5.５",
    }
    for profile in SUPPORTED_PROFILES:
        disguised = lookalikes[profile.name]
        assert profile.replacement_pattern.fullmatch(disguised) is None, (
            f"{profile.name} replacement pattern accepted fullwidth digits: "
            f"{disguised!r}"
        )


def test_fullwidth_replacement_rejected_at_the_gate():
    # Payload-level confirmation on one pre-ASCII family: a disguised Go
    # replacement must fail the exact-coordinate check, not validate clean.
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            replacement="github.com/golang-jwt/jwt@v3.2.１",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].replacement: must be an exact module@version coordinate" in error
        for error in errors
    ), "a fullwidth-disguised Go replacement passed the exact-coordinate pin"


def test_null_selected_remediation_cannot_claim_created_change_request():
    # Deferred from the Bundler red-team: with selected_remediation null and
    # selection_blocked unset, the whole remediation block was skipped, so a
    # payload could claim a CREATED change request (and carry a dangerous
    # audit) while validating clean. The contract's no-selection shape is
    # selection_blocked: true, which already fails closed.
    payload = _valid_go_payload()
    payload["selected_remediation"] = None
    payload["change_requests"][0]["status"] = "created"
    payload["change_requests"][0]["branch"] = "remediation/sca/x-1"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "change_requests: a created or reused change request requires a "
        "selected remediation or selection_blocked" in error
        for error in errors
    ), "a created change request rode through with no selected remediation"


def test_supplied_audit_is_validated_without_selected_remediation():
    # Companion seam: a dependency_graph_audit supplied alongside a null
    # selection must still run through the audit state machine instead of
    # being skipped wholesale.
    payload = _valid_go_payload()
    payload["selected_remediation"] = None
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
    ), "a dangerous audit was skipped because selected_remediation was null"


def test_replacement_must_not_restate_the_vulnerable_coordinate():
    # Deferred from the Cargo red-team: a declared replacement equal to the
    # audited coordinate at the remediation's own from_version is a
    # deceptive no-op — it "replaces" the vulnerable state with itself.
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            coordinate="golang.org/x/text",
            replacement="golang.org/x/text@v0.3.5",  # == from_version
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].replacement: must not restate the audited coordinate at its "
        "vulnerable version" in error
        for error in errors
    ), "a self-referential replacement at the vulnerable version validated clean"

    # A same-name replacement at a DIFFERENT version stays legitimate (the
    # Node alias-pin pattern: npm:qs@6.11.0 fixing qs@6.7.0).
    payload["dependency_graph_audit"]["manipulations"][0]["replacement"] = (
        "golang.org/x/text@v0.3.8"
    )

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_same_name_alias_pin_at_fixed_version_stays_accepted():
    # Regression guard for the narrow scope of the self-referential rule:
    # the Phase-2 Node fixture's legitimate alias remediation (qs aliased to
    # npm:qs@6.11.0 while from_version is 6.7.0) must keep validating.
    payload = _valid_node_payload("npm")
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _node_manipulation(
            "npm.alias_redirect",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            coordinate="qs",
            replacement="qs@6.11.0",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"legitimate same-name alias pin rejected: {errors}"


def test_restatement_check_survives_coordinate_scrubbing():
    # Final-pass red-team finding: the restatement guard anchored only on
    # the model-controlled optional `coordinate` field, so omitting it (or
    # scheme-decorating it) silently disabled the rule. The trusted anchor
    # is the selected remediation's own package identity.
    for coordinate in (None, "", "go://golang.org/x/text"):
        payload = _valid_go_payload()
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _go_manipulation(
                "go.replace_module",
                "replacement_declared",
                semantic_effect="dependency_substitution",
                coordinate=coordinate,
                replacement="golang.org/x/text@v0.3.5",  # == from_version
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "must not restate the audited coordinate at its vulnerable version"
            in error
            for error in errors
        ), f"coordinate {coordinate!r} disabled the restatement guard"


def test_restatement_check_survives_version_shape_dodges():
    # Final-pass red-team findings: case-variant names on case-insensitive
    # ecosystems and trailing-.0 version padding dodged the exact string
    # compare, and blanking from_version dodged it entirely (the inventory
    # key's current_version is an equally trusted source).
    from test_sca_nuget_contracts import _nuget_manipulation, _valid_nuget_payload

    for replacement in (
        "Newtonsoft.Json@12.0.2.0",  # trailing-.0 padding
        "newtonsoft.json@12.0.2",  # case variant (NuGet IDs are case-insensitive)
    ):
        payload = _valid_nuget_payload()
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _nuget_manipulation(
                "nuget.package_remove",
                "replacement_declared",
                semantic_effect="dependency_removal",
                coordinate=None,
                replacement=replacement,
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "must not restate the audited coordinate at its vulnerable version"
            in error
            for error in errors
        ), f"replacement {replacement!r} dodged the restatement guard"

    # Blanking from_version: the change-request inventory current_version
    # still names the vulnerable version.
    payload = _valid_go_payload()
    payload["selected_remediation"]["from_version"] = ""
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            coordinate=None,
            replacement="golang.org/x/text@v0.3.5",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "must not restate the audited coordinate at its vulnerable version" in error
        for error in errors
    ), "blanking from_version disabled the restatement guard"


def test_non_dict_audit_fails_closed_without_selection():
    # Final-pass red-team finding: with a null selection, a dangerous audit
    # wrapped in a list (or emitted as a string) skipped the entire audit
    # block because audit_present required a dict.
    for wrapper in (lambda d: [d], lambda d: "see attached audit"):
        payload = _valid_go_payload()
        audit = payload["dependency_graph_audit"]
        payload["selected_remediation"] = None
        payload["change_requests"][0]["status"] = "not_created"
        payload["dependency_graph_audit"] = wrapper(audit)

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "dependency_graph_audit: must be an object" in error for error in errors
        ), f"non-dict audit shape {type(payload['dependency_graph_audit']).__name__} rode through"


def test_non_list_change_requests_fails_closed():
    # Final-pass red-team finding: _list() coerces a non-list container to
    # [], so change_requests emitted as a single object dodged the
    # created-CR guards AND the inventory validation entirely.
    payload = _valid_go_payload()
    payload["change_requests"] = payload["change_requests"][0]
    payload["change_requests"]["status"] = "created"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "change_requests: must be an array" in error for error in errors
    ), "a non-list change_requests container dodged the guards"


def test_restatement_check_survives_full_identity_scrubbing():
    # Verification-round finding: scrubbing coordinate AND the selection's
    # package identity collapsed the name-anchor set to empty, so the guard
    # never fired even though the vulnerable version was known. The
    # inventory key's normalized_package is an equally trusted name source,
    # and when every name source has been scrubbed while the replacement
    # matches a known vulnerable version, the only honest reading is
    # deception — fail closed.
    # Variant 1: selection kept but package identity deleted.
    payload = _valid_go_payload()
    del payload["selected_remediation"]["package"]
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            coordinate=None,
            replacement="golang.org/x/text@v0.3.5",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "must not restate the audited coordinate at its vulnerable version" in error
        for error in errors
    ), "deleting selected_remediation.package disabled the restatement guard"

    # Variant 2: null selection, identity only in the inventory key.
    payload = _valid_go_payload()
    payload["selected_remediation"] = None
    payload["change_requests"][0]["status"] = "not_created"
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            coordinate=None,
            replacement="golang.org/x/text@v0.3.5",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "must not restate the audited coordinate at its vulnerable version" in error
        for error in errors
    ), "null selection + scrubbed coordinate disabled the restatement guard"

    # Regression guard for the empty-names fallback: a DIFFERENT package's
    # replacement at a coincidentally equal version stays legitimate when
    # any name source is present.
    payload = _valid_go_payload()
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _go_manipulation(
            "go.replace_module",
            "replacement_declared",
            semantic_effect="dependency_substitution",
            coordinate="golang.org/x/text",
            replacement="example.com/other-module@v0.3.5",  # different package
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_disguised_change_request_status_still_claims():
    # Verification-round finding: a zero-width character inside the status
    # token dodged the created-CR guard's literal compare. Status tokens go
    # through the same disguise folding as the other identity channels.
    payload = _valid_go_payload()
    payload["selected_remediation"] = None
    payload["change_requests"][0]["status"] = "created​"  # embedded zero-width
    payload["change_requests"][0]["branch"] = "remediation/sca/x-1"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "created or reused change request requires" in error for error in errors
    ), "a disguised status token dodged the created-CR guard"


def test_honest_empty_payload_shapes_stay_accepted():
    # The null-selection hardening must not break honest shapes: a payload
    # with no selection, no selection_blocked, no audit, and no claimed
    # change request keeps whatever validity it had before.
    payload = _valid_go_payload()
    baseline_errors = validate_sca_gate_payload(payload, gate="selection-plan")
    assert baseline_errors == []

    stripped = copy.deepcopy(payload)
    stripped["selected_remediation"] = None
    stripped.pop("dependency_graph_audit")
    stripped["change_requests"][0]["status"] = "not_created"

    errors = validate_sca_gate_payload(stripped, gate="selection-plan")

    assert not any("created or reused change request requires" in e for e in errors)
    assert not any("dependency_graph_audit" in e for e in errors)

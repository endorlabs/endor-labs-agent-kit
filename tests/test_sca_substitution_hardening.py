"""PR 51 review follow-up: the substitution rules in the shared audit engine
each had a tested removal/override sibling while the substitution twin ran
uncovered, and `replacement_conflict_or_incomplete` had zero hits anywhere.
These tests drive every substitution branch and the input-hardening seams."""

from __future__ import annotations

from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    GO_PROFILE,
    GRADLE_PROFILE,
    validate_dependency_graph_audit,
)


def _run(profile, audit, *, risk_status="approved_with_validation_required",
         validated_kinds=()):
    errors: list[str] = []
    validate_dependency_graph_audit(
        profile,
        audit=audit,
        selected_manifests={"go.mod", "build.gradle"},
        risk_status=risk_status,
        successful_validation_kinds=set(validated_kinds),
        errors=errors,
    )
    return errors


def _audit(manipulations, *, status, manifest="go.mod",
           validation_requirements=("resolved_graph", "runtime_linkage")):
    return {
        "package_manager": "go",
        "status": status,
        "manifest": manifest,
        "dependency_path": [],
        "manipulations": list(manipulations),
        "validation_requirements": list(validation_requirements),
    }


def _go_substitution(classification, *, semantic_effect="dependency_substitution",
                     replacement="golang.org/x/crypto@v0.17.0", **overrides):
    manipulation = {
        "type": None,
        "coordinate": "golang.org/x/text",
        "classification": classification,
        "semantic_effect": semantic_effect,
        "mechanism": "go.replace_module",
        "replacement": replacement,
        "evidence": ["replace directive observed in go.mod"],
    }
    manipulation.update(overrides)
    return manipulation


def _gradle_exclusion(classification, *, semantic_effect="dependency_removal",
                      replacement=None, **overrides):
    manipulation = {
        "type": None,
        "coordinate": "org.apache.logging.log4j:log4j-core",
        "classification": classification,
        "semantic_effect": semantic_effect,
        "mechanism": "gradle.exclusion",
        "replacement": replacement,
        "evidence": ["exclude group observed in build.gradle"],
    }
    manipulation.update(overrides)
    return manipulation


def test_substitution_with_removal_only_classification_is_rejected():
    audit = _audit(
        [_go_substitution("not_needed_verified", replacement=None)],
        status="clear",
    )

    errors = _run(GO_PROFILE, audit)

    assert (
        "dependency_graph_audit.manipulations[0].classification: Go substitutions "
        "require replacement evidence" in errors
    )


def test_invalid_semantic_effect_token_is_rejected():
    audit = _audit(
        [_go_substitution("replacement_declared", semantic_effect="graph_rewrite")],
        status="validation_required",
    )

    errors = _run(GO_PROFILE, audit)

    assert any(
        error.startswith(
            "dependency_graph_audit.manipulations[0].semantic_effect: must be one of"
        )
        for error in errors
    )


def test_unmapped_mechanism_substitution_requires_substitution_effect():
    # go.replace_module has no mechanism_semantic_effects entry, so the
    # kind-level coupling is the only guard: a substitution wearing a
    # removal effect must be rejected.
    audit = _audit(
        [_go_substitution("replacement_declared", semantic_effect="dependency_removal")],
        status="validation_required",
    )

    errors = _run(GO_PROFILE, audit)

    assert (
        "dependency_graph_audit.manipulations[0].semantic_effect: must be "
        "dependency_substitution for Go substitutions" in errors
    )


def test_substitution_without_graph_runtime_validation_is_rejected():
    audit = _audit(
        [_go_substitution("replacement_declared")],
        status="validation_required",
        validation_requirements=(),
    )

    errors = _run(GO_PROFILE, audit)

    assert (
        "dependency_graph_audit.validation_requirements: Go substitutions "
        "require resolved_graph and runtime_linkage" in errors
    )


def test_verified_substitution_requires_validated_status():
    audit = _audit(
        [_go_substitution("replacement_verified")],
        status="validation_required",
    )

    errors = _run(GO_PROFILE, audit)

    assert (
        "dependency_graph_audit.status: verified Go substitutions require "
        "validated" in errors
    )


def test_conflicted_substitution_forces_blocked():
    audit = _audit(
        [_go_substitution("replacement_conflict_or_incomplete", replacement=None)],
        status="clear",
    )

    errors = _run(GO_PROFILE, audit)

    assert (
        "dependency_graph_audit.status: unverified Go substitutions require "
        "blocked" in errors
    )


def test_conflicted_removal_forces_blocked():
    audit = _audit(
        [_gradle_exclusion("replacement_conflict_or_incomplete")],
        status="clear",
        manifest="build.gradle",
    )

    errors = _run(GRADLE_PROFILE, audit)

    assert (
        "dependency_graph_audit.status: unverified Gradle exclusions require "
        "blocked" in errors
    )


def test_verified_removal_replacement_requires_validated():
    audit = _audit(
        [
            _gradle_exclusion(
                "replacement_verified",
                semantic_effect="dependency_substitution",
                replacement="org.slf4j:jcl-over-slf4j:1.7.36",
            )
        ],
        status="validation_required",
        manifest="build.gradle",
    )

    errors = _run(GRADLE_PROFILE, audit)

    assert (
        "dependency_graph_audit.status: verified Gradle replacements require "
        "validated" in errors
    )


def test_validated_override_requires_passed_graph_validation():
    audit = _audit(
        [
            _go_substitution(
                "mediation_verified",
                semantic_effect="forced_version_mediation",
                mechanism="go.replace_version",
                replacement=None,
            )
        ],
        status="validated",
    )

    errors = _run(GO_PROFILE, audit, validated_kinds=())

    assert (
        "dependency_graph_audit: validated Go direct overrides require "
        "passed resolved_graph and runtime_linkage validation" in errors
    )


def test_validated_substitution_requires_passed_graph_validation():
    audit = _audit(
        [_go_substitution("replacement_verified")],
        status="validated",
    )

    errors = _run(GO_PROFILE, audit, validated_kinds=("resolved_graph",))

    assert (
        "dependency_graph_audit: validated Go substitutions require "
        "passed resolved_graph and runtime_linkage validation" in errors
    )


def test_non_dict_manipulation_entry_fails_closed():
    audit = _audit(["replace golang.org/x/text"], status="clear")

    errors = _run(GO_PROFILE, audit)

    assert "dependency_graph_audit.manipulations[0]: must be an object" in errors


def test_profile_matchers_fail_closed_on_non_string_input():
    assert GO_PROFILE.kind_of(None, "go.replace_module") is None
    assert GO_PROFILE.kind_of("replace", None) is None
    assert GO_PROFILE.matches_shared_ecosystem("golang") is False
    assert GO_PROFILE.matches_shared_manifest("go.mod") is False
    assert GO_PROFILE.matches_shared_manifest(123) is False
    assert GO_PROFILE.matches_manifest(123) is False
    assert GO_PROFILE.matches_coordinate(None) is False

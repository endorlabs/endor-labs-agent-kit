from __future__ import annotations

from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.workflow_output_contracts.sca.package_managers import (
    PIP_PROFILE,
    PIPENV_PROFILE,
    POETRY_PROFILE,
    SUPPORTED_PROFILES,
    UV_PROFILE,
    detect_package_managers,
)

_PYTHON_MANAGERS = ("pip", "poetry", "pipenv", "uv")
_PYTHON_PROFILES = (PIP_PROFILE, POETRY_PROFILE, PIPENV_PROFILE, UV_PROFILE)


def _valid_python_payload(manager: str = "pip") -> dict:
    manifests = {
        "pip": ["requirements.txt"],
        "poetry": ["pyproject.toml"],
        "pipenv": ["Pipfile"],
        "uv": ["pyproject.toml"],
    }[manager]
    affected = {
        "pip": ["requirements.txt"],
        "poetry": ["pyproject.toml", "poetry.lock"],
        "pipenv": ["Pipfile", "Pipfile.lock"],
        "uv": ["pyproject.toml", "uv.lock"],
    }[manager]
    return {
        "summary": f"Gate 1 selection plan for urllib3 in a {manager}-managed service.",
        "selected_remediation": {
            "package": "urllib3",
            "from_version": "1.26.4",
            "to_version": "1.26.19",
            "upgrade_risk": "low",
            "cia_status": "no breaking changes",
            "findings_fixed": 1,
            "finding_instances_fixed": 1,
            "unique_advisories_fixed": 1,
            "fixed_finding_uuids": ["6a60c9445beb5fb713450071"],
            "findings_introduced": 0,
            "conflicts": 0,
            "uia_uuid": "version-upgrade-fixture-004",
            "project_uuid": "project-fixture-webapp-004",
            "namespace": "tenant-a",
            "manifests": manifests,
            "affected_manifests": affected,
        },
        "project_resolution": {
            "status": "resolved",
            "project_uuid": "project-fixture-webapp-004",
            "namespace": "tenant-a",
            "namespace_provenance": "~/.endorctl/config.yaml ENDOR_NAMESPACE",
            "repo_full_name": "example/webapp-python",
            "default_branch": "main",
            "traverse_attempted": True,
        },
        "risk_decision": {
            "status": "approved_with_validation_required",
            "summary": "Patch-level bump governed by the manifest range; install and test before PR.",
            "source_usage_summary": "Local source imports urllib3 directly; no graph manipulations beyond the manifest range.",
            "validation_requirements": [
                "python -m pip show urllib3",
                "python -m pytest",
            ],
        },
        "uia_evidence": [
            {
                "resource_type": "VersionUpgrade",
                "uuid": "version-upgrade-fixture-004",
                "upgrade_risk": "low",
                "cia_status": "no breaking changes",
                "findings_fixed": 1,
                "finding_instances_fixed": 1,
                "unique_advisories_fixed": 1,
                "fixed_finding_uuids": ["6a60c9445beb5fb713450071"],
                "findings_introduced": 0,
            }
        ],
        "dependency_graph_audit": {
            "package_manager": manager,
            "status": "clear",
            "manifest": manifests[0],
            "dependency_path": [
                "pypi://example-webapp@1.0.0",
                "pypi://urllib3@1.26.19",
            ],
            "manipulations": [
                {
                    "type": None,
                    "coordinate": "urllib3",
                    "classification": "version_control",
                    "semantic_effect": "native_version_control",
                    "mechanism": f"{manager}.manifest_range",
                    "replacement": None,
                    "evidence": [f"urllib3 range declared directly in {manifests[0]}"],
                }
            ],
            "validation_requirements": [],
        },
        "patch_plan": [
            {
                "file": manifests[0],
                "branch_name": "remediation/sca/urllib3-1.26.19",
            }
        ],
        "validation": [
            {
                "command": "python -m pip show urllib3",
                "status": "planned",
                "purpose": "Confirm urllib3 resolves to 1.26.19",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "base_branch": "main",
                "branch": "not_created",
                "proposed_branch": "remediation/sca/urllib3-1.26.19",
                "inventory": {
                    "status": "none_found",
                    "lookup_method": "source provider branch and change-request inventory",
                    "checked_at": "2026-08-18T12:00:00Z",
                    "fresh_recheck": False,
                    "key": {
                        "repository": "example/webapp-python",
                        "base_branch": "main",
                        "ecosystem": "pypi",
                        "normalized_package": "pypi://urllib3",
                        "manifest": manifests[0],
                        "current_version": "1.26.4",
                        "target_version": "1.26.19",
                        "finding_set": [],
                    },
                    "candidates": [],
                    "reconciliation": {
                        "status": "not_needed",
                        "reason": "No existing candidate found.",
                        "selected_target_version": "1.26.19",
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


def _python_manipulation(mechanism: str, classification: str, **overrides) -> dict:
    manipulation = {
        "type": None,
        "coordinate": "chardet-equivalent",
        "classification": classification,
        "semantic_effect": overrides.pop("semantic_effect", None),
        "mechanism": mechanism,
        "replacement": overrides.pop("replacement", None),
        "evidence": ["observed in the declaring manifest"],
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


def test_python_profiles_registered_with_registry_level_ecosystem():
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
    }

    for profile in _PYTHON_PROFILES:
        assert profile.type_driven is False
        assert profile.semantic_effect_required is True
        # Endor treats Python as one PyPI registry family: the
        # duplicate-inventory key is manager-agnostic while the audit's
        # package_manager stays manager-specific.
        assert profile.canonical_ecosystem == "pypi"


def test_python_lockfile_detection_is_manager_specific():
    cases = {
        "poetry.lock": "poetry",
        "Pipfile": "pipenv",
        "Pipfile.lock": "pipenv",
        "uv.lock": "uv",
        "uv.toml": "uv",
    }
    for manifest, expected in cases.items():
        detections = _detect(manifests=(manifest,))
        assert [d.profile.name for d in detections] == [expected], (
            f"{manifest} should identify exactly {expected}: "
            f"{[d.profile.name for d in detections]}"
        )


def test_pip_claims_no_strong_manifest_signals():
    # pip has no lockfile, and every pip-format file (requirements.txt,
    # requirements.in, constraints.txt) is legitimately produced or consumed
    # by Poetry exports and uv's pip interface. pip identity therefore comes
    # from the audit's declared manager over family-shared signals, never
    # from a strong manifest match of its own.
    for manifest in ("requirements.txt", "requirements.in", "constraints.txt"):
        detections = _detect(manifests=(manifest,))
        python_names = {
            d.profile.name for d in detections if d.profile.name in _PYTHON_MANAGERS
        }
        assert python_names == set(_PYTHON_MANAGERS), (
            f"{manifest} should be a family-shared signal: {python_names}"
        )
        assert all(
            not (set(d.signals) & {"ecosystem", "manifest"})
            for d in detections
            if d.profile.name in _PYTHON_MANAGERS
        ), f"{manifest} produced a strong manager-specific signal"


def test_shared_python_signals_do_not_single_out_a_manager():
    # pyproject.toml, the pypi ecosystem token, and pypi:// coordinates are
    # shared across the PyPI family — none may claim a single manager alone.
    for signals in (
        {"manifests": ("pyproject.toml",)},
        {"ecosystem_tokens": ("pypi",)},
        {"coordinates": ("pypi://urllib3@1.26.19",)},
    ):
        detections = _detect(**signals)
        python_names = {
            d.profile.name for d in detections if d.profile.name in _PYTHON_MANAGERS
        }
        assert len(python_names) > 1, f"shared signal {signals} singled out {python_names}"

    # A manager-specific lockfile resolves the shared signals.
    detections = _detect(
        ecosystem_tokens=("pypi",), manifests=("pyproject.toml", "poetry.lock")
    )
    assert [d.profile.name for d in detections] == ["poetry"]
    # The pypi registry token is the canonical inventory ecosystem for Poetry.
    assert detections[0].ecosystem_is_canonical is True


def test_poetry_export_coexistence_is_not_ambiguous():
    # `poetry export` routinely commits a requirements.txt next to
    # poetry.lock (Docker builds, CI). The exported file is a family-shared
    # signal, so the lockfile's strong Poetry identity must win instead of
    # the pair failing closed as conflicting managers.
    detections = _detect(
        manifests=("pyproject.toml", "poetry.lock", "requirements.txt")
    )
    assert [d.profile.name for d in detections] == ["poetry"]

    payload = _valid_python_payload("poetry")
    payload["selected_remediation"]["affected_manifests"] = [
        "pyproject.toml",
        "poetry.lock",
        "requirements.txt",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"poetry-export coexistence failed closed: {errors}"


def test_conflicting_python_lockfiles_are_ambiguous():
    detections = _detect(manifests=("poetry.lock", "uv.lock"))
    assert {d.profile.name for d in detections} == {"poetry", "uv"}

    payload = _valid_python_payload("poetry")
    payload["selected_remediation"]["affected_manifests"] = [
        "pyproject.toml",
        "poetry.lock",
        "uv.lock",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "conflicting poetry and uv lockfiles did not fail closed"


def test_python_family_narrows_by_declared_manager_without_lockfile():
    # A requirements-only repo carries only family-shared signals; the
    # declared audit manager narrows the family instead of failing closed.
    for manager in _PYTHON_MANAGERS:
        payload = _valid_python_payload(manager)
        payload["selected_remediation"]["manifests"] = ["requirements.txt"]
        payload["selected_remediation"]["affected_manifests"] = ["requirements.txt"]
        payload["dependency_graph_audit"]["manifest"] = "requirements.txt"
        payload["dependency_graph_audit"]["manipulations"][0]["evidence"] = [
            "urllib3 range declared directly in requirements.txt"
        ]
        payload["change_requests"][0]["inventory"]["key"]["manifest"] = (
            "requirements.txt"
        )
        payload["patch_plan"][0]["file"] = "requirements.txt"

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert errors == [], f"declared {manager} did not narrow the family: {errors}"


def test_python_package_manager_schema_enum_covers_python_managers():
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
        None,
    }


def test_poetry_selection_requires_dependency_graph_audit():
    payload = _valid_python_payload("poetry")
    payload.pop("dependency_graph_audit")

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "dependency_graph_audit: required for selected Poetry remediations" in errors
    ), "Poetry signals (pypi ecosystem + poetry.lock) did not engage the audit"


def test_python_native_manifest_range_is_accepted_per_manager():
    for manager in _PYTHON_MANAGERS:
        payload = _valid_python_payload(manager)

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert errors == [], f"{manager} native manifest range rejected: {errors}"


def test_python_manipulations_are_mechanism_driven():
    payload = _valid_python_payload("pip")
    payload["dependency_graph_audit"]["manipulations"][0]["type"] = "exclusion"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].type: must be null for pip manipulations" in error for error in errors
    )

    payload = _valid_python_payload("pip")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = None

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "].mechanism: required for pip manipulations" in error for error in errors
    )

    payload = _valid_python_payload("pip")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = "pip.magic"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    # Cross-manager mechanism smuggling fails closed in both directions.
    payload = _valid_python_payload("pip")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "npm.overrides"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)

    payload = _valid_python_payload("poetry")
    payload["dependency_graph_audit"]["manipulations"][0]["mechanism"] = (
        "pip.constraints_pin"
    )

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_python_overrides_require_mediation_evidence():
    for manager, mechanism, display in (
        ("pip", "pip.constraints_pin", "pip"),
        ("pip", "pip.direct_dependency_override", "pip"),
        ("poetry", "poetry.direct_dependency_override", "Poetry"),
        ("pipenv", "pipenv.direct_dependency_override", "Pipenv"),
        ("uv", "uv.override_dependencies", "uv"),
        ("uv", "uv.constraint_dependencies", "uv"),
    ):
        payload = _valid_python_payload(manager)
        payload["dependency_graph_audit"]["manipulations"] = [
            _python_manipulation(
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

    payload = _valid_python_payload("pip")
    payload["dependency_graph_audit"]["manipulations"] = [
        _python_manipulation(
            "pip.constraints_pin",
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
        "dependency_graph_audit.status: declared pip graph mediation requires validation_required"
        in errors
    )


def test_python_declared_mediation_valid_flow_is_accepted():
    payload = _valid_python_payload("pip")
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _python_manipulation(
            "pip.constraints_pin",
            "mediation_declared",
            semantic_effect="forced_version_mediation",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert errors == [], f"declared pip constraints mediation rejected: {errors}"


def test_python_unverified_override_blocks():
    payload = _valid_python_payload("uv")
    payload["dependency_graph_audit"]["manipulations"] = [
        _python_manipulation(
            "uv.override_dependencies",
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
        "dependency_graph_audit.status: unverified uv direct overrides require blocked"
        in errors
    )


def test_python_lockfile_edit_requires_lockfile_override_effect():
    for manager, mechanism in (
        ("poetry", "poetry.lockfile_edit"),
        ("pipenv", "pipenv.lockfile_edit"),
        ("uv", "uv.lockfile_edit"),
    ):
        payload = _valid_python_payload(manager)
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _python_manipulation(
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
            "semantic_effect: must be lockfile_override" in error for error in errors
        ), f"{mechanism} accepted a mediation-only semantic effect"

        payload["dependency_graph_audit"]["manipulations"][0]["semantic_effect"] = (
            "lockfile_override"
        )

        assert (
            validate_sca_gate_payload(payload, gate="selection-plan") == []
        ), f"{mechanism} with lockfile_override rejected"


def test_pip_has_no_lockfile_edit_mechanism():
    # pip has no lockfile, so a pip.lockfile_edit claim is not a real
    # construct and must fail the mechanism whitelist.
    payload = _valid_python_payload("pip")
    payload["dependency_graph_audit"]["status"] = "validation_required"
    payload["risk_decision"]["status"] = "approved_with_validation_required"
    payload["dependency_graph_audit"]["manipulations"] = [
        _python_manipulation(
            "pip.lockfile_edit",
            "mediation_declared",
            semantic_effect="lockfile_override",
        )
    ]
    payload["dependency_graph_audit"]["validation_requirements"] = [
        "resolved_graph",
        "runtime_linkage",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any("].mechanism: must be one of" in error for error in errors)


def test_python_source_specifier_requires_source_override_effect():
    for manager, mechanism in (
        ("pip", "pip.source_specifier"),
        ("poetry", "poetry.source_specifier"),
        ("pipenv", "pipenv.source_specifier"),
        ("uv", "uv.source_specifier"),
        ("uv", "uv.sources_redirect"),
    ):
        payload = _valid_python_payload(manager)
        payload["dependency_graph_audit"]["status"] = "validation_required"
        payload["risk_decision"]["status"] = "approved_with_validation_required"
        payload["dependency_graph_audit"]["manipulations"] = [
            _python_manipulation(
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


def test_python_has_no_removal_or_substitution_buckets():
    # No pip/Poetry/Pipenv/uv construct removes or aliases a resolved-graph
    # node the way a JVM exclusion or an npm alias redirect does: pip
    # famously has no exclusion mechanism, and a fork swap is a manifest
    # edit of the declaration itself, not an in-place substitution.
    for profile in _PYTHON_PROFILES:
        kinds = set(profile.mechanisms.values())
        assert "removal" not in kinds, f"{profile.name} claims a removal construct"
        assert (
            "substitution" not in kinds
        ), f"{profile.name} claims a substitution construct"

    # dependency_removal and dependency_substitution are therefore never
    # claimable through Python mechanisms.
    for effect in ("dependency_removal", "dependency_substitution"):
        payload = _valid_python_payload("pip")
        payload["dependency_graph_audit"]["status"] = "blocked"
        payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"
        payload["dependency_graph_audit"]["manipulations"] = [
            _python_manipulation(
                "pip.constraints_pin", "unverified", semantic_effect=effect
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]

        errors = validate_sca_gate_payload(payload, gate="selection-plan")

        assert any(
            "].semantic_effect: must be" in error for error in errors
        ), f"{effect} was claimable through a pip mechanism"


def test_python_inventory_ecosystem_must_be_registry_pypi():
    payload = _valid_python_payload("poetry")
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "poetry"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be pypi for Poetry remediations"
        in errors
    )

    payload = _valid_python_payload("pip")
    payload["change_requests"][0]["inventory"]["key"]["ecosystem"] = "python"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "change_requests[0].inventory.key.ecosystem: must be pypi for pip remediations"
        in errors
    )


def test_python_unavailable_audit_cannot_be_low_risk():
    payload = _valid_python_payload("pipenv")
    payload["risk_decision"]["status"] = "approved_low_risk"
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert (
        "risk_decision.status: unavailable Pipenv dependency graph audit cannot be approved_low_risk"
        in errors
    )


def test_unresolvable_declared_python_manager_fails_closed():
    # Inherited red-team rule: an audit that claims content must declare a
    # resolvable manager even when every detection signal is scrubbed.
    # Python near-misses (pip3, PIP, conda) must not skip validation.
    def scrubbed_payload(package_manager):
        payload = _valid_python_payload("pip")
        key = payload["change_requests"][0]["inventory"]["key"]
        key["ecosystem"] = "python-ish"
        key["manifest"] = "app/deps.list"
        key["normalized_package"] = "urllib3"
        payload["selected_remediation"]["manifests"] = ["app/deps.list"]
        payload["selected_remediation"]["affected_manifests"] = ["app/deps.list"]
        payload["patch_plan"][0]["file"] = "app/deps.list"
        payload["dependency_graph_audit"]["manifest"] = "app/deps.list"
        payload["dependency_graph_audit"]["package_manager"] = package_manager
        payload["dependency_graph_audit"]["manipulations"] = [
            _python_manipulation(
                "pip.constraints_pin",
                "unverified",
                semantic_effect="forced_version_mediation",
            )
        ]
        payload["dependency_graph_audit"]["validation_requirements"] = [
            "resolved_graph",
            "runtime_linkage",
        ]
        return payload

    for token in (None, "PIP", "pip3", "conda", "python", ["pip"]):
        errors = validate_sca_gate_payload(
            scrubbed_payload(token), gate="selection-plan"
        )

        assert any(
            "dependency_graph_audit.package_manager: must be one of" in error
            for error in errors
        ), f"unresolvable declared manager {token!r} skipped audit validation"

    # The honest unsupported-manager shape stays accepted: unavailable with
    # no manipulations and no supported-manager claim.
    payload = scrubbed_payload("conda")
    payload["dependency_graph_audit"]["status"] = "unavailable"
    payload["dependency_graph_audit"]["manifest"] = None
    payload["dependency_graph_audit"]["manipulations"] = []
    payload["dependency_graph_audit"]["validation_requirements"] = []
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_whitespace_padded_python_lockfiles_still_count_as_strong_signals():
    # Inherited red-team rule: padded lockfile names keep their strong
    # signal, so conflicting lockfiles cannot dodge the ambiguity gate.
    for padded in ("poetry.lock ", " poetry.lock", "poetry.lock\n"):
        detections = _detect(manifests=(padded,))
        assert [d.profile.name for d in detections] == ["poetry"], (
            f"padded manifest {padded!r} lost its strong poetry signal"
        )

    payload = _valid_python_payload("poetry")
    payload["selected_remediation"]["affected_manifests"] = [
        "pyproject.toml",
        "poetry.lock",
        "uv.lock ",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "whitespace-padded conflicting lockfile bypassed the ambiguity gate"


def test_format_char_disguised_lockfiles_still_count_as_strong_signals():
    # Red-team finding: zero-width/format characters and Windows-style
    # trailing dots survived basename normalization, so a disguised
    # conflicting lockfile lost its strong signal and dodged the ambiguity
    # fail-closed gate (same disguise class as the whitespace padding fixed
    # in the Node phase).
    for disguised in (
        "uv.lock​",
        "uv.lock﻿",
        "uv.lock⁠",
        "uv.lock.",
        "uv​.lock",
    ):
        detections = _detect(manifests=(disguised,))
        assert [d.profile.name for d in detections] == ["uv"], (
            f"disguised manifest {disguised!r} lost its strong uv signal"
        )

    payload = _valid_python_payload("poetry")
    payload["selected_remediation"]["affected_manifests"] = [
        "pyproject.toml",
        "poetry.lock",
        "uv.lock​",
    ]

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "ambiguous package-manager signals" in error for error in errors
    ), "format-char-disguised conflicting lockfile bypassed the ambiguity gate"


def test_unresolvable_manager_unavailable_audit_cannot_be_low_risk():
    # Red-team finding: the honest unsupported-manager pass-through
    # (unavailable + no manipulations + unresolvable declared manager)
    # skipped profile validation entirely, so the documented coupling
    # "unavailable audit cannot be approved_low_risk" never fired.
    payload = _valid_python_payload("pip")
    key = payload["change_requests"][0]["inventory"]["key"]
    key["ecosystem"] = "conda-forge"
    key["manifest"] = "environment.yml"
    key["normalized_package"] = "urllib3"
    payload["selected_remediation"]["manifests"] = ["environment.yml"]
    payload["selected_remediation"]["affected_manifests"] = ["environment.yml"]
    payload["patch_plan"][0]["file"] = "environment.yml"
    payload["dependency_graph_audit"] = {
        "package_manager": "conda",
        "status": "unavailable",
        "manifest": None,
        "dependency_path": [],
        "manipulations": [],
        "validation_requirements": [],
    }
    payload["risk_decision"]["status"] = "approved_low_risk"

    errors = validate_sca_gate_payload(payload, gate="selection-plan")

    assert any(
        "unavailable" in error and "approved_low_risk" in error for error in errors
    ), "unsupported-manager unavailable audit accompanied approved_low_risk"

    # The honest shape stays accepted with a fail-closed risk decision.
    payload["risk_decision"]["status"] = "blocked_needs_compatibility_analysis"

    assert validate_sca_gate_payload(payload, gate="selection-plan") == []


def test_python_self_declared_audit_is_validated_when_signals_are_scrubbed():
    payload = _valid_python_payload("uv")
    key = payload["change_requests"][0]["inventory"]["key"]
    key["ecosystem"] = "python-ish"
    key["manifest"] = "app/deps.list"
    key["normalized_package"] = "urllib3"
    payload["selected_remediation"]["manifests"] = ["app/deps.list"]
    payload["selected_remediation"]["affected_manifests"] = ["app/deps.list"]
    payload["dependency_graph_audit"]["manifest"] = "app/deps.list"
    payload["dependency_graph_audit"]["manipulations"] = [
        _python_manipulation(
            "uv.override_dependencies",
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
        "dependency_graph_audit.status: unverified uv direct overrides require blocked"
        in errors
    ), "scrubbing every detection signal skipped validation of a self-declared uv audit"


def test_manager_ecosystem_tokens_are_strong_python_signals():
    # A manager name used as the ecosystem token unambiguously identifies
    # that manager (unlike npm, no Python manager name doubles as the
    # canonical registry token) — but it is still non-canonical for the
    # duplicate-inventory key, which requires pypi.
    for token, expected in (
        ("pip", "pip"),
        ("poetry", "poetry"),
        ("pipenv", "pipenv"),
        ("uv", "uv"),
    ):
        detections = _detect(ecosystem_tokens=(token,))
        python_detections = [
            d for d in detections if d.profile.name in _PYTHON_MANAGERS
        ]
        assert [d.profile.name for d in python_detections] == [expected], (
            f"ecosystem token {token!r} did not identify {expected}"
        )
        assert python_detections[0].ecosystem_is_canonical is False

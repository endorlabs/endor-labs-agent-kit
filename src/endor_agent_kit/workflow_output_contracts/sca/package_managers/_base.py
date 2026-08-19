"""Shared dependency-graph audit engine parameterized by package-manager profiles.

The engine owns the semantic state machine: classification whitelists per
manipulation kind, status forcing, evidence coupling, risk-decision coupling,
and the normalized output caps. Profiles own manager-specific vocabulary only
(ecosystem aliases, manifest and coordinate shapes, manipulation type names).
Payload fields are untrusted model output, so every rule fails closed on
unrecognized tokens instead of skipping them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Mapping

from endor_agent_kit.workflow_output_contracts.sca._coerce import _list, _text

AUDIT_STATUSES = (
    "blocked",
    "clear",
    "unavailable",
    "validated",
    "validation_required",
)

CLASSIFICATIONS = (
    "mediation_declared",
    "mediation_verified",
    "not_needed_verified",
    "replacement_conflict_or_incomplete",
    "replacement_declared",
    "replacement_verified",
    "unverified",
    "version_control",
)

SEMANTIC_EFFECTS = (
    "asset_or_feature_suppression",
    "dependency_removal",
    "dependency_substitution",
    "forced_version_mediation",
    "lockfile_override",
    "native_version_control",
    "source_override",
)

UNSAFE_CLASSIFICATIONS = frozenset({"unverified", "replacement_conflict_or_incomplete"})
OVERRIDE_CLASSIFICATIONS = frozenset(
    {
        "mediation_declared",
        "mediation_verified",
        "unverified",
        "replacement_conflict_or_incomplete",
    }
)
REMOVAL_CLASSIFICATIONS = frozenset(
    {
        "unverified",
        "replacement_conflict_or_incomplete",
        "replacement_declared",
        "replacement_verified",
        "not_needed_verified",
    }
)
SUBSTITUTION_CLASSIFICATIONS = frozenset(
    {
        "unverified",
        "replacement_conflict_or_incomplete",
        "replacement_declared",
        "replacement_verified",
    }
)
GRAPH_RUNTIME_KINDS = frozenset({"resolved_graph", "runtime_linkage"})

COORDINATE_RE = re.compile(
    r"[A-Za-z0-9._-]+:[A-Za-z0-9._-]+(?::[A-Za-z0-9._+-]+)?"
)

MAX_MANIPULATIONS = 8
MAX_DEPENDENCY_PATH = 12
MAX_EVIDENCE_ITEMS = 3
MAX_VALIDATION_REQUIREMENTS = 2


@dataclass(frozen=True)
class PackageManagerAuditProfile:
    """One package manager's dependency-graph audit vocabulary.

    Type-driven profiles (Maven) classify manipulations through the shared
    `type` enum. Mechanism-driven profiles (Gradle onward) keep `type` null
    and carry the manager construct in the namespaced `mechanism` field, so
    the shared type enum never grows per manager. Both map constructs onto
    the same four semantic kinds: native, override, removal, substitution.
    """

    name: str
    display_name: str
    ecosystem_aliases: frozenset[str]
    manifest_basenames: frozenset[str]
    manifest_suffixes: tuple[str, ...]
    coordinate_prefixes: tuple[str, ...]
    native_types: frozenset[str]
    override_types: frozenset[str]
    removal_types: frozenset[str]
    type_driven: bool = True
    semantic_effect_required: bool = False
    mechanisms: Mapping[str, str] = field(default_factory=dict)
    # Registry-family vocabulary: some managers share one registry (npm/Yarn/
    # pnpm all install from the npm registry), so the duplicate-inventory
    # ecosystem token, some manifests, and coordinate shapes identify the
    # family, never one manager. Shared signals are weak: they yield to any
    # manager-specific ecosystem or manifest match.
    canonical_ecosystem: str = ""
    shared_ecosystem_aliases: frozenset[str] = frozenset()
    shared_manifest_basenames: frozenset[str] = frozenset()
    # Mechanisms whose semantic_effect differs from the kind default (e.g. a
    # hand-edited lockfile is an override construct with lockfile_override
    # semantics, not forced version mediation).
    mechanism_semantic_effects: Mapping[str, frozenset[str]] = field(
        default_factory=dict
    )
    replacement_pattern: re.Pattern[str] = COORDINATE_RE
    replacement_format: str = "group:artifact"

    def __post_init__(self) -> None:
        if not self.canonical_ecosystem:
            object.__setattr__(self, "canonical_ecosystem", self.name)

    @property
    def manipulation_types(self) -> frozenset[str]:
        return self.native_types | self.override_types | self.removal_types

    def mechanism_for_type(self, manipulation_type: str) -> str:
        return f"{self.name}.{manipulation_type}"

    def kind_of(self, manipulation_type: str, mechanism: str) -> str | None:
        if not isinstance(manipulation_type, str) or not isinstance(mechanism, str):
            return None
        if self.type_driven:
            if manipulation_type in self.native_types:
                return "native"
            if manipulation_type in self.override_types:
                return "override"
            if manipulation_type in self.removal_types:
                return "removal"
            return None
        return self.mechanisms.get(mechanism)

    def matches_ecosystem(self, token: str) -> bool:
        return _normalize_ecosystem(token) in self.ecosystem_aliases

    def matches_shared_ecosystem(self, token: str) -> bool:
        return _normalize_ecosystem(token) in self.shared_ecosystem_aliases

    def matches_manifest(self, manifest: str) -> bool:
        name = _manifest_basename(manifest)
        if name is None:
            return False
        return name in self.manifest_basenames or name.endswith(self.manifest_suffixes)

    def matches_shared_manifest(self, manifest: str) -> bool:
        name = _manifest_basename(manifest)
        if name is None:
            return False
        return name in self.shared_manifest_basenames

    def matches_coordinate(self, coordinate: str) -> bool:
        if not isinstance(coordinate, str):
            return False
        return coordinate.lower().startswith(self.coordinate_prefixes)


@dataclass(frozen=True)
class PackageManagerDetection:
    """Result of matching one profile against payload-level signals."""

    profile: PackageManagerAuditProfile
    ecosystem_token: str
    ecosystem_is_canonical: bool
    signals: tuple[str, ...]


def _manifest_basename(manifest: object) -> str | None:
    """Whitespace-stripped lowercase basename, or None for non-strings.

    Stripping is load-bearing: a padded lockfile name ('yarn.lock ') must
    still register as a strong manager signal, or conflicting lockfiles could
    dodge the ambiguity fail-closed gate.
    """

    if not isinstance(manifest, str):
        return None
    return PurePosixPath(manifest.strip().replace("\\", "/")).name.lower()


def _normalize_ecosystem(token: str) -> str:
    normalized = _text(token).lower()
    if normalized.startswith("ecosystem_"):
        normalized = normalized[len("ecosystem_") :]
    return "-".join(part for part in normalized.replace("_", " ").split() if part)


def detect_package_managers(
    profiles: tuple[PackageManagerAuditProfile, ...],
    *,
    ecosystem_tokens: tuple[str, ...],
    manifests: tuple[str, ...],
    coordinates: tuple[str, ...],
) -> list[PackageManagerDetection]:
    """Match profiles against every available signal, not just the ecosystem string."""

    primary_token = ecosystem_tokens[0] if ecosystem_tokens else ""
    detections: list[PackageManagerDetection] = []
    for profile in profiles:
        signals: list[str] = []
        if any(profile.matches_ecosystem(token) for token in ecosystem_tokens):
            signals.append("ecosystem")
        if any(profile.matches_manifest(manifest) for manifest in manifests):
            signals.append("manifest")
        if any(
            profile.matches_shared_ecosystem(token) for token in ecosystem_tokens
        ):
            signals.append("registry_ecosystem")
        if any(
            profile.matches_shared_manifest(manifest) for manifest in manifests
        ):
            signals.append("shared_manifest")
        if any(profile.matches_coordinate(coordinate) for coordinate in coordinates):
            signals.append("coordinate")
        if signals:
            detections.append(
                PackageManagerDetection(
                    profile=profile,
                    ecosystem_token=primary_token,
                    # Canonicality is exact: aliases and case/prefix variants are
                    # detection signals, but duplicate-inventory keys require the
                    # registry-level canonical token (the manager name outside
                    # registry families).
                    ecosystem_is_canonical=primary_token
                    == profile.canonical_ecosystem,
                    signals=tuple(signals),
                )
            )
    # Coordinate formats, registry-level ecosystem tokens, and registry-shared
    # manifests identify a family, not one manager (JVM packages are mvn://
    # for both Maven and Gradle; package.json is shared by npm/Yarn/pnpm), so
    # those matches yield to any profile matched by manager-specific ecosystem
    # or manifest evidence.
    strong = [
        detection
        for detection in detections
        if set(detection.signals) & {"ecosystem", "manifest"}
    ]
    if strong:
        return strong
    return detections


def validate_dependency_graph_audit(
    profile: PackageManagerAuditProfile,
    *,
    audit: dict[str, Any],
    selected_manifests: set[str],
    risk_status: str,
    successful_validation_kinds: set[str],
    errors: list[str],
) -> None:
    """Apply the shared graph-safety state machine to one audit object."""

    display = profile.display_name
    audit_status = _text(audit.get("status"))
    if _text(audit.get("package_manager")) != profile.name:
        errors.append(f"dependency_graph_audit.package_manager: must be {profile.name}")
    if audit_status not in AUDIT_STATUSES:
        errors.append(
            "dependency_graph_audit.status: must be one of " + ", ".join(AUDIT_STATUSES)
        )
    audit_manifest = _text(audit.get("manifest"))
    if (
        audit_status != "unavailable"
        and selected_manifests
        and audit_manifest not in selected_manifests
    ):
        errors.append(
            "dependency_graph_audit.manifest: must match a selected remediation manifest"
        )

    for field_name in ("dependency_path", "manipulations", "validation_requirements"):
        raw_value = audit.get(field_name)
        if raw_value is not None and not isinstance(raw_value, list):
            errors.append(f"dependency_graph_audit.{field_name}: must be an array")

    dependency_path = _list(audit.get("dependency_path"))
    if len(dependency_path) > MAX_DEPENDENCY_PATH:
        errors.append(
            "dependency_graph_audit.dependency_path: must contain at most "
            f"{MAX_DEPENDENCY_PATH} entries"
        )
    manipulations = _list(audit.get("manipulations"))
    if len(manipulations) > MAX_MANIPULATIONS:
        errors.append(
            "dependency_graph_audit.manipulations: must contain at most "
            f"{MAX_MANIPULATIONS} entries"
        )
    raw_requirements = _list(audit.get("validation_requirements"))
    audit_validation_requirements = {
        item for item in raw_requirements if isinstance(item, str)
    }
    if len(raw_requirements) > MAX_VALIDATION_REQUIREMENTS or not (
        audit_validation_requirements <= GRAPH_RUNTIME_KINDS
        and len(audit_validation_requirements) == len(raw_requirements)
    ):
        errors.append(
            "dependency_graph_audit.validation_requirements: must contain at most "
            f"{MAX_VALIDATION_REQUIREMENTS} entries drawn from resolved_graph and "
            "runtime_linkage"
        )

    removal_classifications: set[str] = set()
    override_classifications: set[str] = set()
    substitution_classifications: set[str] = set()
    # Entries beyond the cap already fail the payload via the cap error above;
    # bounding the walk keeps the error list itself bounded on huge payloads.
    for index, manipulation in enumerate(manipulations[:MAX_MANIPULATIONS]):
        prefix = f"dependency_graph_audit.manipulations[{index}]"
        if not isinstance(manipulation, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        manipulation_type = _text(manipulation.get("type"))
        classification = _text(manipulation.get("classification"))
        mechanism = _text(manipulation.get("mechanism"))
        if profile.type_driven:
            if manipulation_type not in profile.manipulation_types:
                errors.append(
                    f"{prefix}.type: must be one of "
                    + ", ".join(sorted(profile.manipulation_types))
                )
            if (
                manipulation.get("mechanism") is not None
                and manipulation_type in profile.manipulation_types
                and mechanism != profile.mechanism_for_type(manipulation_type)
            ):
                errors.append(
                    f"{prefix}.mechanism: must be "
                    f"{profile.mechanism_for_type(manipulation_type)} for {display} "
                    "manipulations"
                )
        else:
            if manipulation_type:
                errors.append(
                    f"{prefix}.type: must be null for {display} manipulations; the "
                    "mechanism field carries the construct"
                )
            if not mechanism:
                errors.append(
                    f"{prefix}.mechanism: required for {display} manipulations"
                )
            elif mechanism not in profile.mechanisms:
                errors.append(
                    f"{prefix}.mechanism: must be one of "
                    + ", ".join(sorted(profile.mechanisms))
                )
            if profile.semantic_effect_required and manipulation.get(
                "semantic_effect"
            ) is None:
                errors.append(
                    f"{prefix}.semantic_effect: required for {display} manipulations"
                )
        if classification not in CLASSIFICATIONS:
            errors.append(
                f"{prefix}.classification: must be one of " + ", ".join(CLASSIFICATIONS)
            )
        raw_evidence = manipulation.get("evidence")
        if raw_evidence is not None and not isinstance(raw_evidence, list):
            errors.append(f"{prefix}.evidence: must be an array")
        if len(_list(raw_evidence)) > MAX_EVIDENCE_ITEMS:
            errors.append(
                f"{prefix}.evidence: must contain at most {MAX_EVIDENCE_ITEMS} entries"
            )
        replacement = _text(manipulation.get("replacement"))
        if classification in {"replacement_declared", "replacement_verified"}:
            if not replacement:
                errors.append(f"{prefix}.replacement: required for {classification}")
            elif not profile.replacement_pattern.fullmatch(replacement):
                errors.append(
                    f"{prefix}.replacement: must be an exact "
                    f"{profile.replacement_format} coordinate"
                )

        kind = profile.kind_of(manipulation_type, mechanism)
        if kind == "native" and classification != "version_control":
            errors.append(
                f"{prefix}.classification: native {display} controls require "
                "version_control"
            )
        if kind == "override" and classification not in OVERRIDE_CLASSIFICATIONS:
            errors.append(
                f"{prefix}.classification: direct {display} overrides require "
                "mediation evidence"
            )
        if kind == "removal" and classification not in REMOVAL_CLASSIFICATIONS:
            errors.append(
                f"{prefix}.classification: {display} exclusions require unverified, "
                "replacement_declared, replacement_verified, not_needed_verified, or "
                "replacement_conflict_or_incomplete"
            )
        if kind == "substitution" and classification not in SUBSTITUTION_CLASSIFICATIONS:
            errors.append(
                f"{prefix}.classification: {display} substitutions require "
                "replacement evidence"
            )

        if manipulation.get("semantic_effect") is not None:
            semantic_effect = _text(manipulation.get("semantic_effect"))
            mechanism_effects = profile.mechanism_semantic_effects.get(mechanism)
            if semantic_effect not in SEMANTIC_EFFECTS:
                errors.append(
                    f"{prefix}.semantic_effect: must be one of "
                    + ", ".join(SEMANTIC_EFFECTS)
                )
            elif mechanism_effects is not None:
                if semantic_effect not in mechanism_effects:
                    construct = mechanism.split(".", 1)[-1] if mechanism else mechanism
                    errors.append(
                        f"{prefix}.semantic_effect: must be "
                        + " or ".join(sorted(mechanism_effects))
                        + f" for {display} {construct} manipulations"
                    )
            elif kind == "native" and semantic_effect != "native_version_control":
                errors.append(
                    f"{prefix}.semantic_effect: must be native_version_control for "
                    f"native {display} controls"
                )
            elif kind == "override" and semantic_effect != "forced_version_mediation":
                errors.append(
                    f"{prefix}.semantic_effect: must be forced_version_mediation for "
                    f"direct {display} overrides"
                )
            elif kind == "removal" and semantic_effect not in {
                "dependency_removal",
                "dependency_substitution",
            }:
                errors.append(
                    f"{prefix}.semantic_effect: must be dependency_removal or "
                    f"dependency_substitution for {display} exclusions"
                )
            elif kind == "substitution" and semantic_effect != "dependency_substitution":
                errors.append(
                    f"{prefix}.semantic_effect: must be dependency_substitution for "
                    f"{display} substitutions"
                )

        if kind == "removal":
            removal_classifications.add(classification)
        if kind == "override":
            override_classifications.add(classification)
        if kind == "substitution":
            substitution_classifications.add(classification)

    has_removal = bool(removal_classifications)
    has_override = bool(override_classifications)
    has_substitution = bool(substitution_classifications)
    unsafe_removals = removal_classifications & UNSAFE_CLASSIFICATIONS
    unsafe_overrides = override_classifications & UNSAFE_CLASSIFICATIONS
    unsafe_substitutions = substitution_classifications & UNSAFE_CLASSIFICATIONS

    if has_removal and not GRAPH_RUNTIME_KINDS <= audit_validation_requirements:
        errors.append(
            f"dependency_graph_audit.validation_requirements: {display} exclusions "
            "require resolved_graph and runtime_linkage"
        )
    if has_override and not GRAPH_RUNTIME_KINDS <= audit_validation_requirements:
        errors.append(
            f"dependency_graph_audit.validation_requirements: {display} graph "
            "manipulations require resolved_graph and runtime_linkage"
        )
    if has_substitution and not GRAPH_RUNTIME_KINDS <= audit_validation_requirements:
        errors.append(
            f"dependency_graph_audit.validation_requirements: {display} substitutions "
            "require resolved_graph and runtime_linkage"
        )
    if unsafe_substitutions and audit_status != "blocked":
        errors.append(
            f"dependency_graph_audit.status: unverified {display} substitutions "
            "require blocked"
        )
    if (
        "replacement_declared" in substitution_classifications
        and not unsafe_substitutions
        and audit_status != "validation_required"
    ):
        errors.append(
            f"dependency_graph_audit.status: declared {display} substitutions require "
            "validation_required"
        )
    if (
        "replacement_verified" in substitution_classifications
        and audit_status != "validated"
    ):
        errors.append(
            f"dependency_graph_audit.status: verified {display} substitutions require "
            "validated"
        )
    if unsafe_removals and audit_status != "blocked":
        errors.append(
            f"dependency_graph_audit.status: unverified {display} exclusions require "
            "blocked"
        )
    if unsafe_overrides and audit_status != "blocked":
        errors.append(
            f"dependency_graph_audit.status: unverified {display} direct overrides "
            "require blocked"
        )
    if (
        "replacement_declared" in removal_classifications
        and not unsafe_removals
        and audit_status != "validation_required"
    ):
        errors.append(
            f"dependency_graph_audit.status: declared {display} replacements require "
            "validation_required"
        )
    if (
        "mediation_declared" in override_classifications
        and not unsafe_overrides
        and audit_status != "validation_required"
    ):
        errors.append(
            f"dependency_graph_audit.status: declared {display} graph mediation "
            "requires validation_required"
        )
    if "mediation_verified" in override_classifications and audit_status != "validated":
        errors.append(
            f"dependency_graph_audit.status: verified {display} graph mediation "
            "requires validated"
        )
    if "replacement_verified" in removal_classifications and audit_status != "validated":
        errors.append(
            f"dependency_graph_audit.status: verified {display} replacements require "
            "validated"
        )
    if "not_needed_verified" in removal_classifications and audit_status != "validated":
        errors.append(
            f"dependency_graph_audit.status: verified not-needed {display} exclusions "
            "require validated"
        )

    if audit_status == "blocked" and risk_status.startswith("approved"):
        errors.append(
            f"risk_decision.status: blocked {display} dependency graph audit cannot "
            "accompany an approved decision"
        )
    if audit_status == "validation_required" and risk_status == "approved_low_risk":
        errors.append(
            f"risk_decision.status: {display} graph manipulation awaiting validation "
            "cannot be approved_low_risk"
        )
    if audit_status == "unavailable" and risk_status == "approved_low_risk":
        errors.append(
            f"risk_decision.status: unavailable {display} dependency graph audit "
            "cannot be approved_low_risk"
        )
    if (
        audit_status == "validated"
        and has_removal
        and not GRAPH_RUNTIME_KINDS <= successful_validation_kinds
    ):
        errors.append(
            f"dependency_graph_audit: validated {display} exclusions require passed "
            "resolved_graph and runtime_linkage validation"
        )
    if (
        audit_status == "validated"
        and has_override
        and not GRAPH_RUNTIME_KINDS <= successful_validation_kinds
    ):
        errors.append(
            f"dependency_graph_audit: validated {display} direct overrides require "
            "passed resolved_graph and runtime_linkage validation"
        )
    if (
        audit_status == "validated"
        and has_substitution
        and not GRAPH_RUNTIME_KINDS <= successful_validation_kinds
    ):
        errors.append(
            f"dependency_graph_audit: validated {display} substitutions require "
            "passed resolved_graph and runtime_linkage validation"
        )

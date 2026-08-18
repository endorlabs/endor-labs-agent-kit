"""Gradle dependency-graph audit profile.

Gradle manipulations are mechanism-driven: `type` stays null (the shared type
enum never grows per manager) and the namespaced `mechanism` token carries the
native construct, with `semantic_effect` required. Plain JVM Gradle only;
Android variant-aware evidence is out of scope for this profile version.
"""

from __future__ import annotations

from types import MappingProxyType

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

GRADLE_PROFILE = PackageManagerAuditProfile(
    name="gradle",
    display_name="Gradle",
    ecosystem_aliases=frozenset({"gradle", "gradle-kotlin", "gradlew"}),
    manifest_basenames=frozenset(
        {
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
            "libs.versions.toml",
            "gradle.lockfile",
        }
    ),
    manifest_suffixes=(".gradle", ".gradle.kts", ".versions.toml", ".lockfile"),
    # JVM coordinates are registry-level (mvn://) and shared with Maven, so
    # Gradle claims no coordinate signal of its own.
    coordinate_prefixes=(),
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "gradle.version_catalog": "native",
            "gradle.constraint": "native",
            "gradle.platform": "native",
            "gradle.enforced_platform": "override",
            "gradle.resolution_strategy_force": "override",
            "gradle.direct_dependency_override": "override",
            "gradle.rich_version_rule": "override",
            "gradle.exclusion": "removal",
            "gradle.dependency_substitution": "substitution",
            "gradle.component_metadata_rule": "substitution",
        }
    ),
)

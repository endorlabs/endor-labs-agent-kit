"""Maven dependency-graph audit profile."""

from __future__ import annotations

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

MAVEN_PROFILE = PackageManagerAuditProfile(
    name="maven",
    display_name="Maven",
    ecosystem_aliases=frozenset(
        {
            "maven",
            "mvn",
            "apache-maven",
            "maven-central",
            "maven2",
            "maven3",
            "java-maven",
        }
    ),
    manifest_basenames=frozenset({"pom.xml"}),
    manifest_suffixes=(".pom",),
    coordinate_prefixes=("mvn://",),
    native_types=frozenset({"version_property", "dependency_management", "bom"}),
    override_types=frozenset({"direct_dependency_override"}),
    removal_types=frozenset({"exclusion"}),
)

"""Package-manager dependency-graph audit profiles and detection registry."""

from __future__ import annotations

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    AUDIT_STATUSES,
    CLASSIFICATIONS,
    GRAPH_RUNTIME_KINDS,
    SEMANTIC_EFFECTS,
    PackageManagerAuditProfile,
    PackageManagerDetection,
    detect_package_managers,
    validate_dependency_graph_audit,
)
from endor_agent_kit.workflow_output_contracts.sca.package_managers.gradle import (
    GRADLE_PROFILE,
)
from endor_agent_kit.workflow_output_contracts.sca.package_managers.maven import (
    MAVEN_PROFILE,
)

SUPPORTED_PROFILES: tuple[PackageManagerAuditProfile, ...] = (
    MAVEN_PROFILE,
    GRADLE_PROFILE,
)

__all__ = [
    "AUDIT_STATUSES",
    "CLASSIFICATIONS",
    "GRADLE_PROFILE",
    "GRAPH_RUNTIME_KINDS",
    "MAVEN_PROFILE",
    "SEMANTIC_EFFECTS",
    "SUPPORTED_PROFILES",
    "PackageManagerAuditProfile",
    "PackageManagerDetection",
    "detect_package_managers",
    "validate_dependency_graph_audit",
]

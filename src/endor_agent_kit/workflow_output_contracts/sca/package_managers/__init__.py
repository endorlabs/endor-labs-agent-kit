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
from endor_agent_kit.workflow_output_contracts.sca.package_managers.node import (
    NPM_PROFILE,
    PNPM_PROFILE,
    YARN_PROFILE,
)

SUPPORTED_PROFILES: tuple[PackageManagerAuditProfile, ...] = (
    MAVEN_PROFILE,
    GRADLE_PROFILE,
    NPM_PROFILE,
    YARN_PROFILE,
    PNPM_PROFILE,
)

__all__ = [
    "AUDIT_STATUSES",
    "CLASSIFICATIONS",
    "GRADLE_PROFILE",
    "GRAPH_RUNTIME_KINDS",
    "MAVEN_PROFILE",
    "NPM_PROFILE",
    "PNPM_PROFILE",
    "SEMANTIC_EFFECTS",
    "SUPPORTED_PROFILES",
    "YARN_PROFILE",
    "PackageManagerAuditProfile",
    "PackageManagerDetection",
    "detect_package_managers",
    "validate_dependency_graph_audit",
]

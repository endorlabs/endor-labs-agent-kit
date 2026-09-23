"""Package-manager dependency-graph audit profiles and detection registry."""

from __future__ import annotations

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    AUDIT_STATUSES,
    CLASSIFICATIONS,
    GRAPH_RUNTIME_KINDS,
    MAX_DEPENDENCY_PATH,
    MAX_EVIDENCE_ITEMS,
    MAX_MANIPULATIONS,
    MAX_VALIDATION_REQUIREMENTS,
    SEMANTIC_EFFECTS,
    PackageManagerAuditProfile,
    PackageManagerDetection,
    _fold_disguises,
    _normalize_version_token,
    detect_package_managers,
    validate_dependency_graph_audit,
)

# Public aliases: consumers outside this package normalize model-controlled
# tokens with the same disguise folding and version normalization the audit
# engine applies internally, so the seam is part of the package surface.
fold_disguises = _fold_disguises
normalize_version_token = _normalize_version_token
from endor_agent_kit.workflow_output_contracts.sca.package_managers.bundler import (
    BUNDLER_PROFILE,
)
from endor_agent_kit.workflow_output_contracts.sca.package_managers.cargo import (
    CARGO_PROFILE,
)
from endor_agent_kit.workflow_output_contracts.sca.package_managers.go import (
    GO_PROFILE,
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
from endor_agent_kit.workflow_output_contracts.sca.package_managers.nuget import (
    NUGET_PROFILE,
)
from endor_agent_kit.workflow_output_contracts.sca.package_managers.python import (
    PIP_PROFILE,
    PIPENV_PROFILE,
    POETRY_PROFILE,
    UV_PROFILE,
)

SUPPORTED_PROFILES: tuple[PackageManagerAuditProfile, ...] = (
    MAVEN_PROFILE,
    GRADLE_PROFILE,
    NPM_PROFILE,
    YARN_PROFILE,
    PNPM_PROFILE,
    PIP_PROFILE,
    POETRY_PROFILE,
    PIPENV_PROFILE,
    UV_PROFILE,
    GO_PROFILE,
    NUGET_PROFILE,
    BUNDLER_PROFILE,
    CARGO_PROFILE,
)

__all__ = [
    "AUDIT_STATUSES",
    "BUNDLER_PROFILE",
    "CARGO_PROFILE",
    "CLASSIFICATIONS",
    "GO_PROFILE",
    "GRADLE_PROFILE",
    "GRAPH_RUNTIME_KINDS",
    "MAVEN_PROFILE",
    "MAX_DEPENDENCY_PATH",
    "MAX_EVIDENCE_ITEMS",
    "MAX_MANIPULATIONS",
    "MAX_VALIDATION_REQUIREMENTS",
    "NPM_PROFILE",
    "NUGET_PROFILE",
    "PIP_PROFILE",
    "PIPENV_PROFILE",
    "PNPM_PROFILE",
    "POETRY_PROFILE",
    "SEMANTIC_EFFECTS",
    "SUPPORTED_PROFILES",
    "UV_PROFILE",
    "YARN_PROFILE",
    "PackageManagerAuditProfile",
    "PackageManagerDetection",
    "detect_package_managers",
    "fold_disguises",
    "normalize_version_token",
    "validate_dependency_graph_audit",
]

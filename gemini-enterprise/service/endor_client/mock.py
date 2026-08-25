"""Deterministic Endor SCA client for local development and tests.

Build-order step 2 (§7, §12) requires a well-formed task result from mocked
findings -- no real auth, no real Endor calls. This client returns a fixed,
deterministic dataset (2 P0 + 5 P1) for any resolved target and echoes the
resolved namespace, so the A2A round-trip can be exercised end-to-end locally.

Special repo tokens let tests drive the non-happy paths without real Endor:

* ``acme/needs-auth``            -> raises AuthenticationError
* ``acme/forbidden-namespace``  -> raises NamespaceNotAuthorizedError
* ``acme/empty``                -> resolves but returns zero findings
* ``acme/partial``              -> returns findings plus a data_gap
"""

from __future__ import annotations

from ..a2a.errors import AuthenticationError, NamespaceNotAuthorizedError
from ..a2a.models import (
    AnalysisRequest,
    BreakingChangeRisk,
    RecommendedAction,
    ScaFinding,
    Severity,
)
from .base import EndorSCAClient, EndorSCAResult

_MOCK_FINDINGS: list[ScaFinding] = [
    ScaFinding(
        package="log4j-core",
        current_version="2.14.1",
        vulnerability_ids=["CVE-2021-44228", "CVE-2021-45046"],
        severity=Severity.P0,
        recommended_action=RecommendedAction.UPGRADE,
        target_version="2.17.1",
        breaking_change_risk=BreakingChangeRisk.LOW,
        patch_available=False,
    ),
    ScaFinding(
        package="jackson-databind",
        current_version="2.9.8",
        vulnerability_ids=["CVE-2020-36518"],
        severity=Severity.P0,
        recommended_action=RecommendedAction.UPGRADE,
        target_version="2.12.7.1",
        breaking_change_risk=BreakingChangeRisk.MEDIUM,
        patch_available=True,
    ),
    ScaFinding(
        package="commons-text",
        current_version="1.9",
        vulnerability_ids=["CVE-2022-42889"],
        severity=Severity.P1,
        recommended_action=RecommendedAction.UPGRADE,
        target_version="1.10.0",
        breaking_change_risk=BreakingChangeRisk.LOW,
        patch_available=False,
    ),
    ScaFinding(
        package="snakeyaml",
        current_version="1.30",
        vulnerability_ids=["CVE-2022-1471"],
        severity=Severity.P1,
        recommended_action=RecommendedAction.UPGRADE,
        target_version="2.0",
        breaking_change_risk=BreakingChangeRisk.HIGH,
        patch_available=False,
    ),
    ScaFinding(
        package="spring-web",
        current_version="5.3.18",
        vulnerability_ids=["CVE-2024-22243"],
        severity=Severity.P1,
        recommended_action=RecommendedAction.UPGRADE,
        target_version="5.3.32",
        breaking_change_risk=BreakingChangeRisk.LOW,
        patch_available=False,
    ),
    ScaFinding(
        package="guava",
        current_version="30.0-jre",
        vulnerability_ids=["CVE-2023-2976"],
        severity=Severity.P1,
        recommended_action=RecommendedAction.UPGRADE,
        target_version="32.0.0-jre",
        breaking_change_risk=BreakingChangeRisk.MEDIUM,
        patch_available=False,
    ),
    ScaFinding(
        package="netty-codec-http",
        current_version="4.1.68.Final",
        vulnerability_ids=["CVE-2022-24823"],
        severity=Severity.P1,
        recommended_action=RecommendedAction.PATCH,
        target_version="4.1.77.Final",
        breaking_change_risk=BreakingChangeRisk.LOW,
        patch_available=True,
    ),
]


class MockEndorSCAClient(EndorSCAClient):
    """Return deterministic SCA findings without touching Endor."""

    def _resolve_namespace(self, request: AnalysisRequest) -> str:
        if request.namespace:
            return request.namespace
        if request.repo_full_name:
            return request.repo_full_name
        if request.project_id:
            return f"project:{request.project_id}"
        # The parser guarantees at least one of the above, but stay defensive.
        return "unknown"

    def get_sca_analysis(self, request: AnalysisRequest) -> EndorSCAResult:
        target = (request.repo_full_name or "").lower()

        if target == "acme/needs-auth":
            raise AuthenticationError(
                "Endor authentication is unavailable for this request."
            )
        if target == "acme/forbidden-namespace":
            raise NamespaceNotAuthorizedError(
                "The authenticated caller is not authorized for the requested "
                "Endor namespace."
            )

        namespace = self._resolve_namespace(request)

        if target == "acme/empty":
            return EndorSCAResult(namespace=namespace, findings=[], data_gaps=[])

        wanted = set(request.severity_filter) or {Severity.P0, Severity.P1}
        findings = [f for f in _MOCK_FINDINGS if f.severity in wanted]

        data_gaps: list[str] = []
        if target == "acme/partial":
            data_gaps.append(
                "version_upgrade_uia_unavailable: mocked partial-evidence path"
            )

        return EndorSCAResult(
            namespace=namespace,
            findings=findings,
            data_gaps=data_gaps,
        )

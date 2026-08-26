"""Direct Endor REST API client (build-order step 3).

Talks to the namespace-scoped Endor REST API confirmed against a live tenant:

* ``GET /v1/namespaces/{ns}/projects``          -- resolve repo -> project.
* ``GET /v1/namespaces/{ns}/findings``          -- SCA vulnerability findings.
* ``GET /v1/namespaces/{ns}/version-upgrades``  -- upgrade/UIA evidence (v1: not
  yet correlated per-finding; reserved for remediation ranking).

Authentication is an api-key -> bearer-token exchange handled by
:class:`~service.endor_client.auth.TokenProvider`. This client implements the
same :class:`~service.endor_client.base.EndorSCAClient` interface as the mock,
so nothing upstream changes when it is selected.

v1 is read-only: it only issues GET list calls; it never mutates Endor or
source state.
"""

from __future__ import annotations

from typing import Any, Iterable
from urllib.parse import quote

import httpx

from ..a2a.errors import AuthenticationError, NamespaceNotAuthorizedError
from ..a2a.models import (
    AnalysisRequest,
    BreakingChangeRisk,
    RecommendedAction,
    ScaFinding,
    Severity,
)
from ..a2a.validation import (
    is_valid_project_uuid,
    validate_namespace,
    validate_project_id,
    validate_repo_full_name,
)
from .auth import TokenProvider
from .base import EndorSCAClient, EndorSCAResult

# Endor severity level -> our P0/P1 bucket. Documented and adjustable: v1 treats
# critical/high as P0 and medium/low as P1.
_LEVEL_TO_SEVERITY: dict[str, Severity] = {
    "FINDING_LEVEL_CRITICAL": Severity.P0,
    "FINDING_LEVEL_HIGH": Severity.P0,
    "FINDING_LEVEL_MEDIUM": Severity.P1,
    "FINDING_LEVEL_LOW": Severity.P1,
}
_SEVERITY_TO_LEVELS: dict[Severity, list[str]] = {
    Severity.P0: ["FINDING_LEVEL_CRITICAL", "FINDING_LEVEL_HIGH"],
    Severity.P1: ["FINDING_LEVEL_MEDIUM", "FINDING_LEVEL_LOW"],
}

_VULN_CATEGORY = "spec.finding_categories contains [FINDING_CATEGORY_VULNERABILITY]"

_FINDING_MASK = ",".join(
    [
        "uuid",
        "spec.level",
        "spec.target_dependency_package_name",
        "spec.finding_tags",
        "spec.proposed_version",
        "spec.fixing_patch",
        "spec.finding_metadata.vulnerability.meta.name",
        "spec.finding_metadata.vulnerability.spec.aliases",
    ]
)
_PROJECT_MASK = "uuid,meta.name,spec.git.full_name"

_PAGE_SIZE = 100
_MAX_FINDINGS = 500  # bound the read for a single analysis task


def _parse_package(purl: str | None) -> tuple[str, str]:
    """Split ``mvn://org.assertj:assertj-core@3.24.2`` -> (name, version)."""

    if not purl:
        return "", ""
    body = purl.split("://", 1)[-1]
    name, sep, version = body.rpartition("@")
    if not sep:  # no version present
        return version, ""
    return name, version


def _order_aliases(aliases: Iterable[str] | None, primary: str | None) -> list[str]:
    """Return advisory ids with CVEs first, de-duplicated, primary included."""

    seen: list[str] = []
    for value in list(aliases or []) + ([primary] if primary else []):
        if value and value not in seen:
            seen.append(value)
    seen.sort(key=lambda v: (0 if v.upper().startswith("CVE-") else 1, v))
    return seen


class RestEndorSCAClient(EndorSCAClient):
    def __init__(
        self,
        *,
        token_provider: TokenProvider,
        default_namespace: str | None = None,
        http_client: httpx.Client | None = None,
        base_url: str | None = None,
    ) -> None:
        self._tokens = token_provider
        self._default_namespace = default_namespace
        self._client = http_client or httpx.Client(
            base_url=base_url or token_provider._credentials.base_url,
            timeout=60.0,
        )

    # -- HTTP helpers ---------------------------------------------------------

    def _get_list(
        self, namespace: str, resource: str, *, filter: str, mask: str,
        page_size: int = _PAGE_SIZE, page_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "list_parameters.filter": filter,
            "list_parameters.mask": mask,
            "list_parameters.page_size": page_size,
        }
        if page_id:
            params["list_parameters.page_id"] = page_id
        # Defense in depth: validate + percent-encode the only dynamic path
        # segment so a namespace can never restructure the URL.
        validate_namespace(namespace)
        response = self._client.get(
            f"/v1/namespaces/{quote(namespace, safe='')}/{resource}",
            params=params,
            headers=self._tokens.auth_header(),
        )
        if response.status_code in (401, 403):
            # 401: token/credential problem. 403: authenticated but not entitled
            # to this namespace.
            if response.status_code == 401:
                raise AuthenticationError("Endor authentication failed or expired.")
            raise NamespaceNotAuthorizedError(
                f"Not authorized for Endor namespace {namespace!r}."
            )
        response.raise_for_status()
        return response.json()

    def _iter_objects(
        self, namespace: str, resource: str, *, filter: str, mask: str,
        cap: int,
    ) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []
        page_id: str | None = None
        while len(objects) < cap:
            payload = self._get_list(
                namespace, resource, filter=filter, mask=mask, page_id=page_id
            )
            listing = payload.get("list") or {}
            page = listing.get("objects") or []
            objects.extend(page)
            page_id = (listing.get("response") or {}).get("next_page_id") or listing.get(
                "next_page_id"
            )
            if not page or not page_id:
                break
        return objects[:cap]

    # -- Resolution + mapping -------------------------------------------------

    def _resolve_project_uuid(
        self, namespace: str, request: AnalysisRequest
    ) -> tuple[str | None, list[str]]:
        if request.project_id:
            return validate_project_id(request.project_id), []
        selector = request.repo_full_name
        if not selector:
            return None, ["no_repo_or_project_selector"]
        # Validated before it enters the filter literal (defense in depth).
        validate_repo_full_name(selector)
        filt = f'spec.git.full_name=="{selector}"'
        payload = self._get_list(
            namespace, "projects", filter=filt, mask=_PROJECT_MASK, page_size=2
        )
        objects = (payload.get("list") or {}).get("objects") or []
        if not objects:
            return None, [f"project_not_found: {selector}"]
        return objects[0].get("uuid"), []

    def _severity_filter(self, request: AnalysisRequest) -> str:
        wanted = request.severity_filter or [Severity.P0, Severity.P1]
        levels: list[str] = []
        for severity in wanted:
            levels.extend(_SEVERITY_TO_LEVELS.get(severity, []))
        if not levels:
            return ""
        return "spec.level in [" + ",".join(levels) + "]"

    def _to_finding(self, obj: dict[str, Any]) -> ScaFinding | None:
        spec = obj.get("spec") or {}
        level = spec.get("level")
        severity = _LEVEL_TO_SEVERITY.get(level)
        if severity is None:
            return None  # INFO/unknown levels are not P0/P1

        package, version = _parse_package(spec.get("target_dependency_package_name"))
        vuln = ((spec.get("finding_metadata") or {}).get("vulnerability") or {})
        primary = (vuln.get("meta") or {}).get("name")
        aliases = (vuln.get("spec") or {}).get("aliases")
        vuln_ids = _order_aliases(aliases, primary)

        tags = spec.get("finding_tags") or []
        proposed = spec.get("proposed_version") or None
        patch_available = bool(spec.get("fixing_patch"))
        has_upgrade = bool(proposed) or "FINDING_TAGS_FIX_AVAILABLE" in tags

        if has_upgrade:
            action = RecommendedAction.UPGRADE
        elif patch_available:
            action = RecommendedAction.PATCH
        else:
            action = RecommendedAction.NO_FIX_AVAILABLE

        return ScaFinding(
            package=package,
            current_version=version,
            vulnerability_ids=vuln_ids,
            severity=severity,
            recommended_action=action,
            target_version=proposed,
            # Per-finding breaking-change risk needs version-upgrade/UIA
            # correlation, which v1 does not do yet; report unknown honestly.
            breaking_change_risk=BreakingChangeRisk.UNKNOWN,
            patch_available=patch_available,
        )

    # -- Interface ------------------------------------------------------------

    def get_sca_analysis(self, request: AnalysisRequest) -> EndorSCAResult:
        namespace = request.namespace or self._default_namespace
        if not namespace:
            return EndorSCAResult(
                namespace="unknown", findings=[], data_gaps=["no_namespace_resolved"]
            )

        validate_namespace(namespace)
        project_uuid, gaps = self._resolve_project_uuid(namespace, request)
        if not project_uuid:
            return EndorSCAResult(namespace=namespace, findings=[], data_gaps=gaps)
        # An Endor-returned project uuid must be a well-formed UUID before it is
        # interpolated into the findings filter.
        if not is_valid_project_uuid(project_uuid):
            return EndorSCAResult(
                namespace=namespace, findings=[], data_gaps=["invalid_project_uuid"]
            )

        filt = f'spec.project_uuid=="{project_uuid}" and {_VULN_CATEGORY}'
        severity_clause = self._severity_filter(request)
        if severity_clause:
            filt = f"{filt} and {severity_clause}"

        raw = self._iter_objects(
            namespace, "findings", filter=filt, mask=_FINDING_MASK, cap=_MAX_FINDINGS
        )

        findings: list[ScaFinding] = []
        for obj in raw:
            mapped = self._to_finding(obj)
            if mapped is not None:
                findings.append(mapped)

        data_gaps = list(gaps)
        if len(raw) >= _MAX_FINDINGS:
            data_gaps.append(
                f"findings_truncated_at_{_MAX_FINDINGS}: more findings exist than "
                "were analyzed in this task"
            )

        # Rank most severe first for a stable, useful ordering.
        findings.sort(key=lambda f: 0 if f.severity is Severity.P0 else 1)

        return EndorSCAResult(
            namespace=namespace, findings=findings, data_gaps=data_gaps
        )

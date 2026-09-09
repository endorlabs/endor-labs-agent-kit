"""The three OSS-intelligence tools, backed by Endor's public ``oss`` namespace.

Confirmed against the live API:

* resolve a purl -> package-version uuid: ``package-versions`` filtered by
  ``meta.name=="<purl>"``;
* dependency vulnerabilities: ``findings`` filtered by ``spec.target_uuid``;
* package risk: ``metrics`` filtered by ``meta.parent_uuid`` (scores live in
  ``spec.metric_values``);
* vulnerability details: ``vulnerabilities`` filtered by ``spec.aliases``.

Read-only, and always the shared ``oss`` namespace — never a customer tenant.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from ..a2a.errors import AuthenticationError
from ..endor_client.token_source import TokenSource
from .models import (
    DependencyVulnerabilities,
    DependencyVulnerability,
    PackageRisk,
    VulnerabilityDetail,
)
from .refs import normalize_advisory_id, validate_purl

OSS_NAMESPACE = "oss"
_LEVEL = "FINDING_LEVEL_"


class OssIntelClient(ABC):
    @abstractmethod
    def vulnerability_details(self, advisory_id: str) -> VulnerabilityDetail | None: ...

    @abstractmethod
    def package_risk(self, purl: str) -> PackageRisk: ...

    @abstractmethod
    def dependency_vulnerabilities(self, purl: str) -> DependencyVulnerabilities: ...


def _flatten_numbers(obj: Any, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.update(_flatten_numbers(value, f"{prefix}{key}."))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[prefix.rstrip(".")] = float(obj)
    return out


class OssRestClient(OssIntelClient):
    def __init__(
        self,
        token_provider: TokenSource,
        *,
        http_client: httpx.Client | None = None,
        base_url: str | None = None,
    ) -> None:
        self._tokens = token_provider
        self._client = http_client or httpx.Client(
            base_url=base_url or token_provider.base_url, timeout=45.0
        )

    def _list(self, resource: str, *, filter: str, mask: str, page_size: int = 5) -> list[dict[str, Any]]:
        response = self._client.get(
            f"/v1/namespaces/{OSS_NAMESPACE}/{resource}",
            params={
                "list_parameters.filter": filter,
                "list_parameters.mask": mask,
                "list_parameters.page_size": page_size,
            },
            headers=self._tokens.auth_header(),
        )
        if response.status_code in (401, 403):
            # OSS uses the service credential, so this is a config problem, not
            # a per-user authorization issue.
            raise AuthenticationError("Endor rejected the OSS service credential.")
        response.raise_for_status()
        return (response.json().get("list") or {}).get("objects") or []

    # -- tools ----------------------------------------------------------------

    def vulnerability_details(self, advisory_id: str) -> VulnerabilityDetail | None:
        vid = normalize_advisory_id(advisory_id)
        objects = self._list(
            "vulnerabilities",
            filter=f'spec.aliases contains ["{vid}"]',
            mask="uuid,meta.name,spec.summary,spec.aliases,spec.cvss_v3_severity,spec.epss_score,spec.references",
        )
        if not objects:
            return VulnerabilityDetail(id=vid, found=False)
        spec = objects[0].get("spec") or {}
        cvss = spec.get("cvss_v3_severity") or {}
        aliases = list(spec.get("aliases") or [])
        primary = next((a for a in aliases if a.upper().startswith("CVE-")), None)
        return VulnerabilityDetail(
            id=primary or (objects[0].get("meta") or {}).get("name") or vid,
            aliases=aliases,
            summary=spec.get("summary"),
            severity=_clean_level(cvss.get("level") if isinstance(cvss, dict) else None),
            cvss_score=(cvss.get("score") if isinstance(cvss, dict) else None),
            epss_score=_first_number(spec.get("epss_score")),
            references=_reference_urls(spec.get("references")),
        )

    def _resolve_package(self, purl: str) -> tuple[str | None, str | None]:
        objects = self._list(
            "package-versions",
            filter=f'meta.name=="{purl}"',
            mask="uuid,meta.name,spec.package_name,spec.ecosystem",
            page_size=1,
        )
        if not objects:
            return None, None
        return objects[0].get("uuid"), (objects[0].get("spec") or {}).get("package_name")

    def package_risk(self, purl: str) -> PackageRisk:
        p = validate_purl(purl)
        pv_uuid, package_name = self._resolve_package(p)
        if not pv_uuid:
            return PackageRisk(purl=p, found=False)
        metrics = self._list(
            "metrics",
            filter=f'meta.parent_uuid=="{pv_uuid}"',
            mask="uuid,meta.name,spec.metric_values",
            page_size=20,
        )
        scores: dict[str, float] = {}
        for metric in metrics:
            name = (metric.get("meta") or {}).get("name") or "metric"
            values = (metric.get("spec") or {}).get("metric_values")
            for key, value in _flatten_numbers(values).items():
                scores[f"{name}.{key}" if key else name] = value
        return PackageRisk(purl=p, package_name=package_name, scores=scores)

    def dependency_vulnerabilities(self, purl: str) -> DependencyVulnerabilities:
        p = validate_purl(purl)
        pv_uuid, package_name = self._resolve_package(p)
        if not pv_uuid:
            return DependencyVulnerabilities(purl=p, found=False)
        findings = self._list(
            "findings",
            filter=f'spec.target_uuid=="{pv_uuid}" and '
            "spec.finding_categories contains [FINDING_CATEGORY_VULNERABILITY]",
            mask="uuid,spec.level,spec.finding_metadata.vulnerability.meta.name,"
            "spec.finding_metadata.vulnerability.spec.aliases,"
            "spec.finding_metadata.vulnerability.spec.summary",
            page_size=100,
        )
        vulns: list[DependencyVulnerability] = []
        for finding in findings:
            spec = finding.get("spec") or {}
            vuln = ((spec.get("finding_metadata") or {}).get("vulnerability") or {})
            aliases = list((vuln.get("spec") or {}).get("aliases") or [])
            primary = next(
                (a for a in aliases if a.upper().startswith("CVE-")),
                (vuln.get("meta") or {}).get("name"),
            )
            level = spec.get("level") or ""
            vulns.append(
                DependencyVulnerability(
                    id=primary or "unknown",
                    aliases=aliases,
                    severity=level[len(_LEVEL):] if level.startswith(_LEVEL) else None,
                    summary=(vuln.get("spec") or {}).get("summary"),
                )
            )
        return DependencyVulnerabilities(
            purl=p, package_name=package_name, vulnerabilities=vulns
        )


def _clean_level(value: Any) -> str | None:
    """Strip Endor enum prefixes so severity reads as CRITICAL, HIGH, …."""

    if not isinstance(value, str):
        return None
    for prefix in ("FINDING_LEVEL_", "LEVEL_"):
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def _first_number(value: Any) -> float | None:
    nums = _flatten_numbers(value) if isinstance(value, (dict, list)) else {}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return next(iter(nums.values()), None)


def _reference_urls(value: Any) -> list[str]:
    urls: list[str] = []
    for ref in value or []:
        if isinstance(ref, dict) and isinstance(ref.get("url"), str):
            urls.append(ref["url"])
        elif isinstance(ref, str):
            urls.append(ref)
    return urls[:10]

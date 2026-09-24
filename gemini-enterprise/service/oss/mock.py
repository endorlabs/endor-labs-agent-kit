"""Deterministic OSS client for local dev and tests (no network)."""

from __future__ import annotations

from .client import OssIntelClient, _purl_version
from .models import (
    DependencyVulnerabilities,
    DependencyVulnerability,
    PackageRisk,
    UpgradeRecommendations,
    VulnerabilityDetail,
)
from .refs import normalize_advisory_id, validate_purl
from .upgrades import compute_upgrade_options


class OssMockClient(OssIntelClient):
    def vulnerability_details(self, advisory_id: str) -> VulnerabilityDetail | None:
        vid = normalize_advisory_id(advisory_id)
        if vid == "CVE-2021-44228":
            return VulnerabilityDetail(
                id="CVE-2021-44228",
                aliases=["CVE-2021-44228", "GHSA-jfh8-c2jp-5v3q"],
                summary="Remote code injection in Log4j",
                severity="CRITICAL",
                cvss_score=10.0,
                epss_score=0.94,
                references=["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
                fixed_versions=["2.15.0"],
            )
        return VulnerabilityDetail(id=vid, found=False)

    def package_risk(self, purl: str) -> PackageRisk:
        p = validate_purl(purl)
        return PackageRisk(
            purl=p,
            package_name=p.split("://", 1)[-1].split("@", 1)[0],
            ecosystem=p.split("://", 1)[0],
            scores={"scorecard.overall": 6.4, "security.score": 3.1},
        )

    def dependency_vulnerabilities(self, purl: str) -> DependencyVulnerabilities:
        p = validate_purl(purl)
        return DependencyVulnerabilities(
            purl=p,
            package_name=p.split("://", 1)[-1].split("@", 1)[0],
            vulnerabilities=[
                DependencyVulnerability(
                    id="CVE-2021-44228",
                    aliases=["CVE-2021-44228", "GHSA-jfh8-c2jp-5v3q"],
                    severity="CRITICAL",
                    summary="Remote code injection in Log4j",
                )
            ],
        )

    def recommend_upgrades(self, purl: str) -> UpgradeRecommendations:
        p = validate_purl(purl)
        current = _purl_version(p)
        vulns = [
            ("CVE-2021-44228", ["2.15.0"]),
            ("CVE-2021-45046", ["2.16.0"]),
            ("CVE-2021-44832", ["2.17.1"]),
        ]
        options, data_gaps = compute_upgrade_options(current, vulns)
        return UpgradeRecommendations(
            purl=p,
            package_name=p.split("://", 1)[-1].split("@", 1)[0],
            current_version=current,
            current_vulnerabilities=[v[0] for v in vulns],
            options=options,
            data_gaps=data_gaps,
        )

"""Result models for the three OSS-intelligence tools (Option A)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VulnerabilityDetail(BaseModel):
    """`get_endor_vulnerability` — details for one CVE/GHSA."""

    id: str
    aliases: list[str] = Field(default_factory=list)
    summary: str | None = None
    severity: str | None = None
    cvss_score: float | None = None
    epss_score: float | None = None
    references: list[str] = Field(default_factory=list)
    found: bool = True


class PackageRisk(BaseModel):
    """`check_dependency_for_risks` — Endor scores for a package version."""

    purl: str
    package_name: str | None = None
    ecosystem: str | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    found: bool = True


class DependencyVulnerability(BaseModel):
    id: str
    aliases: list[str] = Field(default_factory=list)
    severity: str | None = None
    summary: str | None = None


class DependencyVulnerabilities(BaseModel):
    """`check_dependency_for_vulnerabilities` — known vulns for a package."""

    purl: str
    package_name: str | None = None
    vulnerabilities: list[DependencyVulnerability] = Field(default_factory=list)
    found: bool = True

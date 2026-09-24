"""Framework-neutral tool functions for the ADK agent (customer-hosted MVP).

Thin wrappers over the shared :class:`OssIntelClient` so the ADK agent, the A2A
app, and the tests all call the same, already-tested code. There is **no ADK
import here** — this module is importable and testable without ``google-adk``.

The client is selected by ``OSS_CLIENT`` (``mock`` default, ``rest`` for live
Endor OSS data), exactly like the rest of the service.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .factory import build_oss_client


@lru_cache(maxsize=1)
def _client():
    return build_oss_client()


def vulnerability_details(advisory_id: str) -> dict[str, Any]:
    """Get details for a specific open-source vulnerability by CVE or GHSA id.

    Args:
        advisory_id: A CVE, GHSA, or BIT id, e.g. "CVE-2021-44228".

    Returns:
        The vulnerability's severity, CVSS/EPSS scores, summary, and aliases.
    """
    result = _client().vulnerability_details(advisory_id)
    return result.model_dump(mode="json") if result is not None else {"found": False}


def dependency_vulnerabilities(purl: str) -> dict[str, Any]:
    """List known vulnerabilities for an open-source package version.

    Args:
        purl: A package URL, e.g. "mvn://org.apache.logging.log4j:log4j-core@2.14.1"
            or "npm://lodash@4.17.20".

    Returns:
        The package name and the list of known vulnerabilities (id, severity, summary).
    """
    return _client().dependency_vulnerabilities(purl).model_dump(mode="json")


def package_risk(purl: str) -> dict[str, Any]:
    """Get Endor risk scores for an open-source package version.

    Args:
        purl: A package URL, e.g. "pypi://requests@2.19.1".

    Returns:
        The package name and a map of Endor score names to values.
    """
    return _client().package_risk(purl).model_dump(mode="json")


def recommend_upgrades(purl: str) -> dict[str, Any]:
    """Recommend upgrade versions that fix a package version's known vulnerabilities.

    Args:
        purl: A package URL, e.g. "mvn://org.apache.logging.log4j:log4j-core@2.14.1".

    Returns:
        The current version, its known vulnerabilities, and ranked upgrade options
        (each with the advisories it fixes and the jump size), for the
        "pick an upgrade" choice UI.
    """
    return _client().recommend_upgrades(purl).model_dump(mode="json")

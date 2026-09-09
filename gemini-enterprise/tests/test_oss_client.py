"""Offline tests for the Option A OSS-intelligence tools (httpx.MockTransport).

Response shapes mirror the live ``oss`` namespace confirmed during the P0 spike.
"""

from __future__ import annotations

import httpx
import pytest

from service.a2a.errors import InvalidParamsError
from service.endor_client.token_source import ForwardedBearer
from service.oss.client import OssRestClient
from service.oss.mock import OssMockClient
from service.oss.refs import normalize_advisory_id, validate_purl
from service.oss.tools import TOOL_NAMES, dispatch_tool

PURL = "mvn://org.apache.logging.log4j:log4j-core@2.14.1"
PV_UUID = "634a0f27a6fad281952b77d5"


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    filt = request.url.params.get("list_parameters.filter", "")

    def rows(objects):
        return httpx.Response(200, json={"list": {"objects": objects}})

    if path.endswith("/vulnerabilities"):
        return rows([{
            "meta": {"name": "GHSA-jfh8-c2jp-5v3q"},
            "spec": {
                "summary": "Remote code injection in Log4j",
                "aliases": ["GHSA-jfh8-c2jp-5v3q", "CVE-2021-44228"],
                "cvss_v3_severity": {"level": "CRITICAL", "score": 10.0},
                "epss_score": {"probability": 0.94},
                "references": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2021-44228"}],
            },
        }])
    if path.endswith("/package-versions"):
        found = "log4j-core" in filt
        return rows([{"uuid": PV_UUID, "spec": {"package_name": "mvn://org.apache.logging.log4j:log4j-core"}}] if found else [])
    if path.endswith("/metrics"):
        return rows([{"meta": {"name": "scorecard"}, "spec": {"metric_values": {"overall": 6.4, "nested": {"security": 3.1}}}}])
    if path.endswith("/findings"):
        return rows([{
            "spec": {
                "level": "FINDING_LEVEL_CRITICAL",
                "finding_metadata": {"vulnerability": {
                    "meta": {"name": "GHSA-jfh8-c2jp-5v3q"},
                    "spec": {"aliases": ["GHSA-jfh8-c2jp-5v3q", "CVE-2021-44228"], "summary": "RCE in Log4j"},
                }},
            }
        }])
    return httpx.Response(404)


def _client() -> OssRestClient:
    http = httpx.Client(transport=httpx.MockTransport(_handler), base_url="https://api.test")
    return OssRestClient(ForwardedBearer("svc.token", "https://api.test"), http_client=http)


# -- reference validation (injection safety) ----------------------------------

def test_refs_validation():
    assert normalize_advisory_id("cve-2021-44228") == "CVE-2021-44228"
    assert validate_purl("mvn://g:a@1.2.3") == "mvn://g:a@1.2.3"
    for bad in ['CVE-2021-44228" or "1', "DROP", "GHSA-xx"]:
        with pytest.raises(InvalidParamsError):
            normalize_advisory_id(bad)
    for bad in ['mvn://a" or x', "not a purl", "mvn://a b"]:
        with pytest.raises(InvalidParamsError):
            validate_purl(bad)


# -- the three tools ----------------------------------------------------------

def test_vulnerability_details():
    v = _client().vulnerability_details("CVE-2021-44228")
    assert v.found and v.id == "CVE-2021-44228"
    assert "CVE-2021-44228" in v.aliases
    assert v.severity == "CRITICAL" and v.cvss_score == 10.0
    assert v.epss_score == 0.94
    assert v.references == ["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"]


def test_package_risk_flattens_scores():
    r = _client().package_risk(PURL)
    assert r.found and r.package_name == "mvn://org.apache.logging.log4j:log4j-core"
    assert r.scores["scorecard.overall"] == 6.4
    assert r.scores["scorecard.nested.security"] == 3.1


def test_dependency_vulnerabilities():
    d = _client().dependency_vulnerabilities(PURL)
    assert d.found and d.vulnerabilities
    v = d.vulnerabilities[0]
    assert v.id == "CVE-2021-44228" and v.severity == "CRITICAL"


def test_package_not_found():
    r = _client().package_risk("npm://does-not-exist@0.0.0")
    assert r.found is False and r.scores == {}


def test_dispatch_tool_via_mock():
    client = OssMockClient()
    assert TOOL_NAMES == {"vulnerability_details", "dependency_vulnerabilities", "package_risk"}
    assert dispatch_tool(client, "vulnerability_details", {"advisory_id": "CVE-2021-44228"}).found
    assert dispatch_tool(client, "package_risk", {"purl": PURL}).scores
    with pytest.raises(ValueError):
        dispatch_tool(client, "bogus", {})

"""The ADK tool functions (customer-hosted MVP), offline via the mock client.

These are the plain-python functions the ADK agent registers as tools; ADK isn't
imported here, so they're testable without google-adk.
"""

from __future__ import annotations

import pytest

from service.oss import adk_tools


@pytest.fixture(autouse=True)
def _mock_client(monkeypatch):
    monkeypatch.setenv("OSS_CLIENT", "mock")
    adk_tools._client.cache_clear()
    yield
    adk_tools._client.cache_clear()


def test_vulnerability_details_returns_json_dict():
    d = adk_tools.vulnerability_details("CVE-2021-44228")
    assert d["id"] == "CVE-2021-44228"
    assert d["severity"] == "CRITICAL"


def test_unknown_advisory_reports_not_found():
    d = adk_tools.vulnerability_details("CVE-2000-0001")
    assert d["found"] is False


def test_dependency_vulnerabilities_returns_list():
    d = adk_tools.dependency_vulnerabilities(
        "mvn://org.apache.logging.log4j:log4j-core@2.14.1"
    )
    assert d["found"] is True
    assert isinstance(d["vulnerabilities"], list) and d["vulnerabilities"]


def test_package_risk_returns_scores():
    d = adk_tools.package_risk("npm://lodash@4.17.20")
    assert d["scores"]


def test_recommend_upgrades_returns_ranked_options():
    d = adk_tools.recommend_upgrades(
        "mvn://org.apache.logging.log4j:log4j-core@2.14.1"
    )
    assert d["found"] is True
    assert d["current_version"] == "2.14.1"
    assert [o["version"] for o in d["options"]] == ["2.15.0", "2.16.0", "2.17.1"]
    recommended = [o for o in d["options"] if o["recommended"]]
    assert len(recommended) == 1 and recommended[0]["version"] == "2.17.1"
    assert recommended[0]["fixes_all"] is True


def test_bad_identifier_is_rejected():
    from service.a2a.errors import InvalidParamsError

    with pytest.raises(InvalidParamsError):
        adk_tools.vulnerability_details("not-an-advisory")

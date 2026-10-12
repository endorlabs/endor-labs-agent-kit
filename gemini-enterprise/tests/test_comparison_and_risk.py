"""Phase 3+6 (Google/Veer feedback): organize the output.

#6 — risk scores render as a human summary, never raw Endor metric paths.
#3 — two+ CVEs asked together produce a comparison, rendered as an A2UI
     Canvas + IFrameSrcdoc HTML table (text comparison remains the fallback).
"""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

from service.oss.app import app
from service.oss.mock import OssMockClient
from service.oss.router import RuleBasedRouter, _risk_summary
from service.oss.ui import to_a2ui_comparison_parts

client = TestClient(app)
_ids = itertools.count(1)
A2UI_MIME = "application/json+a2ui"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for key in ("OSS_CLIENT", "OSS_ROUTER", "OSS_UI_PROTOCOL"):
        monkeypatch.delenv(key, raising=False)
    from service.oss.factory import build_oss_router

    build_oss_router.cache_clear()
    yield
    build_oss_router.cache_clear()


def _ask(text: str) -> dict:
    body = {
        "jsonrpc": "2.0", "id": next(_ids), "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}},
    }
    return client.post("/", json=body).json()


def _parts(result: dict) -> list[dict]:
    return result["result"]["artifacts"][0]["parts"]


def _text(result: dict) -> str:
    return next((p["text"] for p in _parts(result) if p.get("kind") == "text"), "")


# -- #6 risk formatting --------------------------------------------------------

def test_risk_summary_is_human_readable_not_raw_paths():
    scores = {
        "package_version_scorecard.scorecard.score_card.overall_score": 6.0,
        "pkg_version_stats_for_vuln.vulnerabilityStatsType.vulnerability_stats.critical_vulnerabilities": 0.0,
        "pkg_version_stats_for_vuln.vulnerabilityStatsType.vulnerability_stats.high_vulnerabilities": 2.0,
    }
    out = _risk_summary(scores)
    assert "overall risk 6/10" in out
    assert "2 high" in out and "0 critical" in out
    # never leak the raw metric path names
    assert "scorecard" not in out and "pkg_version_stats" not in out


def test_risk_answer_has_no_raw_field_names():
    result = _ask("What's the Endor risk score for npm://lodash@4.17.20?")
    txt = _text(result)
    assert "Endor risk for" in txt
    assert "package_version_scorecard" not in txt and "vulnerabilityStatsType" not in txt


# -- #3 comparison -------------------------------------------------------------

def test_router_compares_two_cves():
    r = RuleBasedRouter(OssMockClient())
    ans = r.answer("Compare CVE-2021-44228 with CVE-2021-45046")
    assert len(ans.comparison) == 2
    assert [d.id for d in ans.comparison] == ["CVE-2021-44228", "CVE-2021-45046"]
    assert ans.answer.startswith("Comparing CVE-2021-44228 vs CVE-2021-45046")
    assert ans.advisory is None  # comparison path, not single-advisory


def test_single_cve_is_not_a_comparison():
    r = RuleBasedRouter(OssMockClient())
    ans = r.answer("What is CVE-2021-44228?")
    assert ans.comparison == []
    assert ans.advisory is not None


def test_comparison_surface_cards_carry_both_cves():
    r = RuleBasedRouter(OssMockClient())
    details = r.answer("Compare CVE-2021-44228 with CVE-2021-45046").comparison
    parts = to_a2ui_comparison_parts(details)
    data_model = next(p["data"]["updateDataModel"]["value"] for p in parts if "updateDataModel" in p["data"])
    ids = [c["id"] for c in data_model["cves"]]
    assert ids == ["CVE-2021-44228", "CVE-2021-45046"]
    first = data_model["cves"][0]
    assert "CRITICAL" in first["meta"] and "CVSS 10" in first["meta"]


def test_comparison_card_dedups_and_caps_fixed_versions():
    from service.oss.models import VulnerabilityDetail
    from service.oss.ui import _comparison_card

    d = VulnerabilityDetail(
        id="CVE-x", found=True, severity="CRITICAL",
        fixed_versions=["2.15.0", "2.15.0", "1.9.2", "2.15.0", "a", "b", "c", "d", "e"],
    )
    card = _comparison_card(d)
    assert card["fixed"].count("2.15.0") == 1   # de-duplicated
    assert "(+1 more)" in card["fixed"]          # 7 unique -> 6 shown + 1 more


def test_comparison_emits_a2ui_card_surface(monkeypatch):
    """Rendered with the proven basic catalog (inline), not an IFrameSrcdoc — GE
    leaves the composite-catalog iframe blank."""
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    result = _ask("Compare CVE-2021-44228 with CVE-2021-45046")
    a2ui = [
        p["data"] for p in _parts(result)
        if p.get("kind") == "data" and (p.get("metadata") or {}).get("mimeType") == A2UI_MIME
    ]
    kinds = [next(iter(m.keys() - {"version"})) for m in a2ui]
    assert kinds == ["createSurface", "updateComponents", "updateDataModel"]
    assert a2ui[0]["createSurface"]["catalogId"].endswith("basic_catalog.json")
    ids = {c["id"] for c in a2ui[1]["updateComponents"]["components"]}
    assert {"root", "heading", "cve-list", "cve-card", "cve-id"} <= ids
    assert not any(c["component"] == "IFrameSrcdoc" for c in a2ui[1]["updateComponents"]["components"])
    # the plain-text comparison must still be present (fallback)
    assert "Comparing" in _text(result)


def test_single_cve_emits_no_comparison_surface(monkeypatch):
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    result = _ask("What is CVE-2021-44228?")
    a2ui = [
        p for p in _parts(result)
        if p.get("kind") == "data" and (p.get("metadata") or {}).get("mimeType") == A2UI_MIME
    ]
    assert not a2ui

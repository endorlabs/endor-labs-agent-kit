"""Phase 4 (Google/Veer #4): a package's known vulnerabilities render as cards, each
with a clickable "Explain" button that re-asks "What is <CVE>". Basic catalog
(inline, proven). The text list remains the fallback; upgrade flow is unaffected.
"""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

from service.oss.app import app

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


def _ask(text: str, protocol: str | None = None) -> dict:
    body = {
        "jsonrpc": "2.0", "id": next(_ids), "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}},
    }
    return client.post("/", json=body).json()


def _parts(result: dict) -> list[dict]:
    return result["result"]["artifacts"][0]["parts"]


def _a2ui(result: dict) -> list[dict]:
    return [
        p["data"] for p in _parts(result)
        if p.get("kind") == "data" and (p.get("metadata") or {}).get("mimeType") == A2UI_MIME
    ]


def test_vuln_list_emits_clickable_cards(monkeypatch):
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    result = _ask("What are the vulnerabilities in mvn://org.apache.logging.log4j:log4j-core@2.14.1?")
    a2ui = _a2ui(result)
    kinds = [next(iter(m.keys() - {"version"})) for m in a2ui]
    assert kinds == ["createSurface", "updateComponents", "updateDataModel"]
    assert a2ui[0]["createSurface"]["surfaceId"] == "endor-vuln-list"
    comps = a2ui[1]["updateComponents"]["components"]
    btn = next(c for c in comps if c["id"] == "vuln-btn")
    assert btn["component"] == "Button"
    assert btn["action"]["event"]["name"] == "explain_cve"
    assert btn["action"]["event"]["context"]["cve"] == {"path": "id"}
    # the data model carries each CVE id
    model = a2ui[2]["updateDataModel"]["value"]
    assert any("CVE-2021-44228" == v["id"] for v in model["vulns"])


def test_clicking_explain_returns_cve_detail():
    purl_q_surface = "endor-vuln-list"
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "message/send",
        "params": {"message": {"role": "user", "parts": [
            {"kind": "text", "text": "User action triggered."},
            {"kind": "data", "metadata": {"mimeType": A2UI_MIME}, "data": {
                "version": "v0.9",
                "action": {
                    "name": "explain_cve",
                    "context": {"cve": "CVE-2021-44228"},
                    "sourceComponentId": "vuln-btn",
                    "surfaceId": purl_q_surface,
                },
            }},
        ]}},
    }
    result = client.post("/", json=body).json()
    data = next(p["data"] for p in _parts(result) if p.get("kind") == "data" and "answer" in p.get("data", {}))
    assert "CVE-2021-44228" in data["answer"]
    assert data["advisory"]["severity"] == "CRITICAL"


def test_upgrade_query_shows_choicepicker_not_vuln_list(monkeypatch):
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    result = _ask("How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?")
    surfaces = {m["createSurface"]["surfaceId"] for m in _a2ui(result) if "createSurface" in m}
    assert "endor-upgrade-choices" in surfaces
    assert "endor-vuln-list" not in surfaces


def test_plain_cve_question_has_no_vuln_list(monkeypatch):
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    result = _ask("What is CVE-2021-44228?")
    surfaces = {m["createSurface"]["surfaceId"] for m in _a2ui(result) if "createSurface" in m}
    assert "endor-vuln-list" not in surfaces

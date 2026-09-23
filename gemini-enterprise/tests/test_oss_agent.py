"""End-to-end OSS agent over A2A JSON-RPC (P2), mock client."""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

from service.a2a import errors
from service.oss.app import app

client = TestClient(app)
_ids = itertools.count(1)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for key in ("OSS_CLIENT", "OSS_ROUTER", "OSS_MODEL", "OSS_MODEL_PROVIDER",
                "OSS_INFO_TOKEN", "OSS_UI_PROTOCOL", "GOOGLE_GENAI_USE_VERTEXAI"):
        monkeypatch.delenv(key, raising=False)
    from service.oss.factory import build_oss_router

    build_oss_router.cache_clear()
    yield
    build_oss_router.cache_clear()


def _ask(text: str) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": next(_ids),
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}},
    }
    return client.post("/", json=body).json()


def _data(result: dict) -> dict:
    parts = result["result"]["artifacts"][0]["parts"]
    return next(p["data"] for p in parts if p["kind"] == "data")


def test_agent_card_served():
    card = client.get("/.well-known/agent-card.json").json()
    assert card["skills"][0]["id"] == "oss_intelligence"
    assert "securitySchemes" not in card  # public access


def test_ask_about_cve_end_to_end():
    result = _ask("What is CVE-2021-44228?")
    assert result["result"]["status"]["state"] == "completed"
    data = _data(result)
    assert data["advisory"]["severity"] == "CRITICAL"
    assert "CVE-2021-44228" in data["answer"]


def test_ask_about_package_end_to_end():
    result = _ask("Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable?")
    data = _data(result)
    assert "dependency_vulnerabilities" in data["tools_used"]


def _parts(result: dict) -> list[dict]:
    return result["result"]["artifacts"][0]["parts"]


def test_upgrade_question_emits_a2a_interactive_element_by_default():
    # OSS_UI_PROTOCOL unset (hermetic) -> A2A structured parts.
    result = _ask("How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?")
    ui_parts = [
        p for p in _parts(result)
        if p["kind"] == "data" and (p.get("metadata") or {}).get("endor/ui")
    ]
    assert len(ui_parts) == 1
    element = ui_parts[0]["data"]
    assert element["type"] == "endor.upgrade_choices"
    assert any(c["recommended"] for c in element["choices"])
    # No AG-UI events in metadata on the default A2A path.
    meta = result["result"]["artifacts"][0].get("metadata") or {}
    assert "endor/ag_ui_events" not in meta


def test_upgrade_question_emits_ag_ui_events_when_selected(monkeypatch):
    monkeypatch.setenv("OSS_UI_PROTOCOL", "ag_ui")
    result = _ask("How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?")
    events = result["result"]["artifacts"][0]["metadata"]["endor/ag_ui_events"]
    assert [e["type"] for e in events] == ["RUN_STARTED", "CUSTOM", "RUN_FINISHED"]
    assert events[1]["name"] == "endor.upgrade_choices"
    # And no A2A interactive data part on the AG-UI-only path.
    assert not [
        p for p in _parts(result)
        if p["kind"] == "data" and (p.get("metadata") or {}).get("endor/ui")
    ]


def test_upgrade_question_emits_a2ui_surface_when_selected(monkeypatch):
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    result = _ask("How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?")
    a2ui = [
        p for p in _parts(result)
        if p["kind"] == "data" and (p.get("metadata") or {}).get("mimeType") == "application/json+a2ui"
    ]
    # createSurface + updateComponents + updateDataModel
    assert len(a2ui) == 3
    kinds = [next(iter(p["data"].keys() - {"version"})) for p in a2ui]
    assert kinds == ["createSurface", "updateComponents", "updateDataModel"]
    versions = [o["version"] for o in a2ui[2]["data"]["updateDataModel"]["value"]["options"]]
    assert versions == ["2.15.0", "2.16.0", "2.17.1"]


def test_agent_card_declares_a2ui_extension():
    card = client.get("/.well-known/agent-card.json").json()
    exts = card["capabilities"].get("extensions") or []
    a2ui = [e for e in exts if e["uri"].endswith("a2a-extension/a2ui/v0.9")]
    assert a2ui, "agent card must advertise the A2UI v0.9 extension"
    assert a2ui[0]["params"]["supportedCatalogIds"] == [
        "https://a2ui.org/specification/v0_9/basic_catalog.json"
    ]


def test_a2ui_extension_activation_is_echoed():
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "What is CVE-2021-44228?"}]}},
    }
    uri = "https://a2ui.org/a2a-extension/a2ui/v0.9"
    r = client.post("/", json=body, headers={"X-A2A-Extensions": uri})
    assert r.headers.get("X-A2A-Extensions") == uri
    # Not echoed when the client didn't request it.
    r2 = client.post("/", json=body)
    assert "X-A2A-Extensions" not in r2.headers


def test_select_upgrade_event_returns_confirmation(monkeypatch):
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    purl = "mvn://org.apache.logging.log4j:log4j-core@2.14.1"
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "message/send",
        "params": {"message": {"role": "user", "parts": [
            {"kind": "data", "data": {
                "name": "select_upgrade",
                "context": {"version": "2.17.1", "purl": purl},
            }},
        ]}},
    }
    result = client.post("/", json=body).json()
    data = _data(result)
    # Confirms the chosen version and how to apply it.
    assert "2.17.1" in data["answer"]
    assert "recommend_upgrades" in data["tools_used"]
    # Does NOT re-render the choice cards on a selection.
    a2ui = [
        p for p in _parts(result)
        if p["kind"] == "data" and (p.get("metadata") or {}).get("mimeType") == "application/json+a2ui"
    ]
    assert not a2ui


def test_plain_question_has_no_interactive_element():
    result = _ask("What is CVE-2021-44228?")
    assert not [
        p for p in _parts(result)
        if p["kind"] == "data" and (p.get("metadata") or {}).get("endor/ui")
    ]
    meta = result["result"]["artifacts"][0].get("metadata") or {}
    assert "endor/ag_ui_events" not in meta


def test_tasks_get_roundtrip():
    sent = _ask("What is CVE-2021-44228?")
    task_id = sent["result"]["id"]
    got = client.post(
        "/", json={"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": task_id}}
    ).json()
    assert got["result"]["id"] == task_id
    miss = client.post(
        "/", json={"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": "nope"}}
    ).json()
    assert miss["error"]["code"] == errors.TASK_NOT_FOUND


def test_unknown_method():
    r = client.post(
        "/", json={"jsonrpc": "2.0", "id": 1, "method": "message/stream", "params": {}}
    ).json()
    assert r["error"]["code"] == errors.METHOD_NOT_FOUND


# -- health + token-gated model info ------------------------------------------

def test_healthz_is_public_and_minimal():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_model_info_disabled_without_token_env():
    # OSS_INFO_TOKEN unset (hermetic) -> endpoint does not exist.
    assert client.get("/internal/model").status_code == 404


def test_model_info_requires_matching_token(monkeypatch):
    monkeypatch.setenv("OSS_INFO_TOKEN", "s3cret")
    assert client.get("/internal/model").status_code == 404  # missing header
    assert client.get("/internal/model", headers={"x-info-token": "wrong"}).status_code == 404
    r = client.get("/internal/model", headers={"x-info-token": "s3cret"})
    assert r.status_code == 200
    assert "router" in r.json()


def test_model_info_reflects_config(monkeypatch):
    monkeypatch.setenv("OSS_INFO_TOKEN", "tok")
    monkeypatch.setenv("OSS_ROUTER", "model")
    monkeypatch.setenv("OSS_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "1")
    body = client.get("/internal/model", headers={"x-info-token": "tok"}).json()
    assert body["router"] == "model"
    assert body["providers"] == ["gemini"]
    assert body["transport"] == "vertex"
    assert body["model"]  # a non-empty default

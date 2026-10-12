"""Regression guardrails for the richer-A2UI work (Google/Veer feedback, Oct 2026).

The golden rule of the rich-UI plan is **additive only**: no matter which UI
protocol or flag is enabled, every answer must still carry (a) a plain-text answer
part and (b) the structured ``data`` answer whose ``answer`` field is non-empty.
That is the graceful-degradation guarantee — if any A2UI surface fails to render,
the user still gets today's working answer.

These tests fail loudly if a future UI change ever drops the answer, breaks the
one shipped A2UI surface (the upgrade ChoicePicker), or regresses the 11 demo/POV
prompts shipped in ``marketplace-readiness/README.md``. Run deterministically
against the mock client (no network, no creds).
"""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

from service.oss.app import app

client = TestClient(app)
_ids = itertools.count(1)


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for key in (
        "OSS_CLIENT", "OSS_ROUTER", "OSS_MODEL", "OSS_MODEL_PROVIDER",
        "OSS_INFO_TOKEN", "OSS_UI_PROTOCOL", "OSS_GE_SUGGESTIONS",
        "GOOGLE_GENAI_USE_VERTEXAI",
    ):
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


def _text_answer(result: dict) -> str | None:
    return next((p["text"] for p in _parts(result) if p.get("kind") == "text"), None)


def _data_answer(result: dict) -> str | None:
    for p in _parts(result):
        if p.get("kind") == "data" and isinstance(p.get("data"), dict) and "answer" in p["data"]:
            return p["data"]["answer"]
    return None


# The exact demo/POV prompt set published in marketplace-readiness/README.md.
# Keep this list in sync with that doc — it is the user-facing demo script.
DEMO_PROMPTS = [
    "What is CVE-2021-44228?",
    "Explain CVE-2021-45046 — how severe is it and what's affected?",
    "Compare CVE-2021-44228 and CVE-2021-45046.",
    "What are the vulnerabilities in mvn://org.apache.logging.log4j:log4j-core@2.14.1?",
    "Is npm://lodash@4.17.20 vulnerable?",
    "Does pypi://requests@2.19.1 have known CVEs?",
    "Any known vulnerabilities in mvn://com.fasterxml.jackson.core:jackson-databind@2.9.10?",
    "What's the Endor risk score for npm://lodash@4.17.20?",
    "Give me the Endor package risk for mvn://org.apache.logging.log4j:log4j-core@2.14.1",
    "Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable? Recommend a safe upgrade.",
    "What version should I upgrade npm://lodash@4.17.20 to?",
]

# Representative prompt per capability (CVE / package-vulns / risk / upgrade).
REPRESENTATIVE_PROMPTS = [
    "What is CVE-2021-44228?",
    "Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable?",
    "What's the Endor risk score for npm://lodash@4.17.20?",
    "How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?",
]

# Every UI protocol the agent can emit. "default" = OSS_UI_PROTOCOL unset.
PROTOCOLS = ["default", "a2a", "ag_ui", "a2ui", "both"]


def _set_protocol(monkeypatch, proto: str) -> None:
    if proto != "default":
        monkeypatch.setenv("OSS_UI_PROTOCOL", proto)


@pytest.mark.parametrize("proto", PROTOCOLS)
@pytest.mark.parametrize("prompt", REPRESENTATIVE_PROMPTS)
def test_answer_always_carries_text_and_data(monkeypatch, prompt, proto):
    """INVARIANT (additive-only): no UI protocol ever removes the plain-text answer
    or the structured ``data.answer``. This is the guardrail the richer A2UI work
    must never violate."""
    _set_protocol(monkeypatch, proto)
    result = _ask(prompt)
    assert result["result"]["status"]["state"] == "completed", (prompt, proto)
    text = _text_answer(result)
    assert text and text.strip(), f"missing/empty text answer for {prompt!r} ({proto})"
    data_ans = _data_answer(result)
    assert data_ans and data_ans.strip(), f"missing/empty data.answer for {prompt!r} ({proto})"


@pytest.mark.parametrize("flag", ["0", "1"])
def test_ge_suggestions_flag_keeps_answer(monkeypatch, flag):
    """Follow-up suggestion chips (Phase 2) must only append — never displace the
    plain-text / structured answer."""
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    monkeypatch.setenv("OSS_GE_SUGGESTIONS", flag)
    result = _ask("How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?")
    assert (_text_answer(result) or "").strip()
    assert (_data_answer(result) or "").strip()


@pytest.mark.parametrize("prompt", DEMO_PROMPTS)
def test_demo_prompts_all_answer(prompt):
    """Each of the 11 published demo/POV prompts must produce a completed,
    non-empty answer (so the listing's demo script keeps working as we add UI)."""
    result = _ask(prompt)
    assert result["result"]["status"]["state"] == "completed", prompt
    assert (_text_answer(result) or "").strip(), prompt


def test_a2ui_upgrade_surface_golden_structure(monkeypatch):
    """Lock the one shipped A2UI surface (the upgrade ChoicePicker): the three
    messages, the surface id + catalog, the component-tree ids, the select-event
    name, and the data-model shape. Guards it while new surfaces are added."""
    monkeypatch.setenv("OSS_UI_PROTOCOL", "a2ui")
    result = _ask("How do I fix mvn://org.apache.logging.log4j:log4j-core@2.14.1?")
    a2ui = [
        p["data"] for p in _parts(result)
        if p.get("kind") == "data"
        and (p.get("metadata") or {}).get("mimeType") == "application/json+a2ui"
    ]
    assert [next(iter(m.keys() - {"version"})) for m in a2ui] == [
        "createSurface", "updateComponents", "updateDataModel",
    ]
    create, comps, model = a2ui
    assert create["createSurface"]["surfaceId"] == "endor-upgrade-choices"
    assert create["createSurface"]["catalogId"].endswith("basic_catalog.json")

    ids = {c["id"] for c in comps["updateComponents"]["components"]}
    assert {
        "root", "heading", "options-list", "option-card", "opt-button", "opt-button-text",
    } <= ids
    btn = next(c for c in comps["updateComponents"]["components"] if c["id"] == "opt-button")
    assert btn["action"]["event"]["name"] == "select_upgrade"

    value = model["updateDataModel"]["value"]
    assert value["purl"] and isinstance(value["options"], list) and value["options"]
    assert {"version", "purl", "summary", "buttonLabel"} <= set(value["options"][0].keys())

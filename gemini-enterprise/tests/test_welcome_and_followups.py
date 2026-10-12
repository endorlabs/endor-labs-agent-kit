"""Phase 1 (Google/Veer feedback): greeting -> welcome + clickable example queries
(#1 discoverability), and contextual follow-up chips after answers (#2).

Chips render as GE ``application/json+suggestions`` (clicking re-asks the question).
All additive: the plain-text answer is always still present.
"""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

from service.oss.app import app
from service.oss.router import RuleBasedRouter
from service.oss.mock import OssMockClient

client = TestClient(app)
_ids = itertools.count(1)

SUGG_MIME = "application/json+suggestions"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    for key in ("OSS_CLIENT", "OSS_ROUTER", "OSS_UI_PROTOCOL", "OSS_GE_SUGGESTIONS"):
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


def _suggestions(result: dict) -> list[str]:
    """Pull the suggestion-chip questions from the data part (and verify the file
    part mirrors them)."""
    qs = None
    for p in _parts(result):
        if p.get("kind") == "data" and (p.get("metadata") or {}).get("mimeType") == SUGG_MIME:
            qs = p["data"]["recommendedQuestionsResponse"]["questions"]
    return qs or []


def _text(result: dict) -> str:
    return next((p["text"] for p in _parts(result) if p.get("kind") == "text"), "")


# -- router unit level ---------------------------------------------------------

def test_router_greeting_is_welcome_with_examples():
    r = RuleBasedRouter(OssMockClient())
    for greeting in ("Hello", "Hello Auri", "hi", "what can you do?"):
        ans = r.answer(greeting)
        assert ans.is_welcome, greeting
        assert "Endor AURI" in ans.answer and "I can:" in ans.answer
        assert len(ans.suggestions) >= 3
        assert any("CVE-2021-44228" in s for s in ans.suggestions)


def test_router_cve_answer_offers_compare_followup():
    r = RuleBasedRouter(OssMockClient())
    ans = r.answer("What is CVE-2021-44228?")
    assert not ans.is_welcome
    assert any(s.startswith("Compare CVE-2021-44228") for s in ans.suggestions)


def test_router_package_answer_offers_upgrade_or_risk_followup():
    r = RuleBasedRouter(OssMockClient())
    ans = r.answer("Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable?")
    assert ans.suggestions  # at least one contextual next step
    assert any("upgrade" in s.lower() or "risk" in s.lower() for s in ans.suggestions)


# -- end-to-end over the A2A app ----------------------------------------------

@pytest.mark.parametrize("greeting", ["Hello", "Hello Auri", "hello auri", "hi there"])
def test_hello_end_to_end_welcome_and_chips(greeting):
    result = _ask(greeting)
    assert result["result"]["status"]["state"] == "completed"
    # Capabilities are publicized in the text answer...
    assert "Endor AURI" in _text(result) and "risk score" in _text(result)
    # ...and the example queries are offered as clickable chips.
    qs = _suggestions(result)
    assert len(qs) >= 3
    assert any("CVE-2021-44228" in q for q in qs)


def test_chips_are_data_part_only_no_file_attachment():
    """GE renders the data part as chips but errors on a file part with this
    mimeType ("Unsupported attachment", seen live 2026-10-12). Lock: chips are a
    single data part, and no file part carries the suggestions mimeType."""
    result = _ask("Hello")
    sugg = [
        p for p in _parts(result)
        if (p.get("metadata") or {}).get("mimeType") == SUGG_MIME
        or (p.get("kind") == "file" and (p.get("file") or {}).get("mimeType") == SUGG_MIME)
    ]
    assert len(sugg) == 1 and sugg[0]["kind"] == "data"
    assert not any(p.get("kind") == "file" for p in _parts(result))


def test_answer_still_has_text_with_chips():
    """Additive-only: emitting chips never removes the plain-text answer."""
    result = _ask("What is CVE-2021-44228?")
    assert _text(result).strip()
    assert _suggestions(result)  # follow-ups present too

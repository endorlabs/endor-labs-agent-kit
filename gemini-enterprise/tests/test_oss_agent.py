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
    for key in ("OSS_CLIENT", "OSS_ROUTER", "OSS_MODEL"):
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

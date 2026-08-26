"""Transport-level error contract: unexpected exceptions must come back as
JSON-RPC error envelopes (HTTP 200), never as raw HTTP 500s, and must not
leak internal details.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from service.a2a.errors import INTERNAL_ERROR
from service.app import app
from service.config import build_endor_client

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_client_cache():
    """The client factory is cached per process; isolate it per test."""

    build_endor_client.cache_clear()
    yield
    build_endor_client.cache_clear()


def _send_message(text: str = "Check acme/service-api") -> "httpx.Response":  # noqa: F821
    return client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": text}]}},
        },
    )


def test_misconfigured_client_returns_jsonrpc_internal_error(monkeypatch):
    monkeypatch.setenv("ENDOR_CLIENT", "bogus")

    response = _send_message()

    assert response.status_code == 200  # JSON-RPC errors live in the body
    body = response.json()
    assert body["error"]["code"] == INTERNAL_ERROR
    assert body["error"]["message"] == "Internal error"
    # The invalid config value must not leak into the response.
    assert "bogus" not in response.text


def test_missing_rest_credentials_surface_as_auth_error(monkeypatch):
    monkeypatch.setenv("ENDOR_CLIENT", "rest")
    for var in ("ENDOR_API_CREDENTIALS_KEY", "ENDOR_API_CREDENTIALS_SECRET",
                "ENDOR_ALLOW_ENDORCTL_CONFIG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ENDORCTL_CONFIG", "/nonexistent/config.yaml")

    response = _send_message()

    assert response.status_code == 200
    body = response.json()
    from service.a2a.errors import AUTH_FAILED

    assert body["error"]["code"] == AUTH_FAILED

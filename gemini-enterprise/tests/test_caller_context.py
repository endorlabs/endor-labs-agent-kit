"""The CallerContext seam: tenant namespace precedence.

This is the injection point that makes the service multi-tenant-ready, so its
precedence rules are pinned down here.
"""

from __future__ import annotations

from service.a2a.context import CallerContext, resolve_caller_context
from service.a2a.task_handler import handle_message_send
from service.endor_client.mock import MockEndorSCAClient


def _params(text: str, metadata: dict | None = None) -> dict:
    message: dict = {"role": "user", "parts": [{"kind": "text", "text": text}]}
    if metadata is not None:
        message["metadata"] = metadata
    return {"message": message}


def _namespace_of(task: dict) -> str:
    data = next(p for p in task["artifacts"][0]["parts"] if p["kind"] == "data")
    return data["data"]["namespace"]


def test_context_namespace_used_when_request_has_none():
    task = handle_message_send(
        _params("scan acme/service-api"),
        client=MockEndorSCAClient(),
        caller_context=CallerContext(namespace="tenant-x"),
    )
    assert _namespace_of(task) == "tenant-x"


def test_explicit_request_namespace_overrides_context():
    task = handle_message_send(
        _params("scan acme/service-api", {"namespace": "explicit-ns"}),
        client=MockEndorSCAClient(),
        caller_context=CallerContext(namespace="tenant-x"),
    )
    assert _namespace_of(task) == "explicit-ns"


def test_no_context_falls_back_to_request_target():
    task = handle_message_send(
        _params("scan acme/service-api"),
        client=MockEndorSCAClient(),
        caller_context=CallerContext(),
    )
    # Mock derives the namespace from the repo when nothing else is set.
    assert _namespace_of(task) == "acme/service-api"


def test_resolver_reads_endor_namespace_env(monkeypatch):
    monkeypatch.setenv("ENDOR_NAMESPACE", "from-env")
    assert resolve_caller_context("Bearer ignored-for-now").namespace == "from-env"


def test_resolver_namespace_none_without_env(monkeypatch):
    monkeypatch.delenv("ENDOR_NAMESPACE", raising=False)
    assert resolve_caller_context(None).namespace is None

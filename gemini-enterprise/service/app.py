"""FastAPI app exposing the A2A JSON-RPC endpoint and the Agent Card.

v1 / build-order step 2: a local, mocked A2A round-trip. Endpoints:

* ``GET  /healthz``                     -- liveness probe.
* ``GET  /.well-known/agent-card.json`` -- the A2A Agent Card (§4).
* ``POST /``                            -- JSON-RPC 2.0; method ``message/send``.

Auth (OAuth/DCR) and procurement are intentionally absent here -- the public
service will sit behind them (§3, §5), but they are later build-order steps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .a2a.errors import AgentError, MethodNotFoundError
from .a2a.errors import INVALID_REQUEST, PARSE_ERROR
from .a2a.context import resolve_caller_context
from .a2a.task_handler import handle_message_send, handle_tasks_get
from .a2a.task_store import TaskStore
from .config import build_endor_client

# Per-process store so `tasks/get` can return a recently completed task.
_TASK_STORE = TaskStore()

_AGENT_CARD_PATH = Path(__file__).resolve().parent.parent / "agent-card.json"

app = FastAPI(
    title="Endor Labs SCA Remediation (Gemini Enterprise)",
    version="1.0.0",
    description="Read-only SCA finding + remediation A2A agent. v1 (mocked).",
)


def _load_agent_card() -> dict[str, Any]:
    return json.loads(_AGENT_CARD_PATH.read_text(encoding="utf-8"))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/.well-known/agent-card.json")
def agent_card() -> JSONResponse:
    return JSONResponse(_load_agent_card())


def _jsonrpc_error(
    request_id: Any, code: int, message: str, *, data: Any | None = None
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    # JSON-RPC transport errors are still HTTP 200; the error lives in the body.
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": error})


def _jsonrpc_result(request_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


@app.post("/")
async def jsonrpc_entrypoint(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 -- any malformed body is a parse error
        return _jsonrpc_error(None, PARSE_ERROR, "Invalid JSON payload")

    if not isinstance(payload, dict):
        return _jsonrpc_error(None, INVALID_REQUEST, "Request must be a JSON object")

    request_id = payload.get("id")

    if payload.get("jsonrpc") != "2.0":
        return _jsonrpc_error(
            request_id, INVALID_REQUEST, "Only JSON-RPC 2.0 is supported"
        )

    method = payload.get("method")
    params = payload.get("params", {})
    caller_context = resolve_caller_context(request.headers.get("authorization"))

    try:
        if method == "message/send":
            result = handle_message_send(
                params,
                client=build_endor_client(),
                caller_context=caller_context,
                task_store=_TASK_STORE,
            )
            return _jsonrpc_result(request_id, result)
        if method == "tasks/get":
            result = handle_tasks_get(params, task_store=_TASK_STORE)
            return _jsonrpc_result(request_id, result)
        raise MethodNotFoundError(f"Unknown method: {method!r}")
    except AgentError as exc:
        return _jsonrpc_error(
            request_id, exc.code, exc.message, data=exc.data
        )
    except NotImplementedError as exc:
        # e.g. ENDOR_CLIENT=rest before the real client lands.
        return _jsonrpc_error(request_id, -32603, str(exc))

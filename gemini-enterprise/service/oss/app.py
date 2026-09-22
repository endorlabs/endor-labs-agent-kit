"""FastAPI app for the Option-A OSS agent (Public Access).

Self-contained A2A JSON-RPC transport (reusing the shared a2a error + task-store
primitives) so the OSS agent is independent of the SCA app. Endpoints:

* ``GET  /healthz``
* ``GET  /.well-known/agent-card.json`` — the OSS Agent Card.
* ``POST /`` — JSON-RPC 2.0; ``message/send`` and ``tasks/get``.

Public Access: no per-user auth here. The "call is from Google against an active
Marketplace order" gate (P3) will wrap this; it is not built yet.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..a2a.errors import INTERNAL_ERROR, INVALID_REQUEST, PARSE_ERROR
from ..a2a.errors import AgentError, MethodNotFoundError
from ..a2a.task_store import TaskStore
from .agent import handle_oss_message, handle_tasks_get
from .factory import build_oss_router

logger = logging.getLogger(__name__)

_TASK_STORE = TaskStore()
_AGENT_CARD_PATH = Path(__file__).resolve().parents[2] / "agent-card-oss.json"

app = FastAPI(
    title="Endor AURI Agent (Gemini Enterprise)",
    version="1.0.0",
    description="Public-access OSS vulnerability / package-risk / CVE agent (Option A).",
)


def _load_agent_card() -> dict[str, Any]:
    return json.loads(_AGENT_CARD_PATH.read_text(encoding="utf-8"))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    # Public liveness probe — intentionally reveals nothing.
    return {"status": "ok"}


@app.get("/internal/model")
def model_info(request: Request) -> JSONResponse:
    """Token-gated model/provider info (no secrets).

    Disabled unless ``OSS_INFO_TOKEN`` is set (fail-closed). Requires a matching
    ``X-Info-Token`` header; any miss returns 404 so the endpoint does not
    advertise its existence.
    """

    expected = os.environ.get("OSS_INFO_TOKEN")
    provided = request.headers.get("x-info-token", "")
    if not expected or not hmac.compare_digest(provided, expected):
        return JSONResponse({"error": "not found"}, status_code=404)
    from .model import active_model

    return JSONResponse(active_model())


@app.get("/.well-known/agent-card.json")
def agent_card() -> JSONResponse:
    return JSONResponse(_load_agent_card())


def _error(request_id: Any, code: int, message: str, *, data: Any | None = None) -> JSONResponse:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": err})


def _result(request_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


@app.post("/")
async def jsonrpc_entrypoint(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return _error(None, PARSE_ERROR, "Invalid JSON payload")
    if not isinstance(payload, dict):
        return _error(None, INVALID_REQUEST, "Request must be a JSON object")

    request_id = payload.get("id")
    if payload.get("jsonrpc") != "2.0":
        return _error(request_id, INVALID_REQUEST, "Only JSON-RPC 2.0 is supported")

    method = payload.get("method")
    params = payload.get("params", {})
    try:
        if method == "message/send":
            result = handle_oss_message(
                params, router=build_oss_router(), task_store=_TASK_STORE
            )
            return _result(request_id, result)
        if method == "tasks/get":
            return _result(request_id, handle_tasks_get(params, task_store=_TASK_STORE))
        raise MethodNotFoundError(f"Unknown method: {method!r}")
    except AgentError as exc:
        return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": exc.to_jsonrpc()})
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled error in OSS agent method %r", method)
        return _error(request_id, INTERNAL_ERROR, "Internal error")

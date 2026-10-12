#!/usr/bin/env python3
"""Local A2UI tester for the Endor AURI agent.

Renders the agent's actual A2UI surfaces in a browser *before* anything is
deployed — the Phase-0 safety net for the richer-UI work. It does NOT modify the
agent: it imports the real FastAPI A2A app and mounts it under ``/agent``, then
serves the renderer (index.html) from the same origin (so no CORS, no proxy).

Runs the agent against the deterministic **mock** client with A2UI enabled, so it
needs no Endor credentials and no network.

Run:
    .venv/bin/python tools/a2ui_tester/serve.py          # then open http://localhost:8099
Override the port with A2UI_TESTER_PORT.
"""

from __future__ import annotations

import os
from pathlib import Path

# Configure the agent for local, deterministic, A2UI rendering BEFORE importing it.
os.environ.setdefault("OSS_CLIENT", "mock")
os.environ.setdefault("OSS_ROUTER", "rule")
os.environ.setdefault("OSS_UI_PROTOCOL", "a2ui")
os.environ.setdefault("OSS_GE_SUGGESTIONS", "1")

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402

from service.oss.app import app as agent_app  # noqa: E402

tester = FastAPI(title="Endor AURI A2UI local tester")
tester.mount("/agent", agent_app)

_INDEX = Path(__file__).with_name("index.html")


@tester.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(_INDEX.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("A2UI_TESTER_PORT", "8099"))
    print(f"\n  Endor AURI A2UI tester  →  http://localhost:{port}\n")
    uvicorn.run(tester, host="127.0.0.1", port=port)

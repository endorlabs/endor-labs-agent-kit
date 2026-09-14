#!/usr/bin/env python3
"""Live 'ask a question -> get an answer' through the OSS agent (Option A, P2).

Runs the full A2A round-trip: NL question -> rule-based router -> the three OSS
tools against Endor's public `oss` data -> A2A answer. No model key, no customer
tenant. Once a ModelRouter is wired, set OSS_ROUTER=model and this is unchanged.

Usage:
    ENDOR_ALLOW_ENDORCTL_CONFIG=1 python scripts/oss_agent_smoke.py "your question"
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_QUESTIONS = [
    "What is CVE-2021-44228 and how severe is it?",
    "Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable?",
    "What's the risk score for mvn://com.fasterxml.jackson.core:jackson-databind@2.9.8?",
]


def main() -> int:
    os.environ.setdefault("OSS_CLIENT", "rest")
    os.environ.setdefault("OSS_ROUTER", "rule")

    from fastapi.testclient import TestClient

    from service.oss.app import app

    questions = sys.argv[1:] or _QUESTIONS
    with TestClient(app) as client:
        for q in questions:
            body = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "message/send",
                "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": q}]}},
            }
            payload = client.post("/", json=body).json()
            print(f"\nQ: {q}")
            if "error" in payload:
                print(f"   error {payload['error']['code']}: {payload['error']['message']}")
                continue
            data = next(
                p["data"] for p in payload["result"]["artifacts"][0]["parts"] if p["kind"] == "data"
            )
            print(f"   tools: {data['tools_used']}")
            print(f"   A: {data['answer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

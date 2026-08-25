#!/usr/bin/env python3
"""Live integration smoke test against a real Endor tenant.

Drives the full A2A JSON-RPC round-trip through the FastAPI app with the real
Endor REST client (``ENDOR_CLIENT=rest``), proving auth + project resolution +
findings retrieval end to end. Credentials are read by the service from env or
``~/.endorctl/config.yaml`` -- this script never handles them directly.

Usage:
    ENDOR_CLIENT=rest python scripts/endor_smoke.py [owner/repo] [--p0]

Defaults to the ram-learn demo project when no target is given.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure the service package is importable when run from the repo dir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default="rd-endor/sca-basic-cursor")
    parser.add_argument("--p0", action="store_true", help="P0 only")
    parser.add_argument("--limit", type=int, default=10, help="sample findings to print")
    args = parser.parse_args()

    os.environ.setdefault("ENDOR_CLIENT", "rest")

    from fastapi.testclient import TestClient

    from service.app import app

    ask = f"Find {'P0 ' if args.p0 else ''}open source vulnerabilities in {args.target}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": ask}]}},
    }

    with TestClient(app) as client:
        response = client.post("/", json=body)

    payload = response.json()
    if "error" in payload:
        print(f"JSON-RPC error {payload['error']['code']}: {payload['error']['message']}")
        return 1

    task = payload["result"]
    data = next(p["data"] for p in task["artifacts"][0]["parts"] if p["kind"] == "data")

    print(f"ask         : {ask}")
    print(f"task.state  : {task['status']['state']}")
    print(f"status      : {data['status']}")
    print(f"namespace   : {data['namespace']}")
    print(f"summary     : {data['findings_summary']}")
    print(f"data_gaps   : {data['data_gaps']}")
    print(f"findings    : {len(data['findings'])} (showing up to {args.limit})")
    for f in data["findings"][: args.limit]:
        ids = ",".join(f["vulnerability_ids"][:3])
        print(
            f"  [{f['severity']}] {f['package']}@{f['current_version']} "
            f"-> {f['recommended_action']} {f['target_version'] or ''}  {ids}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

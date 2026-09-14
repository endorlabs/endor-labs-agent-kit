#!/usr/bin/env python3
"""Query a deployed Endor OSS agent on Agent Engine — for you or a teammate.

A teammate needs only:
  1. `roles/aiplatform.user` on the project (grant shown in the README), and
  2. `pip install google-cloud-aiplatform vertexai` + `gcloud auth application-default login`.

Usage:
    export GOOGLE_CLOUD_PROJECT=gen-lang-client-0726330811
    export AGENT_ENGINE_LOCATION=us-central1
    export AGENT_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
    python adk/query_agent_engine.py "What is CVE-2021-44228?"
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    question = " ".join(sys.argv[1:]) or "What is CVE-2021-44228?"

    import vertexai
    from vertexai import agent_engines

    vertexai.init(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("AGENT_ENGINE_LOCATION", "us-central1"),
    )
    remote = agent_engines.get(os.environ["AGENT_RESOURCE_NAME"])

    # Managed session, so multi-turn/resume works server-side.
    session = remote.create_session(user_id="teammate-test")
    print(f"Q: {question}\n")
    for event in remote.stream_query(
        user_id="teammate-test", session_id=session["id"], message=question
    ):
        for part in (event.get("content", {}) or {}).get("parts", []):
            if part.get("text"):
                print(part["text"], end="")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

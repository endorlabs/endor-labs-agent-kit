#!/usr/bin/env python3
"""Deploy the Endor OSS ADK agent to Vertex AI Agent Engine (customer-hosted).

This packages the ADK agent + the local `service` package and creates a managed
Agent Engine instance — the runtime that provides sessions, resume, and
isolation. Run it with YOUR gcloud/ADC credentials; it deploys to your project.

Prereqs (once):
    gcloud auth application-default login
    gcloud services enable aiplatform.googleapis.com --project=$GOOGLE_CLOUD_PROJECT
    gsutil mb -l us-central1 gs://$GOOGLE_CLOUD_PROJECT-agent-staging   # any bucket

Run:
    export GOOGLE_CLOUD_PROJECT=gen-lang-client-0726330811
    export STAGING_BUCKET=gs://gen-lang-client-0726330811-agent-staging
    export GOOGLE_GENAI_USE_VERTEXAI=1
    export GOOGLE_CLOUD_LOCATION=global          # models serve from global
    python adk/deploy_agent_engine.py

Notes:
* Agent Engine itself is regional (AGENT_ENGINE_LOCATION, default us-central1);
  the *model* uses GOOGLE_CLOUD_LOCATION=global (set above), which the agent
  picks up at runtime.
* The one thing to expect to tweak on first run is bundling the local `service`
  package (extra_packages). If the remote import of `service` fails, adjust the
  path below. Default client is the offline mock; set OSS_CLIENT=rest + the Endor
  credential as env_vars to serve live Endor OSS data.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))       # .../gemini-enterprise/adk
_ROOT = os.path.dirname(_HERE)                            # .../gemini-enterprise
sys.path.insert(0, _ROOT)                                 # import `service`
sys.path.insert(0, _HERE)                                 # import `endor_oss`


def main() -> int:
    import vertexai
    from vertexai import agent_engines
    from vertexai.preview.reasoning_engines import AdkApp

    from endor_oss.agent import root_agent

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    staging = os.environ["STAGING_BUCKET"]
    engine_location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")

    vertexai.init(project=project, location=engine_location, staging_bucket=staging)

    app = AdkApp(agent=root_agent, enable_tracing=True)
    remote = agent_engines.create(
        agent_engine=app,
        display_name="Endor OSS Intelligence",
        description="Open-source vulnerability, package-risk, and CVE answers (public data).",
        requirements=os.path.join(_HERE, "requirements.txt"),
        extra_packages=[os.path.join(_ROOT, "service")],   # bundle the shared core
        env_vars={
            "GOOGLE_GENAI_USE_VERTEXAI": "1",
            "GOOGLE_CLOUD_LOCATION": os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
            "OSS_MODEL": os.environ.get("OSS_MODEL", "gemini-3.6-flash"),
            "OSS_CLIENT": os.environ.get("OSS_CLIENT", "mock"),
        },
    )
    print("\nDeployed Agent Engine:")
    print("  resource_name:", remote.resource_name)
    print("\nSave that resource_name — use it in adk/query_agent_engine.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

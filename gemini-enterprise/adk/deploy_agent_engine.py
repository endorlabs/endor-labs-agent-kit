#!/usr/bin/env python3
"""Deploy the Endor OSS ADK agent to Vertex AI Agent Engine (customer-hosted).

This packages the ADK agent + the local `service` package and creates a managed
Agent Engine instance — the runtime that provides sessions, resume, and
isolation. Run it with YOUR gcloud/ADC credentials; it deploys to your project.

Prereqs (once):
    pip install -r adk/requirements-deploy.txt   # deploy-host libs (vertexai, etc.)
    gcloud auth application-default login
    gcloud services enable aiplatform.googleapis.com --project=$GOOGLE_CLOUD_PROJECT
    gsutil mb -l us-central1 gs://$GOOGLE_CLOUD_PROJECT-agent-staging   # any bucket

The script runs a preflight (env vars, gs:// bucket, and — if a deploy dep or the
Vertex AI API is missing — the exact command to fix it) and exits 2 before
touching Agent Engine if anything is missing.

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
* Model: the agent defaults to the latest alias (gemini-flash-latest) with
  automatic fallback (see endor_oss/agent.py). Pin a specific id only by
  exporting OSS_MODEL — it is not hardcoded here.
* The one thing to expect to tweak on first run is bundling the local `service`
  package (extra_packages). If the remote import of `service` fails, adjust the
  path below. Default client is the offline mock; set OSS_CLIENT=rest + the Endor
  credential as env_vars to serve live Endor OSS data.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))       # .../gemini-enterprise/adk
_ROOT = os.path.dirname(_HERE)                            # .../gemini-enterprise
sys.path.insert(0, _ROOT)                                 # import `service`
sys.path.insert(0, _HERE)                                 # import `endor_oss`

# Markers that mean "the Vertex AI API is not enabled on this project" — so we
# can turn an opaque stack trace into the one command that fixes it.
_API_DISABLED_MARKERS = (
    "aiplatform.googleapis.com",
    "service_disabled",
    "has not been used in project",
    "api has not been used",
    "accessnotconfigured",
    "it is disabled",
)


class PreflightError(Exception):
    """A deploy prerequisite is missing; the message says how to fix it."""


def _require_env(name: str, example: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise PreflightError(f"{name} is not set. Export it first, e.g.\n    export {name}={example}")
    return value


def _check_staging_bucket(staging: str, project: str) -> None:
    if not staging.startswith("gs://"):
        raise PreflightError(
            f"STAGING_BUCKET must be a gs:// URI, got: {staging!r}\n"
            f"    export STAGING_BUCKET=gs://{project}-agent-staging"
        )
    bucket = staging[len("gs://"):].split("/", 1)[0]
    if not bucket:
        raise PreflightError(f"STAGING_BUCKET has no bucket name: {staging!r}")
    try:
        from google.cloud import storage
    except ImportError:
        print(f"  [preflight] google-cloud-storage not installed; skipping existence "
              f"check for gs://{bucket} (it must already exist).")
        return
    try:
        exists = storage.Client(project=project).lookup_bucket(bucket) is not None
    except Exception as exc:  # noqa: BLE001 - a check failure shouldn't mask the real deploy
        print(f"  [preflight] could not verify gs://{bucket} ({exc}); continuing.")
        return
    if not exists:
        raise PreflightError(
            f"Staging bucket gs://{bucket} does not exist (or is not visible to you).\n"
            f"Create it once:\n    gsutil mb -l us-central1 gs://{bucket}"
        )
    print(f"  [preflight] staging bucket gs://{bucket}: OK")


def _looks_like_api_disabled(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(m in text for m in _API_DISABLED_MARKERS)


def main() -> int:
    try:
        project = _require_env("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0726330811")
        staging = _require_env("STAGING_BUCKET", f"gs://{os.environ.get('GOOGLE_CLOUD_PROJECT', 'PROJECT')}-agent-staging")
        _check_staging_bucket(staging, project)
    except PreflightError as exc:
        print(f"\nPreflight failed:\n  {exc}\n")
        return 2

    engine_location = os.environ.get("AGENT_ENGINE_LOCATION", "us-central1")

    try:
        import vertexai
        from vertexai import agent_engines
        from vertexai.preview.reasoning_engines import AdkApp
    except ImportError as exc:
        print(
            f"\nPreflight failed: deploy libraries are not installed ({exc}).\n"
            f"Install the deploy-host deps (these are NOT part of the agent runtime):\n"
            f"    pip install -r {os.path.join(_HERE, 'requirements-deploy.txt')}\n"
        )
        return 2

    from endor_oss.agent import root_agent

    # Only pin the model if explicitly provided; otherwise the agent resolves the
    # latest alias (gemini-flash-latest) with automatic fallback.
    env_vars = {
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        "GOOGLE_CLOUD_LOCATION": os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
        "OSS_CLIENT": os.environ.get("OSS_CLIENT", "mock"),
    }
    for optional in ("OSS_MODEL", "OSS_MODEL_FALLBACK"):
        if os.environ.get(optional):
            env_vars[optional] = os.environ[optional]

    vertexai.init(project=project, location=engine_location, staging_bucket=staging)

    app = AdkApp(agent=root_agent, enable_tracing=True)

    # Both `service` (shared core) and `endor_oss` (the agent module) must be
    # importable in the remote runtime, because the pickled agent references its
    # tool functions by module path. The SDK tars each extra_packages entry with
    # `tar.add(path)` and NO arcname, so an absolute path lands at a nested,
    # non-importable location — the entries MUST be paths relative to a common
    # root that becomes `/code`. The two packages live under different parents,
    # so stage them into one temp root and hand over relative names.
    build_root = tempfile.mkdtemp(prefix="endor-agent-engine-")
    _ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache")
    shutil.copytree(os.path.join(_ROOT, "service"), os.path.join(build_root, "service"), ignore=_ignore)
    shutil.copytree(os.path.join(_HERE, "endor_oss"), os.path.join(build_root, "endor_oss"), ignore=_ignore)

    prev_cwd = os.getcwd()
    os.chdir(build_root)  # so `tar.add("service")` stores an importable arcname
    try:
        remote = agent_engines.create(
            agent_engine=app,
            display_name="Endor OSS Intelligence",
            description="Open-source vulnerability, package-risk, and CVE answers (public data).",
            requirements=os.path.join(_HERE, "requirements.txt"),
            extra_packages=["service", "endor_oss"],  # relative -> /code/service, /code/endor_oss
            env_vars=env_vars,
        )
    except Exception as exc:  # noqa: BLE001 - translate the common misconfig
        if _looks_like_api_disabled(exc):
            print(
                f"\nPreflight failed: the Vertex AI API is not enabled on {project}.\n"
                f"Enable it once, wait ~1 min, then re-run:\n"
                f"    gcloud services enable aiplatform.googleapis.com --project={project}\n"
            )
            return 2
        raise
    finally:
        os.chdir(prev_cwd)
        shutil.rmtree(build_root, ignore_errors=True)

    print("\nDeployed Agent Engine:")
    print("  resource_name:", remote.resource_name)
    print("  model:", env_vars.get("OSS_MODEL", "gemini-flash-latest (default, with fallback)"))
    print("  client:", env_vars["OSS_CLIENT"])
    print("\nSave that resource_name — use it in adk/query_agent_engine.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

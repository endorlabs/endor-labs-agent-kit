#!/usr/bin/env python3
"""Deploy the Endor OSS ADK agent to Vertex AI Agent Engine (customer-hosted).

This packages the ADK agent + the local `service` package and creates a managed
Agent Engine instance — the runtime that provides sessions, resume, and
isolation. Run it with YOUR gcloud/ADC credentials; it deploys to your project.

Prereqs (once):
    pip install -r adk/requirements-deploy.txt   # deploy-host libs (vertexai, etc.)
    gcloud auth application-default login
    gcloud services enable aiplatform.googleapis.com storage.googleapis.com \
        secretmanager.googleapis.com --project=$GOOGLE_CLOUD_PROJECT   # secretmanager: rest+SM only
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
  path below.
* Client: default is the offline mock. Set OSS_CLIENT=rest for live Endor OSS
  data; the Endor credential is resolved here (env or the endorctl config when
  ENDOR_ALLOW_ENDORCTL_CONFIG=1) and stored per OSS_SECRET_BACKEND:
    - secretmanager (default) — value kept in Secret Manager, read by the engine
      via a SecretRef (needs secretmanager.googleapis.com enabled). Recommended.
    - env — value baked in as a PLAINTEXT env var (throwaway/dev only).
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
# can turn an opaque stack trace into the one command that fixes it. Kept
# SPECIFIC on purpose: the bare hostname appears in unrelated aiplatform errors
# (DNS, quota, permission), so matching it would mislabel those as "not enabled".
_API_DISABLED_MARKERS = (
    "service_disabled",
    "has not been used in project",
    "api has not been used",
    "accessnotconfigured",
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


def _project_number(project: str) -> str:
    """Resolve a project's number (needed for the built-in service-agent emails).

    Prefer an explicit PROJECT_NUMBER / GOOGLE_CLOUD_PROJECT_NUMBER env var (the
    README computes it with gcloud), and only fall back to the Resource Manager
    API — which some restricted networks cannot reach.
    """

    explicit = os.environ.get("PROJECT_NUMBER") or os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER")
    if explicit and explicit.strip().isdigit():
        return explicit.strip()
    try:
        from google.cloud import resourcemanager_v3

        proj = resourcemanager_v3.ProjectsClient().get_project(name=f"projects/{project}")
        return proj.name.split("/")[-1]
    except Exception as exc:  # noqa: BLE001
        raise PreflightError(
            f"Could not resolve the project number for {project!r} ({exc}). "
            f"Set it explicitly:\n"
            f"    export PROJECT_NUMBER=$(gcloud projects describe {project} --format='value(projectNumber)')"
        ) from exc


def _provision_secret(project: str, secret_id: str, value: str, accessor_members: list[str]) -> None:
    """Create/version a Secret Manager secret and grant read access to the engine SA.

    Idempotent: creates the secret if absent, always adds a new version with the
    current value, and ensures each ``accessor_members`` principal has
    ``secretmanager.secretAccessor`` on just this secret (least privilege). The
    secret value is never printed.
    """

    from google.api_core.exceptions import Conflict
    from google.cloud import secretmanager

    # Use the REST transport: some environments' gRPC (c-ares) resolver cannot
    # resolve *.googleapis.com even when plain HTTPS can. REST is equivalent here
    # and avoids that failure mode.
    client = secretmanager.SecretManagerServiceClient(transport="rest")
    parent = f"projects/{project}"
    name = f"{parent}/secrets/{secret_id}"
    try:
        client.create_secret(request={
            "parent": parent,
            "secret_id": secret_id,
            "secret": {"replication": {"automatic": {}}},
        })
    except Conflict:
        # Already exists (AlreadyExists subclasses Conflict; the REST transport
        # surfaces a plain 409 Conflict) — reuse it and just add a new version.
        pass
    client.add_secret_version(request={"parent": name, "payload": {"data": value.encode("utf-8")}})

    role = "roles/secretmanager.secretAccessor"
    policy = client.get_iam_policy(request={"resource": name})
    binding = next((b for b in policy.bindings if b.role == role), None)
    if binding is None:
        binding = policy.bindings.add()
        binding.role = role
    changed = False
    for member in accessor_members:
        if member not in binding.members:
            binding.members.append(member)
            changed = True
    if changed:
        client.set_iam_policy(request={"resource": name, "policy": policy})


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

    # For the live (rest) client the remote runtime has no ~/.endorctl/config.yaml,
    # so the Endor credential must travel to the engine. Resolve it HERE via the
    # normal loader (env, or the endorctl config when ENDOR_ALLOW_ENDORCTL_CONFIG=1);
    # the secret is read inside load_credentials and never printed.
    #
    # OSS_SECRET_BACKEND selects how it is stored on the engine:
    #   secretmanager (default) — value lives in Secret Manager; the engine reads
    #     it at runtime via a SecretRef. Access-controlled, rotatable, not in
    #     plain config. This is the §8.4/§11 posture.
    #   env — value is baked into the engine as a PLAINTEXT env var. Simplest, but
    #     readable by anyone with viewer on the reasoning engine. Throwaway only.
    if env_vars["OSS_CLIENT"] == "rest":
        from service.endor_client.auth import load_credentials

        creds = load_credentials()
        env_vars["ENDOR_API_BASE_URL"] = creds.base_url  # not secret
        if creds.namespace:
            env_vars["ENDOR_NAMESPACE"] = creds.namespace  # not secret

        backend = os.environ.get("OSS_SECRET_BACKEND", "secretmanager").strip().lower()
        if backend == "secretmanager":
            from google.cloud.aiplatform_v1 import types as aip_types

            key_id = os.environ.get("OSS_SECRET_ID_KEY", "endor-oss-api-key")
            secret_id = os.environ.get("OSS_SECRET_ID_SECRET", "endor-oss-api-secret")
            # The reasoning engine resolves env SecretRefs as the AI Platform
            # Reasoning Engine service agent — grant it read on just these secrets.
            number = _project_number(project)
            engine_sa = (
                f"serviceAccount:service-{number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
            )
            _provision_secret(project, key_id, creds.key, [engine_sa])
            _provision_secret(project, secret_id, creds.secret, [engine_sa])
            env_vars["ENDOR_API_CREDENTIALS_KEY"] = aip_types.SecretRef(secret=key_id, version="latest")
            env_vars["ENDOR_API_CREDENTIALS_SECRET"] = aip_types.SecretRef(secret=secret_id, version="latest")
            print(f"  [rest] credential in Secret Manager ({key_id}, {secret_id}); "
                  f"engine reads via SecretRef (value not shown)")
        elif backend == "env":
            env_vars["ENDOR_API_CREDENTIALS_KEY"] = creds.key
            env_vars["ENDOR_API_CREDENTIALS_SECRET"] = creds.secret
            print("  [rest] injected Endor credential as PLAINTEXT env "
                  "(OSS_SECRET_BACKEND=env; value not shown)")
        else:
            raise PreflightError(
                f"Unknown OSS_SECRET_BACKEND: {backend!r} (expected 'secretmanager' or 'env')"
            )

    # Transport for the aiplatform client. Default gRPC; set OSS_API_TRANSPORT=rest
    # on networks whose gRPC (c-ares) resolver can't resolve *-aiplatform.googleapis.com
    # even though plain HTTPS can.
    init_kwargs = {}
    transport = os.environ.get("OSS_API_TRANSPORT", "").strip().lower()
    if transport in ("rest", "grpc"):
        init_kwargs["api_transport"] = transport
    vertexai.init(project=project, location=engine_location, staging_bucket=staging, **init_kwargs)

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
                f"(underlying error: {exc!r})\n"
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

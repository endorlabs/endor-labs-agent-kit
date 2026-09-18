# Endor OSS Intelligence — ADK agent (customer-hosted MVP)

The **customer-hosted** shape of the Option-A agent (see
`../docs/architecture-decisions.md`, AD-1). A Google **ADK** agent whose runtime
(Vertex AI **Agent Engine**) provides **sessions, conversation resume, and
per-customer isolation** — so we don't build those ourselves. It reuses the exact
same three OSS tools as the A2A app; only the shell differs.

## Try it locally (chat UI, managed sessions)

From `gemini-enterprise/` with the service installed (`pip install -e ".[dev]"`):

```bash
pip install google-adk
cd adk
adk web            # opens a local chat UI at http://localhost:8000
# or: adk run endor_oss
```

Ask things like:
- "What is CVE-2021-44228?"
- "Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable?"
- "What's the risk score for npm://lodash@4.17.20?"

By default the tools use the **offline mock**. For **real Endor OSS data**:

```bash
OSS_CLIENT=rest ENDOR_ALLOW_ENDORCTL_CONFIG=1 adk web
```

Model / Vertex configuration is read from the environment:
`GOOGLE_GENAI_USE_VERTEXAI=1` + `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION`
(Vertex), or `GOOGLE_API_KEY` (AI Studio). Override the model with `OSS_MODEL`
(default: **latest** via the `gemini-flash-latest` alias, with automatic
fallback to `gemini-3.5-flash` if the latest is unavailable — override the
fallback with `OSS_MODEL_FALLBACK`). On Vertex, use `GOOGLE_CLOUD_LOCATION=global`
— the current Gemini models are served from the `global` endpoint, not regional
ones.

### Run it with an Anthropic key instead (no Google/Vertex needed)

Easiest path for a teammate who has a Claude API key — zero GCP setup:

```bash
pip install litellm                 # ADK talks to Claude via LiteLLM
export ANTHROPIC_API_KEY=sk-ant-...
# optional: pick the exact model your key can use
export ADK_MODEL=anthropic/claude-sonnet-5
cd adk && adk web
```

The agent auto-selects Anthropic when `ANTHROPIC_API_KEY` is set (or force it
with `ADK_MODEL_PROVIDER=anthropic`). Tool-calling and sessions work the same;
only the model differs.

## Deploy to Agent Engine (acts like a customer tenant)

Deploying is **three separate planes** — the deploy only does the first. Miss
plane 2 or 3 and the agent either never appears in the Gemini Enterprise app, or
appears ENABLED but errors on chat.

```bash
export PROJECT=<your-gcp-project>
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
```

### Plane 1 — deploy the runtime (Vertex AI Agent Engine)

One-time prereqs, then deploy with the script (not `adk deploy` — the script
bundles the shared `service`/`endor_oss` packages and runs a preflight):

```bash
pip install -r adk/requirements-deploy.txt          # deploy-host libs (vertexai, ...)
gcloud services enable aiplatform.googleapis.com storage.googleapis.com --project="$PROJECT"
gcloud storage buckets create "gs://$PROJECT-agent-staging" --project="$PROJECT" --location=us-central1

export GOOGLE_CLOUD_PROJECT="$PROJECT"
export STAGING_BUCKET="gs://$PROJECT-agent-staging"
export GOOGLE_GENAI_USE_VERTEXAI=1 GOOGLE_CLOUD_LOCATION=global AGENT_ENGINE_LOCATION=us-central1

# live Endor data (public `oss` namespace still needs a token — 401 without one):
export OSS_CLIENT=rest ENDOR_ALLOW_ENDORCTL_CONFIG=1   # or set ENDOR_API_CREDENTIALS_KEY/SECRET
# or offline demo data: export OSS_CLIENT=mock

python adk/deploy_agent_engine.py                     # prints the reasoningEngine resource_name
```

Note the printed `resource_name`
(`projects/<num>/locations/us-central1/reasoningEngines/<id>`). You can already
query it directly with `adk/query_agent_engine.py` — **planes 2 and 3 are only
needed to use it *inside a Gemini Enterprise app*.**

> Version pinning matters: the agent is pickled locally and unpickled in the
> runtime, so `adk/requirements.txt` and `adk/requirements-deploy.txt` pin
> `google-adk`/`aiplatform`/`genai`/`pydantic` to the **same** versions. A skew
> shows up as `'LlmAgent' object has no attribute 'mode'` at query time.

### Plane 2 — register the agent into your Gemini Enterprise app

Deploying does **not** list the agent in a Gemini Enterprise app. Either click
**➕ Add agent** in the app UI (choose an existing Agent Engine / ADK agent and
paste the `resource_name`), or register via the Discovery Engine API:

```bash
export APP_ENGINE=<your-gemini-enterprise-engine-id>   # e.g. from the app URL / an agent's SPIFFE ID
export REASONING_ENGINE=<resource_name from plane 1>
TOKEN=$(gcloud auth application-default print-access-token)
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: $PROJECT" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/$PROJECT_NUMBER/locations/global/collections/default_collection/engines/$APP_ENGINE/assistants/default_assistant/agents" \
  -d '{
    "displayName": "Endor OSS Intelligence",
    "description": "Open-source vulnerability, package-risk, CVE, and upgrade answers (public data).",
    "adkAgentDefinition": {
      "toolSettings": { "toolDescription": "Answers OSS vulnerability / package-risk / CVE questions and recommends safe upgrade versions." },
      "provisionedReasoningEngine": { "reasoningEngine": "'"$REASONING_ENGINE"'" }
    }
  }'
```

### Plane 3 — grant the app permission to invoke the engine (once per project)

The Gemini Enterprise app calls the reasoning engine through the **Discovery
Engine service agent**, which needs `aiplatform.user`. Without this the agent
shows ENABLED but every chat errors. Required for **every** project that
registers the agent into a Gemini Enterprise app (skip it if you only call the
engine directly). One-time and idempotent:

```bash
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-discoveryengine.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user" --condition=None
```

Then open the agent under **"Our agents"** in the app and chat — e.g. *"known
vulnerabilities and recommended upgrade for
mvn://org.apache.logging.log4j:log4j-core@2.14.1"*.

> **Credential posture:** with `OSS_CLIENT=rest` the deploy stores the Endor
> API key/secret as **plaintext env vars** on the engine. For anything beyond a
> personal MVP, move to Secret Manager + `SecretRef` (design §8.4/§11).

## Layout

```
adk/endor_oss/
  __init__.py    # exposes root_agent for the adk CLI
  agent.py       # root_agent = Agent(model=gemini, tools=[...])
```
The tool functions live in `service/oss/adk_tools.py` (framework-neutral, shared
with the A2A app and covered by `tests/test_adk_tools.py`). Exact ADK
class/command names can vary by `google-adk` version — pin against the version
you install.

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

```bash
adk deploy agent_engine \
  --project <your-gcp-project> \
  --region us-central1 \
  endor_oss
```
Then query it via the Agent Engine SDK/REST, or register it in a Gemini
Enterprise (test) tenant.

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

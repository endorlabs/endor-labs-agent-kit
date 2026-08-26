# Endor Labs SCA Remediation — Gemini Enterprise Marketplace (v1)

A hosted [A2A](https://a2a-protocol.org/) agent that identifies high-severity
open source (SCA) vulnerability findings for a repository and proposes safe
remediation paths. It is published as an agent in the **Gemini Enterprise
Marketplace**.

This is a **continuously-deployed service**, not a generated recipe artifact.
It deliberately lives at the top level in `gemini-enterprise/` — *not* in
`gemini/`, which is the generated Gemini **CLI** extension package owned by
`endor-agent-kit publish ... --prune` and would get pruned. The two "Gemini"
surfaces are unrelated: `gemini/` = Gemini CLI dev tool; `gemini-enterprise/` =
the Google **Gemini Enterprise** product this service integrates with.

> Design source of truth: *SCA Remediation Agent — Gemini Enterprise
> Marketplace (v1)*. Section references (§N) below point at that doc.

## Status — build-order step 2 (mocked A2A round-trip)

| Build-order step (§7) | State |
| --- | --- |
| 1. IdP/DCR spike | ⛔ open question — needs backend/IdP input (see below) |
| 2. Mocked A2A round-trip | ✅ done |
| **3. Real Endor data (direct REST)** | ✅ **this checkpoint** |
| 4. OAuth + DCR | ⬜ not started |
| 5. Procurement + Firestore | ⬜ not started |
| 6. Cloud Run deploy + real Agent Card URL | ⬜ not started |
| 7. Google validation / E2E review | ⬜ not started |

What works today: a local JSON-RPC `message/send` call parses the
natural-language ask, resolves the repo to an Endor project, and returns a
well-formed A2A `Task` whose data artifact matches the §10 result contract —
now from **real Endor SCA findings** (or mocked, by config). No OAuth/DCR yet,
no mutations.

Verified live end-to-end against a real Endor tenant: findings returned with
real package names, CVE/GHSA IDs, and Endor's proposed target versions, through
the full JSON-RPC → parse → REST → map path.

## Decisions locked in for v1

- **Language/runtime:** Python + FastAPI (§9).
- **Endor data access:** direct Endor **REST API** (§9), isolated behind
  `service/endor_client/`. Confirmed against the repo there is no reusable
  in-repo Endor client to import. Endpoints confirmed against the live API:
  - Auth: `POST /v1/auth/api-key` `{key, secret}` → `{token, expirationTime}`,
    then `Authorization: Bearer <token>`.
  - `GET /v1/namespaces/{ns}/projects` — resolve repo → project (filter
    `spec.git.full_name=="owner/repo"`).
  - `GET /v1/namespaces/{ns}/findings` — SCA findings (filter on
    `spec.finding_categories contains [FINDING_CATEGORY_VULNERABILITY]`,
    `spec.project_uuid`, and `spec.level`).
  - `GET /v1/namespaces/{ns}/version-upgrades` — upgrade/UIA evidence (reserved;
    see limitations).
- **Severity mapping (v1, adjustable):** `CRITICAL`/`HIGH` → P0, `MEDIUM`/`LOW`
  → P1; `INFO`/unknown levels are dropped.
- **Read-only:** v1 returns findings + remediation guidance only. No PRs, no
  branch pushes, no writes to customer source/CI (§1). The mutating phase is v2.

## Layout

```
gemini-enterprise/
  agent-card.json            # A2A Agent Card (§4); also served at /.well-known/agent-card.json
  pyproject.toml             # FastAPI service package + dev deps
  .env.example               # local env / secrets placeholders (§11)
  service/
    app.py                   # FastAPI app: JSON-RPC endpoint + Agent Card + health
    config.py                # env-driven Endor client selection (mock | rest)
    a2a/
      errors.py              # typed errors -> JSON-RPC error responses (§10)
      models.py              # result contract + internal request models (§10)
      context.py             # CallerContext seam: auth/token -> tenant namespace
      request_parser.py      # natural-language message -> validated request (§2)
      task_handler.py        # orchestrates parse -> query -> shape Task result
      task_store.py          # bounded in-memory store for tasks/get
      result_formatter.py    # summary counts + status selection
    endor_client/
      base.py                # EndorSCAClient interface + EndorSCAResult
      mock.py                # deterministic fixtures (ENDOR_CLIENT=mock)
      auth.py                # api-key -> bearer-token exchange + caching
      rest.py                # direct Endor REST client (ENDOR_CLIENT=rest)
  scripts/
    endor_smoke.py           # live integration smoke test against a real tenant
  tests/
    test_a2a_roundtrip.py    # step-2 DoD (§12): local JSON-RPC round-trip
    test_rest_client.py      # step-3 offline contract tests (httpx MockTransport)
```

Deferred (later build-order steps, per §6): `service/auth/` (OAuth authorize/
token + DCR), `service/procurement/` (Pub/Sub subscriber + Partner Procurement
client), and `infra/` (Terraform for the §8 GCP resources).

## Run it locally

```bash
cd gemini-enterprise
python -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn service.app:app --reload --port 8080
```

Then exercise the A2A endpoint:

```bash
curl -s localhost:8080/.well-known/agent-card.json | head

curl -s localhost:8080/ -H 'content-type: application/json' -d '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{ "kind": "text", "text": "Check acme/service-api for P0 SCA findings" }]
    }
  }
}'
```

Run the tests (offline; no network or secrets needed):

```bash
cd gemini-enterprise
python -m pytest -q
```

## Run against real Endor data (step 3)

Set `ENDOR_CLIENT=rest`. Credentials are read by the service from env
(`ENDOR_API_CREDENTIALS_KEY` / `ENDOR_API_CREDENTIALS_SECRET`, plus optional
`ENDOR_NAMESPACE` / `ENDOR_API_BASE_URL`) or, for local dev, from
`~/.endorctl/config.yaml`. The service reads only those keys — it never echoes
the file, and the secret never leaves `auth.py`.

Live smoke test through the full A2A round-trip:

```bash
cd gemini-enterprise
ENDOR_CLIENT=rest python scripts/endor_smoke.py <owner/repo>
ENDOR_CLIENT=rest python scripts/endor_smoke.py <owner/repo> --p0
```

Serve it with the real client:

```bash
ENDOR_CLIENT=rest uvicorn service.app:app --port 8080
```

### v1 limitations (honest gaps)

- `breaking_change_risk` is reported as `unknown` for every finding. Per-finding
  breaking-change risk needs correlation with the `version-upgrades`/UIA
  resource (from/to, conflicts, CIA). The client already reaches that endpoint;
  wiring it into per-finding risk + safest-upgrade ranking is the next step
  (3.1) and mirrors the CLI recipe's UIA logic.
- Findings are read up to a cap (`_MAX_FINDINGS`); a truncated read is recorded
  in `data_gaps` rather than silently dropped.
- `recommended_action`/`patch_available` come from `spec.proposed_version`,
  `spec.fixing_patch`, and `FINDING_TAGS_FIX_AVAILABLE`; Endor-Patch specifics
  are surfaced only as `patch_available`, not yet as a distinct patch plan.

## Gemini-swap readiness

The A2A/transport and data seams are structured so that replacing the local
test driver with real Gemini Enterprise is a fill-in, not a refactor:

- **Tenant seam.** [context.py](service/a2a/context.py) `resolve_caller_context()`
  is the single place where auth becomes a tenant. Today it reads
  `ENDOR_NAMESPACE`; step 4 plugs OAuth-token validation → Endor namespace in
  there. The handler already sources the effective namespace from the context
  (explicit request namespace overrides; otherwise the caller's tenant).
- **A2A protocol.** Parts are accepted with either `kind` or `type`;
  `message/send` and `tasks/get` are handled (`tasks/get` returns a proper A2A
  `TaskNotFound` for unknown ids); streaming/push are advertised off.
- **Client seam.** `EndorSCAClient` swaps mock↔REST by config with no handler
  changes.

Still required before a real Gemini round-trip (steps 4–6): OAuth/DCR + the
token→tenant resolver, a public deployment URL, and Producer Portal
registration. Two things to verify against the exact A2A version Gemini
Enterprise speaks: the Agent Card `protocolVersion` and the multi-tenant client
(today a single service credential + `default_namespace`; per-tenant credential
resolution replaces that once auth lands).

## Input modes (§2)

A2A skills are natural-language triggered, so the target lives in the task
message rather than a rigid schema. The parser accepts:

- a GitHub/GitLab **repo URL** (optionally with a `ref` in message `metadata`),
- an **`owner/repo`** shorthand in the text,
- **`namespace`** / **`endor_project_id`** in message `metadata`.

Ambiguous requests (no resolvable repo or Endor project) are rejected with a
clear JSON-RPC error rather than returning empty results.

### Mock driver tokens

The mock client keys behavior off the resolved `owner/repo` so tests can drive
the non-happy paths without real Endor:

| Repo token | Behavior |
| --- | --- |
| any other repo | 2 P0 + 5 P1 mocked findings |
| `acme/empty` | resolves, zero findings |
| `acme/partial` | findings + a recorded `data_gap` (status `data_gap`) |
| `acme/needs-auth` | JSON-RPC auth error |
| `acme/forbidden-namespace` | JSON-RPC namespace-not-authorized error |

## Open items to resolve before deeper build (§7 step 1, §8.8)

- **IdP dynamic client registration:** does Endor's IdP support DCR directly,
  or is a thin registration shim needed? Biggest unknown; worth a spike first.
- Whether the target marketplace GCP project's Firestore instance is in Native
  mode and what else uses it (§8.3).
- Whether the Endor REST API is publicly reachable with a service credential or
  needs VPC connectivity (§8.2).
- Custom domain (`agents.endorlabs.com`) vs `*.run.app` for the first Producer
  Portal validation pass (§8.8).

## CI

CI lives at the repo root in `.github/workflows/gemini-enterprise-ci.yml`,
path-filtered to `gemini-enterprise/**` (GitHub only runs workflows from the
repo-root `.github/workflows/`, so the §6 sketch of a nested workflow dir would
be ignored). It is independent of the recipe-publish pipeline.

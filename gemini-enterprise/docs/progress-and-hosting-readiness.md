# Endor Gemini Enterprise Agent — Progress & Hosting Readiness

**Scope:** the **Option A** agent — public-access open-source intelligence
(dependency vulnerabilities, package risk, CVE details) for any Gemini Enterprise
user. No Endor login, no customer data. (Option B — OAuth, tenant-scoped — is
parked; see `docs/auth-design.md`.)

Phase labels used below: **P0** = foundation (tool + auth spike, OSS tool client),
**P2** = model tool-calling loop, **Hosting** = Marketplace Step 4 readiness.

---

## P0 — Foundation: OSS tools + auth model  ✅ committed

**Spike outcomes**
- Identified the three OSS tools (the ones the GitHub Copilot plugin uses):
  `check_dependency_for_vulnerabilities`, `check_dependency_for_risks`,
  `get_endor_vulnerability`.
- Mapped them to Endor REST endpoints in the shared **`oss`** namespace:
  `package-versions` (resolve purl→uuid), `findings` (dependency vulns),
  `metrics` (package risk scores), `vulnerabilities` (CVE/GHSA details).
- **Auth reframe:** confirmed the split — Option A (public, no login, no customer
  data) vs Option B (OAuth authorization server, tenant-scoped). Chose **A**.
  Confirmed Endor's API has **no OAuth authorization server** today; the GitHub
  AgentHQ token-exchange (`endorlabs/monorepo#31669`) is the precedent for B, and
  does **not** apply to A.

**Built — the OSS tool client** (`service/oss/`): `OssRestClient` + `OssMockClient`
for the three tools, injection-safe advisory-id/purl validators, offline tests,
and a live smoke.

**Verified live** against the `oss` namespace, e.g. log4j-core@2.14.1:
`CVE-2021-44228` = CRITICAL / CVSS 10.0, 7 known vulns, 11 Endor scores.

**Status:** committed & pushed (`8f9b9cc7`).

## P2 — Model tool-calling loop  ✅ done (uncommitted)

**Built**
- `ModelRouter` — a bounded agentic loop: the model sees the question + the three
  OSS tool specs, requests tool calls, we execute them against the same client,
  feed results back, and return the synthesized answer.
- **Provider seam, Gemini default, pluggable:** `GeminiBackend` (Vertex AI /
  GenAI function calling), `AnthropicBackend` (switchable), `FallbackBackend`
  (`gemini,anthropic` — falls through if Gemini is unavailable), `MockBackend`
  (scripted, for tests). SDKs are lazy-imported — nothing new is required unless
  the model path is actually run.
- `RuleBasedRouter` — deterministic, zero-dependency default for local demos.
- The OSS agent's own A2A app (`service/oss/app.py`, JSON-RPC `message/send` +
  `tasks/get`) and `agent-card-oss.json` (Public Access — no security schemes).

**Verified**
- Full "ask a question → answer" **live** via the rule router (no model key):
  "What is CVE-2021-44228?" → routes to `vulnerability_details` →
  "CRITICAL, CVSS 10.0, EPSS 0.99999. Remote code injection in Log4j".
- The model loop proven **offline** via `MockBackend` (single/multi-tool,
  tool-error recovery, bounded loop, provider selection + fallback).
- Whole suite: **129 tests pass**.

**Status:** uncommitted (ready to commit).
**Pending:** the real Gemini/Vertex call validates only on deploy; confirm the
exact Gemini model id available in the project (default `gemini-2.5-flash`).

## Hosting readiness — Marketplace Step 4

Step 4 = **Producer Portal → "AI Agent as a Service"** (7 sub-steps: select type,
upload Agent Card via GCS, availability, pricing, backend procurement, Google
validation, publish). Full detail: `docs/marketplace-step4-runbook.md`.

**Prerequisites, by owner**
- **Business (Danny + Google rep) — the real gate, has lead time:** Google Cloud
  Partner Network, Marketplace Vendor Agreement, and **agent nomination** (unlocks
  the "AI Agent as a Service" solution type). Plus pricing model and public-vs-private.
- **Technical (us):**
  - ✅ A2A protocol compliance
  - ✅ Agent Card (`agent-card-oss.json`)
  - ✅ Public-Access auth model (no OAuth/DCR needed for A)
  - ✅ Tools + model loop
  - ⛔ **Deployed, reachable HTTPS endpoint** (Agent Card `url` must be live for
    Google's validation) — needs Cloud Run
  - ⛔ **Procurement wiring** (extend the existing handler to the agent product)
  - ⛔ **Public-Access gate (P3)** — "call is from Google + active order"

**GCP prep (dedicated project) — not yet built:** enable APIs; Dockerfile;
Artifact Registry; Cloud Run + least-privilege SA; custom domain
`agents.endorlabs.com`; versioned GCS bucket for the Agent Card; procurement
Pub/Sub + Partner Procurement API; Workload Identity Federation for CI deploy;
Vertex AI access for the Gemini backend.

**Status:** runbook written; infra-as-code not yet started. Recommended first
artifact: **Dockerfile + Cloud Run** (produces the live URL Step 4 hard-requires).

---

## Questions for GCP (they offered to help)

1. **Public-Access order gating:** for an "AI Agent as a Service" with *no*
   per-user identity, what is the exact mechanism to verify a request is "from
   Google against an active Marketplace order" — a signed `software_statement`,
   request signature, IAM, or something else? Any reference implementation?
2. **Agent Card hosting/validation:** is a GCS-hosted Agent Card the only
   integration for Public Access, and what URL/DNS validation does Google do —
   does the `url` need a custom domain (`agents.endorlabs.com`) or is `*.run.app`
   acceptable for launch?
3. **Procurement reuse:** can the existing SaaS procurement handler
   (project `marketplace-458521`) be reused for the agent product, or does
   "AI Agent as a Service" require a separate product/entitlement? Exact Pub/Sub
   topic + entitlement event shapes?
4. **Project architecture:** can the **Partner project** and **Partner Marketplace
   project** be the same, and can we reuse `marketplace-458521`, or is a fresh
   dedicated project required?
5. **Pricing:** which pricing models are available for Agent-as-a-Service
   (free / flat / usage), and how is "the partner pays the model cost per
   question" typically structured?
6. **Validation & E2E:** what exactly does Google test, and is there a
   sandbox/test Gemini Enterprise tenant we can validate against before publish?
7. **Runtime:** any requirement to run on **Agent Engine** vs **Cloud Run**, or
   region constraints?
8. **DCR:** confirm Dynamic Client Registration is **not** required for the
   Public-Access path (only for OAuth 2.0), so Option A can skip it.
9. **Interactive UI protocol (the "A2-UI" ask):** for the interactive
   upgrade-choice elements Gemini Enterprise should render (the "pick an
   upgrade" options from `recommend_upgrades`), what is the exact protocol the
   frontend consumes — **AG-UI** events, **A2A** structured message parts (e.g.
   a `DataPart` / typed content block), or a Gemini-specific schema? Concretely:
   (a) which event/part types render as selectable choices, (b) the expected
   JSON schema for a choice list and for the user's selection coming back, and
   (c) is there a reference agent or renderer we can validate against so the
   content layer we already built (`UpgradeRecommendations` / `UpgradeOption`)
   maps cleanly onto the wire format without a second redesign?

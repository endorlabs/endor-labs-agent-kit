# Architecture Decisions — Endor Gemini Enterprise Agent

Status date: 2026-09-11. These are the decisions we can make **now**, before
Google confirms the listing mechanics. Guiding principle: **optimize for an MVP
that is trivially easy to try — including from a customer's point of view.**
Concretely, "easy to try" means: a customer (or Danny, or us) can run a real
conversation with the agent with the fewest possible moving parts — no login, no
credentials, no bespoke infrastructure.

Each decision is **Accepted** (safe now) or **Provisional** (revisit when Google
answers — see the open list at the end).

---

## AD-1 — Runtime: package as a Google **ADK agent on Vertex AI Agent Engine**  ·  Accepted
**Decision.** Deliver the agent as a Google Agent Development Kit (ADK) agent,
whose managed runtime is Vertex AI Agent Engine.
**Why.** It hands us **session management, conversation resume, and per-customer
isolation for free** (Danny's three concerns become the platform's job, not our
MVP scope), and `adk web` gives a **local chat UI in one command** — the single
biggest "easy to try" win.
**Consequences.** Build a thin ADK layer over existing tools; do not hand-roll a
session store. The FastAPI A2A app is retained (AD-4) but is no longer the
primary shell.

## AD-2 — Do **not** build custom session / memory / isolation infra  ·  Accepted
**Decision.** Rely on Agent Engine **managed Sessions + Memory Bank** for
persistence/resume; rely on **per-customer deployment** for tenant isolation.
**Why.** Removes the hardest and riskiest MVP work and directly answers Danny.
Anything we build ourselves here is a liability we'd have to secure and operate.

## AD-3 — Scope: ship **Option A (public OSS intelligence)** as the MVP  ·  Accepted
**Decision.** The first agent answers open-source questions (dependency
vulnerabilities, package risk, CVE details) from Endor's public data. No Endor
login, no customer data, no OAuth.
**Why.** Maximally easy to try — a customer can use it **instantly with zero
setup or credentials**. It sidesteps tenant isolation and auth entirely, and it's
already built and live-verified. Tenant-scoped answers (Option B) come later on
the customer-hosted + customer-credential path (AD-6).

## AD-4 — Keep the **hosting-agnostic core**; wrap it per shell  ·  Accepted
**Decision.** The three OSS tools + `OssIntelClient` + the model tool-calling loop
stay framework-agnostic. The **ADK agent** (AD-1) and the existing **A2A FastAPI
app** are both thin shells over that same core.
**Why.** One brain, swappable shells — the pivot to ADK/customer-hosting reuses
everything already built; nothing is thrown away, and we keep A2A as an option.

## AD-5 — Model: **Gemini by default, provider-pluggable**  ·  Accepted
**Decision.** Default to Gemini (Vertex) via the `ModelBackend` seam; keep
Anthropic and a fallback selectable by config.
**Why.** Native to the platform and to the customer's Vertex; already implemented;
switchable if Gemini is unavailable.

## AD-6 — Future tenant-scoped auth: **customer-configured Endor credential**, not Endor-as-OAuth-server  ·  Accepted (for the later phase)
**Decision.** When the tenant-scoped agent arrives, it runs in the customer's
tenant and authenticates to Endor with the **customer's own Endor
credential/namespace** they configure (the GitHub AgentHQ / `#31669` pattern) —
Endor does **not** become an OAuth authorization server.
**Why.** Dissolves the two hardest problems at once (tenant isolation + the
OAuth-AS blocker), and matches a pattern Endor has already shipped.

## AD-7 — Distribution: **customer-hosted** for tenant value; partner-hosted A2A as fallback  ·  Provisional
**Decision (intended).** Target customer-hosted deployment (agent runs in the
customer's Agent Engine) for the tenant-scoped value; keep partner-hosted A2A as
the fallback/Option-A path.
**Why provisional.** The exact **Marketplace listing mechanic** for a
customer-hosted agent is the thing we've asked Google. The **runtime** choice
(AD-1) is safe regardless; only the *listing/distribution* wrapper depends on
their answer.

## AD-8 — Interactive "pick an upgrade" element: **one canonical element, protocol-neutral emission**  ·  Accepted
**Decision.** The "A2-UI" ask (interactive upgrade choices) is built as a single
content layer (`recommend_upgrades` → `UpgradeRecommendations`) plus one
canonical UI element (`UpgradeChoiceElement`) with **two adapters** — A2A
structured message parts and AG-UI events — selected at runtime by
`OSS_UI_PROTOCOL` (`a2a` default, `ag_ui`, or `both`). See `service/oss/ui.py`.
**Why.** Which wire format Gemini Enterprise renders is still an open question to
Google (progress doc, Q9). Keeping the content as the single source of truth and
the protocol as a thin, swappable adapter means confirming AG-UI vs A2A is a
config flip, not a redesign — and we can demo either today.

---

## The MVP, in one sentence
An **ADK agent** answering **public OSS questions** with **Gemini**, run via
**`adk web` locally** and deployable to **Agent Engine** — no login, no
credentials, no custom session/isolation code.

## Deferred pending Google (do not decide yet)
- The **Marketplace listing mechanic** for a customer-hosted agent (vs. partner-hosted "Agent as a Service").
- **Billing/procurement** when the runtime is in the customer's project (who pays the model cost).
- Whether an **A2A container is also required** alongside ADK, or ADK suffices.
- Whether customer-hosting still earns the **"Google Cloud Ready – Agent"** designation.
- A **Gemini Enterprise test tenant** for full end-to-end validation.

## What this unblocks next
Build the **ADK wrapper** over the existing OSS tools + Gemini (AD-1/AD-3/AD-4/AD-5)
so the MVP is runnable via `adk web` — the concrete "easy to try" deliverable —
independent of the deferred Google items.

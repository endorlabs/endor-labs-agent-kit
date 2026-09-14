# Step 4 Runbook — List Endor Labs as an "AI Agent as a Service"

**Goal:** get the Endor **Option A** agent (public-access OSS intelligence)
published on Google Cloud Marketplace / Gemini Enterprise, hosted in the
dedicated GCP project.

Source: Google's "[Publish agents in Gemini Enterprise and Google Cloud
Marketplace](https://cloud.google.com/blog/topics/developers-practitioners/publish-agents-in-gemini-enterprise-and-google-cloud-marketplace)".
Step 4 is **"Publish your agent listing on Marketplace"**, done in the
**Producer Portal**. This runbook is what that entails and the prep that gates it.

---

## The 3-project architecture (Step 1 — do this first)

The blog's Step 1 establishes three projects. Map ours:

| Blog project | Purpose | Endor |
| --- | --- | --- |
| **Customer project** | The buyer's GCP project (Gemini Enterprise) | not ours — the customer's |
| **Partner project** | Hosts the agent runtime (Cloud Run) + Agent Card | **the dedicated GCP project** |
| **Partner Marketplace project** | Marketplace listing, billing, procurement integration | dedicated project (or a sibling) — confirm with Google rep |

**Decision:** is the dedicated project both the Partner *and* Partner Marketplace
project, or two? Existing SaaS procurement already lives in `marketplace-458521`;
confirm whether the agent reuses it or gets a fresh project.

## Prerequisites that gate Step 4

Step 4 cannot start until Steps 2–3 are done. Split by owner:

### Business / org (owner: Danny + Google Cloud rep) — NOT engineering
- Join the **Google Cloud Partner Network**.
- Accept the **Marketplace Vendor Agreement (MVA)**.
- Verify **Agent-as-a-Service** listing eligibility.
- **Nominate the agent** via the Google Cloud representative (required to unlock
  the Producer Portal "AI Agent as a Service" solution type).

### Technical (owner: us) — status for Option A
- ✅ **A2A protocol compliance** — the OSS agent speaks A2A JSON-RPC (`message/send`, `tasks/get`).
- ✅ **Agent Card** — `agent-card-oss.json` exists.
- ✅ **Authentication = Public Access** — Option A needs no OAuth/DCR. (That's the
  whole reason A is lighter than B.) The only auth work is the P3 gate:
  "verify the call is from Google against an active Marketplace order."
- ⛔ **Deployed, reachable agent** — the Agent Card's `url` must point at a live
  HTTPS endpoint. Needs Cloud Run deploy (see prep below).

## Step 4 — the seven sub-steps (Producer Portal)

1. **Select Solution Type → "AI Agent as a Service."** Unlocked only after the
   Google rep nominates the agent (Step 2).
2. **Upload the Agent Card** via a **GCS bucket.** Provide the JSON
   (`agent-card-oss.json`) from a versioned bucket in the dedicated project.
   → *We can prep this now* (bucket + upload).
3. **Availability** — publicly available pricing (self-service) **or** private
   offer only. **Decision (Danny):** Option A is public OSS answers; likely
   public/self-service, possibly free or flat.
4. **Pricing** — create the pricing plan + [pricing model](https://docs.cloud.google.com/marketplace/docs/partners/ai-agents/choose-pricing).
   **Decision (Danny):** per-order / usage / free. Note "Endor pays the model
   cost per question," so pricing must cover that.
5. **Technical Integration** — configure the **backend procurement** (no frontend
   integration). Extend the existing procurement handler to the agent product.
6. **Validation & E2E testing** — Google reviews functionality, security, pricing.
   The agent must be **live and reachable** with a valid Agent Card.
7. **Publish** — the agent goes live on the Marketplace.

## Prep we can start now in the dedicated GCP project

Everything here is infra-as-code / scripts we prepare and you apply; none of it
provisions live resources without your `gcloud` auth.

1. **Enable APIs** on the dedicated project: `run`, `artifactregistry`,
   `storage`, `pubsub`, `secretmanager`, `iamcredentials`,
   `cloudcommerceprocurement`, `logging`, `monitoring`.
2. **Containerize the OSS agent** — a `Dockerfile` (uvicorn + `service.oss.app:app`)
   so it can run on Cloud Run.
3. **Artifact Registry** — a Docker repo for the image.
4. **Cloud Run service** — deploy the OSS agent; get a stable HTTPS URL.
   - Runtime service account with least privilege (Secret Manager accessor for
     the Endor service credential; Pub/Sub subscriber for procurement).
   - `min-instances=1` if cold starts hurt UX.
5. **Custom domain** — map `agents.endorlabs.com` (the Agent Card `url` +, later,
   any callback must be stable public URLs Google validates). `*.run.app` only
   for the earliest smoke.
6. **GCS bucket for the Agent Card** (Step 4.2) — versioned; upload
   `agent-card-oss.json`; update its `url` to the Cloud Run/custom-domain URL.
7. **Procurement** (Step 4.5) — Pub/Sub topic/subscription for Marketplace
   entitlement events + the Partner Procurement API client; extend the existing
   handler to the agent product.
8. **CI/CD deploy** — Workload Identity Federation from GitHub Actions (no
   long-lived keys): `roles/run.admin` + `roles/artifactregistry.writer`.
9. **Model runtime** — Vertex AI access in the project for the Gemini backend
   (`OSS_ROUTER=model`, `OSS_MODEL_PROVIDER=gemini`); the Cloud Run SA needs
   `roles/aiplatform.user`.

## Open decisions (owners)

| Decision | Owner |
| --- | --- |
| Dedicated project id; Partner vs Partner-Marketplace project split | Ram + Google rep |
| Partner Network / MVA / agent nomination | Danny + Google rep |
| Pricing model (free / per-order / usage) and public vs private | Danny |
| Custom domain (`agents.endorlabs.com`) approval | Ram + IT |
| Vertex model id available in the project | Ram (confirm in project) |

## Already done (Option A)
A2A OSS agent (`service/oss/`), the three OSS tools (live-verified), the model
tool-calling loop (Gemini default, pluggable), and `agent-card-oss.json`. What's
left before Step 4 is **deploy + the Public-Access gate + procurement**, plus the
business prerequisites.

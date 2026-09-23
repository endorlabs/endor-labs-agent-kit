# Endor AURI for Developers — infrastructure estimate

Solution Validation (Step 1) infrastructure estimate for a **typical customer
deployment**, matching [architecture.svg](architecture.svg). All resources run in
the **customer's own Google Cloud project** (customer-billed). Endor charges $0
for the agent (it queries public OSS data).

## Assumptions
- Region **us-central1**, on-demand list pricing (confirm in the Pricing Calculator).
- **Single-tenant**: one deployment serves one customer org.
- **Typical volume**: one engineering/security team, ~a few hundred agent queries/month.
- **Router = `rule`** (default): no model calls, so **no Vertex AI/Gemini cost**.
- Cloud Run **scales to zero** (no min-instances).

## Monthly estimate (typical)

| Resource | Spec | Est. $/mo | Notes |
|---|---|---|---|
| **Cloud Run** (the agent) | 1 vCPU, 512 MiB, scale-to-zero | **~$0–3** | Low volume usually lands within the Cloud Run free tier (2M req, 180k vCPU-sec, 360k GiB-sec/mo). |
| **Compute Engine — placeholder VM** | e2-standard-2 (2 vCPU/8 GB), 24×7 | **~$35–49** | The cost driver. It is an **idle Marketplace-validation placeholder** — the agent does not run on it. See "Cost optimization." |
| Boot disk | pd-balanced, 10 GB | ~$1 | For the placeholder VM. |
| **Secret Manager** | 2 secret versions + occasional access | **< $1** | First 6 active versions free; access ops negligible. |
| Network egress | agent → Endor public API (+ optional Gemini) | **< $1** | Small JSON payloads at typical volume. |
| Vertex AI / Gemini | only if `oss_router = model` | **$0** default | Rule router makes no model calls. With the model router, Gemini Flash is a few cents at this volume. |
| **Typical total** | | **~$40–55 / mo** | Essentially all the mandatory placeholder VM. |

## Cost optimization (recommended)
The placeholder VM dominates the bill yet does nothing (it exists only to satisfy
the Marketplace VM-listing validation). Downsizing `var.machine_type` cuts the
total sharply:

| machine_type | vCPU / RAM | ~$/mo (VM) | Typical total |
|---|---|---|---|
| e2-standard-2 (current default) | 2 / 8 GB | ~$35–49 | ~$40–55 |
| **e2-small** | 2 (shared) / 2 GB | ~$12 | **~$14** |
| e2-micro | 2 (shared) / 1 GB | ~$6 (may hit the always-free e2-micro tier) | ~$1–8 |

Since the VM is idle, **e2-small (or e2-micro)** is more than sufficient. Set
`-var machine_type=e2-small` at deploy, or change the default in `deploy/variables.tf`.

## Pricing Calculator
Build/save a shareable estimate at **https://cloud.google.com/products/calculator**
with these line items (us-central1):
1. **Compute Engine** — 1 × e2-standard-2 (or e2-small), 730 hrs/mo, 10 GB pd-balanced.
2. **Cloud Run** — 1 vCPU, 512 MiB; ~a few hundred requests/mo, avg ~1s each (typically free-tier).
3. **Secret Manager** — 2 active versions, ~a few thousand access ops/mo.
4. (Optional) **Vertex AI — Gemini Flash** — only if using the model router.

The Compute Engine placeholder line dominates; everything else is rounding error
at this volume.

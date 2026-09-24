# Marketplace readiness — Endor AURI for Developers

Assets for listing the Endor AURI for Developers on the Google Cloud Marketplace / Gemini
Enterprise, per the Agent Factory onboarding deck (Sept 2026).

## Contents
- [agent-description.md](agent-description.md) — listing copy (name, tagline, short/full description, capabilities), Endor brand voice.
- [eval-plan.md](eval-plan.md) — end-to-end eval set: metrics, targets, and cases (tool selection, grounded correctness, upgrade correctness, no-hallucination, scope).
- [wireframes.html](wireframes.html) — low-fidelity A2UI "pick an upgrade" flow (ask → choose → confirm). Open in a browser.
- [architecture.svg](architecture.svg) / [architecture.png](architecture.png) — GCP architecture diagram (Solution Validation Step 1) with **official Google Cloud icons**: partner vs customer tenant, GCP services used, single-tenant, deploy + runtime flows.
- [infra-estimate.md](infra-estimate.md) — infrastructure cost estimate + Pricing Calculator line items (Step 1). Typical ~$40–55/mo, dominated by the placeholder VM (downsize to e2-small for ~$14).
- [deploy/](deploy/) — Terraform bundle for the customer-tenant (VM-listing) path: **Cloud Run A2UI agent** + placeholder VM, Endor credential via Secret Manager, image-build helper. This is the A2UI (interactive) shape — apply/destroy-verified end-to-end, and the A2UI cards + click confirmed live in GE. See [deploy/README.md](deploy/README.md).

## Status
- **A2UI is GA** in Gemini Enterprise (v0.9) — no allowlist. The agent renders interactive upgrade cards + handles clicks, proven end-to-end in the GE UI on live Endor data.
- **AAAS listing exists** in the Producer Portal ("Endor AURI AI Agent", in progress; GCP team assisted).
- **VM listing** remaining: publish the container image + upload the zip to the corp project, then create the VM product in the Producer Portal.

## Pricing
The agent is **free ($0)**: it queries public OSS intelligence, so Endor incurs
no per-query or data cost. The AAAS listing is a free listing (still required as
the public storefront and the entitlement gate for the hidden VM listing). GTV
and sales-volume estimates are not applicable (those are for paid agents). In the
customer-tenant model, the only costs are the Cloud Run agent (scale-to-zero,
~free at typical volume) and the placeholder VM, in the customer's own project.
See [infra-estimate.md](infra-estimate.md).

## Still to produce / pending
- Publish the agent container image to a customer-pullable registry in `marketplace-458521` (needs Artifact Registry Writer + Cloud Build).
- Upload the VM-listing zip to `gs://marketplace-458521-endor-agent-bundle` (needs `roles/storage.objectAdmin`).
- Create + validate + publish the **VM listing** in the Producer Portal referencing the GCS zip.

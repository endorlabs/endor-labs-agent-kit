# Marketplace readiness — Endor AURI Agent

Assets for listing the Endor AURI Agent on the Google Cloud Marketplace / Gemini
Enterprise, per the Agent Factory onboarding deck (Sept 2026).

## Contents
- [agent-description.md](agent-description.md) — listing copy (name, tagline, short/full description, capabilities), Endor brand voice.
- [eval-plan.md](eval-plan.md) — end-to-end eval set: metrics, targets, and cases (tool selection, grounded correctness, upgrade correctness, no-hallucination, scope).
- [wireframes.html](wireframes.html) — low-fidelity A2UI "pick an upgrade" flow (ask → choose → confirm). Open in a browser.
- [architecture.svg](architecture.svg) / [architecture.png](architecture.png) — GCP architecture diagram (Solution Validation Step 1): partner vs customer tenant, GCP services used, single-tenant, deploy + runtime flows. Swap tiles for official Google Cloud icons before final submission.
- [deploy/](deploy/) — Terraform bundle for the customer-tenant (VM-listing) path: Agent Engine deployment + placeholder VM, Endor credential via Secret Manager, packaging script, and vendored Google module. See [deploy/README.md](deploy/README.md).

## Status
- Access request (A2UI + customer-tenant-deployable Preview) sent to the PDM; awaiting grant.
- Target listing structure (deck + Sunny Walia email): a public **AI Agent as a Service** listing (pricing/transactions) + a hidden **VM listing** (Terraform bundle that deploys to Agent Engine in the customer's tenant).

## Pricing
The agent is **free ($0)**: it queries public OSS intelligence, so Endor incurs
no per-query or data cost. The AAAS listing is a free listing (still required as
the public storefront and the entitlement gate for the hidden VM listing). GTV
and sales-volume estimates are not applicable (those are for paid agents). In the
customer-tenant model, the only costs are Agent Engine runtime and the
placeholder VM, which run in the customer's own project on their billing.

## Still to produce
- Infrastructure estimate + Pricing Calculator link (Solution Validation Step 1), covering the customer-borne Agent Engine + placeholder VM only. (Architecture diagram: done — see above; swap in official GCP icons for final.)
- In-project test of the `deploy/` Terraform (Google validation requires a working deploy), then zip + upload to the Producer Portal.

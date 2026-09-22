# Marketplace readiness — Endor AURI Agent

Assets for listing the Endor AURI Agent on the Google Cloud Marketplace / Gemini
Enterprise, per the Agent Factory onboarding deck (Sept 2026).

## Contents
- [agent-description.md](agent-description.md) — listing copy (name, tagline, short/full description, capabilities), Endor brand voice.
- [eval-plan.md](eval-plan.md) — end-to-end eval set: metrics, targets, and cases (tool selection, grounded correctness, upgrade correctness, no-hallucination, scope).
- [wireframes.html](wireframes.html) — low-fidelity A2UI "pick an upgrade" flow (ask → choose → confirm). Open in a browser.
- [deploy/](deploy/) — Terraform bundle for the customer-tenant (VM-listing) path: Agent Engine deployment + placeholder VM, Endor credential via Secret Manager, packaging script, and vendored Google module. See [deploy/README.md](deploy/README.md).

## Status
- Access request (A2UI + customer-tenant-deployable Preview) sent to the PDM; awaiting grant.
- Target listing structure (deck + Sunny Walia email): a public **AI Agent as a Service** listing (pricing/transactions) + a hidden **VM listing** (Terraform bundle that deploys to Agent Engine in the customer's tenant).

## Still to produce
- Architecture diagram (GCP icons) + infrastructure estimate + Pricing Calculator link (Solution Validation Step 1).
- Pricing model decision for the AAAS listing.
- In-project test of the `deploy/` Terraform (Google validation requires a working deploy), then zip + upload to the Producer Portal.

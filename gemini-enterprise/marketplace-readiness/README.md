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

## Sample prompts (demo / POV script)
Run these in the Gemini Enterprise chat against the registered agent. It answers
open-source vulnerability, package-risk, CVE, and safe-upgrade questions from
Endor's public OSS intelligence (packages use purl form: `mvn://group:artifact@version`,
`npm://pkg@version`, `pypi://pkg@version`, `go://module@version`). Verified live.

**CVE / advisory explanation**
- `What is CVE-2021-44228?`
- `Explain CVE-2021-45046 — how severe is it and what's affected?`
- `Compare CVE-2021-44228 and CVE-2021-45046.`

**Package vulnerabilities (multiple ecosystems)**
- `What are the vulnerabilities in mvn://org.apache.logging.log4j:log4j-core@2.14.1?`
- `Is npm://lodash@4.17.20 vulnerable?`
- `Does pypi://requests@2.19.1 have known CVEs?`
- `Any known vulnerabilities in mvn://com.fasterxml.jackson.core:jackson-databind@2.9.10?`

**Endor package risk score**
- `What's the Endor risk score for npm://lodash@4.17.20?`
- `Give me the package risk for mvn://org.apache.logging.log4j:log4j-core@2.14.1.`

**Safe-upgrade recommendation (emits the interactive A2UI upgrade card)**
- `Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable? Recommend a safe upgrade.`
- `What version should I upgrade npm://lodash@4.17.20 to?`

## Pricing
The agent is **free ($0)**: it queries public OSS intelligence, so Endor incurs
no per-query or data cost. The AAAS listing is a free listing (still required as
the public storefront and the entitlement gate for the hidden VM listing). GTV
and sales-volume estimates are not applicable (those are for paid agents). In the
customer-tenant model, the only costs are the Cloud Run agent (scale-to-zero,
~free at typical volume) and the placeholder VM, in the customer's own project.
See [infra-estimate.md](infra-estimate.md).

## Still to produce / pending
- Publish the agent container image to a customer-pullable registry in `YOUR_PUBLISHER_PROJECT` (needs Artifact Registry Writer + Cloud Build).
- Upload the VM-listing zip to `gs://YOUR_PUBLISHER_PROJECT-endor-agent-bundle` (needs `roles/storage.objectAdmin`).
- Create + validate + publish the **VM listing** in the Producer Portal referencing the GCS zip.

# Endor AURI for Developers — customer-tenant deployment package

Terraform bundle for the **customer-tenant-deployable** Marketplace path (the
hidden **VM listing**). The customer's admin deploys it and the agent runs in
their own Google Cloud project, rendering the **A2UI** interactive upgrade-choice
cards in Gemini Enterprise.

## What it deploys

- **Endor AURI for Developers on Cloud Run** — the A2A endpoint Gemini Enterprise
  talks to. It emits the A2UI v0.9 surface (upgrade cards); a card click returns
  the `select_upgrade` event. Reads the Endor credential from Secret Manager.
- **A placeholder Compute Engine VM** — required only by the Marketplace
  VM-listing validation. The agent does **not** run on it (it's small and idle).

> The earlier Agent Engine variant is retired: Agent Engine returns text only,
> and A2UI renders through the A2A/Cloud Run path. See ../../adk/ for the
> Agent Engine (text) agent if you need it.

## Prerequisites (in the customer project)

1. Enable `run.googleapis.com`, `compute.googleapis.com`, `secretmanager.googleapis.com`.
2. Create two Secret Manager secrets with the Endor API credential:
   ```bash
   printf '%s' "$ENDOR_KEY"    | gcloud secrets create endor-oss-api-key    --data-file=- --project "$PROJECT"
   printf '%s' "$ENDOR_SECRET" | gcloud secrets create endor-oss-api-secret --data-file=- --project "$PROJECT"
   ```
   Pass their names as `endor_api_key_secret_id` / `endor_api_secret_secret_id`.
   The values never enter Terraform state.

## Publish the agent image (once per release, by Endor)

The Terraform runs a pre-built container (`var.container_image`). Publish it to a
registry the customer projects can pull from (public Artifact Registry, or the
Marketplace container path):
```bash
PROJECT=endor-labs-marketplace-public TAG=v1 ./build_and_push_image.sh
```
Then set that image as the `container_image` default (variables.tf) or pass it in.

## Deploy + test in your own project first

Google's validation requires a working deploy. Verify before publishing:
```bash
terraform init
terraform apply \
  -var project_id="$PROJECT" \
  -var goog_cm_deployment_name="endor-auri-test" \
  -var container_image="us-central1-docker.pkg.dev/$PROJECT/endor-agents/oss-a2ui:v1" \
  -var endor_api_key_secret_id="endor-oss-api-key" \
  -var endor_api_secret_secret_id="endor-oss-api-secret"
```
`terraform output agent_card_url` gives the URL to register in Gemini Enterprise.
Sanity check: `curl <agent_url>/.well-known/agent-card.json` should show the A2UI
extension and the card `url` self-set to the Cloud Run URL.

Teardown is a plain `terraform destroy` (the Cloud Run service sets
`deletion_protection = false`, and the VM sets `allow_stopping_for_update`, so it
tears down cleanly).

## Build the Marketplace zip

```bash
zip -r endor-auri-agent.zip \
  main.tf variables.tf outputs.tf \
  metadata.yaml metadata.display.yaml marketplace_test.tfvars README.md
```
Upload to a versioned GCS bucket and reference it as the **VM listing** product in
the Producer Portal (Deployment package → Licensed VM Image → Custom UI
Deployment → `source_image` var → GCS zip URL). Deployment-SA roles to grant:
Service Account Admin, Cloud Run Admin, Vertex AI Administrator, Security Admin,
Project IAM Admin, Compute Admin, Service Account User.

## Customer registration in Gemini Enterprise

After the customer runs the Terraform: **Gemini Enterprise → Governance → Agents
→ Add Agent → Agents via Marketplace**, using the `agent_card_url` output. Grant
users access; the agent appears under "From your organization" and renders the
A2UI upgrade cards. (Public OSS data, so no per-user OAuth.)

## Files

| File | Purpose |
|---|---|
| `main.tf` | Cloud Run A2UI service + runtime SA + secret access + invoker IAM + placeholder VM |
| `variables.tf` | Inputs (project, region, container_image, Endor secret IDs, machine_type, …) |
| `outputs.tf` | `agent_url`, `agent_card_url`, service account, instance info |
| `metadata.yaml` / `metadata.display.yaml` | Marketplace technical + UI metadata |
| `marketplace_test.tfvars` | Sample test values |
| `build_and_push_image.sh` | Build + publish the agent container image |

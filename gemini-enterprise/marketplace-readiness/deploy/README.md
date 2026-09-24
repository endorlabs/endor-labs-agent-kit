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

## Before you deploy — get and store your Endor credential

The agent calls the Endor Labs API to answer open-source questions, so it needs an
**Endor Labs API key + secret**. You supply these through **your own Secret
Manager** — the values never appear in Terraform state, in the container image, or
in the Marketplace deployment form (the form only takes the secret *names*).

> **You need an active Endor Labs account with API access.** The agent authenticates
> as your Endor API key; it reads public open-source intelligence, but the API call
> itself is authenticated. If you don't have a key, get one from Endor Labs first.

**Step 1 — Create an Endor API key.**
In the Endor Labs app: **Settings → API Keys → Create API Key**. Copy the **key**
and **secret** (the secret is shown only once).

**Step 2 — Enable the required Google Cloud APIs** in the project you'll deploy into:
```bash
gcloud services enable \
  run.googleapis.com compute.googleapis.com secretmanager.googleapis.com \
  --project "$PROJECT"
```

**Step 3 — Store the credential in Secret Manager** (in the same project):
```bash
printf '%s' "$ENDOR_KEY"    | gcloud secrets create endor-oss-api-key    --data-file=- --project "$PROJECT"
printf '%s' "$ENDOR_SECRET" | gcloud secrets create endor-oss-api-secret --data-file=- --project "$PROJECT"
```
`$ENDOR_KEY` / `$ENDOR_SECRET` are the values from Step 1. You can name the secrets
anything; the defaults above match the sample tfvars.

**Step 4 — Reference the secrets by name at deploy time** (Marketplace UI or
`terraform apply`):
- `endor_api_key_secret_id`    → `endor-oss-api-key`
- `endor_api_secret_secret_id` → `endor-oss-api-secret`

Terraform grants the agent's Cloud Run service account `secretAccessor` on those two
secrets and injects them at runtime via `secret_key_ref`. **The credential values
never enter Terraform state or the image** — only the secret names are passed.

> **Rotating the credential:** add a new version to the secret
> (`gcloud secrets versions add …`); the agent picks it up on its next start (the
> Cloud Run service references the secret, not a pinned version). No redeploy needed
> if you use the `latest` alias.

## Publish the agent image (once per release, by Endor)

The Terraform runs a pre-built container (`var.container_image`). Publish it to a
registry the customer projects can pull from (public Artifact Registry, or the
Marketplace container path). The image is built from a **committed git ref**
(`GIT_REF`, default `HEAD`) — not the working tree — so the artifact is
reproducible and no uncommitted work-in-progress can leak in. Tag a release
first (this repo uses `agents-vX.Y.Z`), then build from that tag:
```bash
git tag agents-v2.3.0            # tag the release commit on the feature branch
PROJECT=endor-labs-marketplace-public GIT_REF=agents-v2.3.0 TAG=v1 ./build_and_push_image.sh
```
The script prints the image's **immutable `@sha256` digest**. Pin that digest as
the `container_image` default in [variables.tf](variables.tf) (not the mutable
`:v1` tag) so customers always pull the exact validated bits:
```hcl
default = "us-central1-docker.pkg.dev/endor-labs-marketplace-public/endor-agents/oss-a2ui@sha256:<hex>"
```

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
Upload to a GCS bucket **with object versioning enabled** (Google requires it) and
reference it as the **VM listing** product in the Producer Portal (Deployment
package → **manual configuration** → **custom UI deployment** → Image variable
`source_image` → GCS Object Location = the uploaded zip).

**Deployment-SA roles to grant** (Google's baseline list for VM listings, plus
**Cloud Run Admin** which our Terraform additionally needs because it creates a
Cloud Run service + invoker IAM):
- Service Account Admin
- Cloud Infrastructure Manager Agent  ← runs the Terraform via Infra Manager
- **Cloud Run Admin**  ← our addition (Cloud Run service + `allUsers` invoker)
- Vertex AI Administrator
- Security Admin
- Project IAM Admin
- Compute Admin
- Service Account User

> **Marketplace Terraform runtime is 1.5.7** (Infra Manager). Our config uses only
> the `hashicorp/google` provider and no local modules, so it is compatible; there
> is no `modules/` dir to bundle (unlike Google's Agent-Engine example). Validate
> against 1.5.7 before publishing if you change the config.
>
> **Packaging note:** Google's `HOW_TO_PACKAGE.md` targets the *Agent Engine*
> model (source packaged into `assets/source.tar.gz` + `agent_package_name`). This
> bundle uses the **Cloud Run + pre-built image** model instead — the agent image
> is published to Artifact Registry and pinned by digest in `var.container_image`,
> so the zip carries **only** Terraform + metadata (no source tar, no
> `agent_config.auto.tfvars`).

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

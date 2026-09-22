# Endor AURI Agent — customer-tenant deployment package

Terraform bundle for the **customer-tenant-deployable** Marketplace path (the
hidden **VM listing**). The customer's admin clicks deploy in the Marketplace and
this Terraform stands up the Endor AURI Agent on **Vertex AI Agent Engine** in
their own project.

Adapted from Google's `marketplace-agents-package` reference. The `modules/`
directory is Google's vendored Cloud Foundation Fabric `agent-engine` module,
included as-is so the deployment runs on Terraform 1.5.7.

## What it deploys

- **Endor AURI Agent on Agent Engine** — the actual workload (managed, autoscaled).
  Uses `google-adk`, reads the Endor credential from Secret Manager at runtime.
- **A placeholder compute instance** — required by the current Marketplace
  VM-listing validation. The agent does **not** run on it; it is small and idle
  (`e2-standard-2` by default). Do not oversize it.

## Prerequisites (in the customer project)

1. Enable `aiplatform.googleapis.com` and `secretmanager.googleapis.com`.
2. Create two Secret Manager secrets holding the Endor API credential, e.g.:
   ```bash
   printf '%s' "$ENDOR_KEY"    | gcloud secrets create endor-oss-api-key    --data-file=- --project "$PROJECT"
   printf '%s' "$ENDOR_SECRET" | gcloud secrets create endor-oss-api-secret --data-file=- --project "$PROJECT"
   ```
   Pass their names as `endor_api_key_secret_id` / `endor_api_secret_secret_id`.
   The credential value never enters Terraform state.

## Package the agent source (before terraform)

`package_agent.py` bundles the agent (`endor_oss`) and the shared core
(`service`) into `assets/source.tar.gz` and writes `agent_config.auto.tfvars`:

```bash
python3 package_agent.py
```

## Test the deployment in your own project first

Google's validation requires a working deploy. Verify before zipping:

```bash
terraform init
terraform apply \
  -var project_id="$PROJECT" \
  -var goog_cm_deployment_name="endor-auri-test" \
  -var endor_api_key_secret_id="endor-oss-api-key" \
  -var endor_api_secret_secret_id="endor-oss-api-secret"
```

Then query the resulting Agent Engine resource (see `../../adk/query_agent_engine.py`).

## Build the Marketplace zip

Include `modules/` and the packaged assets:

```bash
zip -r endor-auri-agent.zip \
  main.tf variables.tf outputs.tf \
  metadata.yaml metadata.display.yaml \
  marketplace_test.tfvars agent_config.auto.tfvars \
  README.md assets/source.tar.gz modules/
```

Upload the zip as the **VM listing** product in the Producer Portal, set the
service-account configuration, run validations, test deploy, and publish. Pair it
with the public **AI Agent as a Service** listing (pricing + private offers) per
the onboarding deck.

## Files

| File | Purpose |
|---|---|
| `main.tf` | Agent Engine deployment + placeholder compute instance |
| `variables.tf` | Inputs (project, region, Endor secret IDs, machine_type, …) |
| `outputs.tf` | Agent Engine id/name/region + instance info |
| `metadata.yaml` | Marketplace technical metadata (variables/outputs) |
| `metadata.display.yaml` | Marketplace UI for the input form |
| `marketplace_test.tfvars` | Sample test values |
| `package_agent.py` | Builds `assets/source.tar.gz` + `agent_config.auto.tfvars` |
| `modules/agent-engine/` | Vendored Google CFF agent-engine module |

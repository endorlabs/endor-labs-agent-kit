# Endor AURI for Developers — VM-installer bundle

A Marketplace **VM listing** whose VM acts as a one-shot **installer**: on boot it
deploys the agent to **Cloud Run** (HTTPS automatically) and **registers it in
Gemini Enterprise**. This satisfies "the VM deploys and registers the agent" while
the agent runs on Cloud Run — so no custom domain, DNS, or load balancer is needed.

## What it creates
- An **installer service account** (the VM runs as this) with `run.admin`,
  `discoveryengine.admin`, and `serviceAccountUser` on the runtime SA.
- A **runtime service account** for Cloud Run (least privilege: reads the two secrets).
- The two **Endor credential secrets** (created with a placeholder so the deploy
  succeeds before a real key exists — see below).
- The **installer VM**, whose `install.sh` runs `gcloud run deploy` + GE registration.

## The Endor credential — available now, real key added after
The bundle **creates** `endor-oss-api-key` / `endor-oss-api-secret` with a
**placeholder** value, so Cloud Run mounts them and the agent deploys + registers
immediately. Until a real key is set, agent queries return
*"Endor rejected the service credentials"* — but the agent is live and registered.

Add the real key **after** registration, then restart the service:
```bash
P=<project>
printf '%s' 'REAL_ENDOR_KEY'    | gcloud secrets versions add endor-oss-api-key    --data-file=- --project=$P
printf '%s' 'REAL_ENDOR_SECRET' | gcloud secrets versions add endor-oss-api-secret --data-file=- --project=$P
gcloud run services update <deployment>-a2ui --region=<region> --project=$P --update-env-vars=RESTART_TS=$(date +%s)
```
(You can also seed a real key at deploy with `-var endor_api_key=… -var endor_api_secret=…`.)

## Gemini Enterprise registration
Set `-var ge_engine_id="projects/<num>/locations/global/collections/default_collection/engines/<engine>"`
and the installer registers the agent automatically (idempotent — skips if it
already exists). Leave it empty to register manually with the Cloud Run
`…/.well-known/agent-card.json`.

## Deployment service-account roles (Producer Portal "Required Roles")
Because the deployment grants the installer SA its roles, it needs **Project IAM
Admin** in addition to the usual set:

- `roles/config.agent` — Cloud Infrastructure Manager agent
- `roles/compute.admin` — Compute Admin (the VM)
- `roles/iam.serviceAccountAdmin` — Service Account Admin (create the 2 SAs)
- `roles/iam.serviceAccountUser` — Service Account User (attach installer SA to the VM)
- `roles/resourcemanager.projectIamAdmin` — **Project IAM Admin** (grant the installer SA `run.admin`/`discoveryengine.admin`)
- `roles/secretmanager.admin` — Secret Manager Admin (create the secrets + grant the runtime SA)

> **Cloud Run Admin** and **Discovery Engine Admin** are held by the **installer SA**
> (granted by this Terraform), NOT by the deployment SA.

## APIs to enable
`compute.googleapis.com`, `run.googleapis.com`, `secretmanager.googleapis.com`,
`discoveryengine.googleapis.com`, `iam.googleapis.com`, `config.googleapis.com`.

## Verify
`terraform output cloud_run_service_name`, then find its HTTPS URL:
`gcloud run services describe <name> --region <region> --format='value(status.url)'`
and `curl <url>/.well-known/agent-card.json`. Watch progress via the VM's
`/var/log/endor-auri-install.log` (see the `installer_log_hint` output).

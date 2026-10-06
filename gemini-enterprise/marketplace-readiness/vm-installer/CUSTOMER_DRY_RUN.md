# Customer dry run — Endor AURI for Developers on Gemini Enterprise

A faithful, **manual** walkthrough of what a customer does to stand up the agent in
their own GCP project. You run every step yourself (API or UI); nothing is auto-driven.

## Ground rules / honesty notes
The published Marketplace listing isn't live yet, so two things Marketplace
normally provides are stood up here as **explicit stand-ins** (flagged 🟡). Everything
else is exactly what a real customer does.

- 🟡 **Image delivery** — GA Marketplace mirrors the container image to a Google
  registry entitled to the customer. Here we instead **build the image into the
  deploy project's own Artifact Registry** (Phase 1). Same end state: the deploy
  pulls a same-project image.
- 🟡 **VM boot image** — GA uses the Marketplace-licensed VM image. Here we use
  **public `debian-12`** (the installer only needs a plain Linux box).
- ✅ Everything else — Infra Manager deploy, deployment service account + roles,
  API enablement, secrets, GE registration, user grant, test — is the real flow.

## Inputs (fill these once, then the commands below use them)
```bash
export PROJECT=<your-project-id>
export PROJECT_NUM=<your-project-number>
export REGION=us-central1
export DEPLOYMENT=endor-auri                 # any name you choose; resources are named <DEPLOYMENT>-*
export GE_ENGINE=projects/$PROJECT_NUM/locations/global/collections/default_collection/engines/<your-ge-engine-id>
export BUNDLE_DIR=<path-to>/marketplace-readiness/vm-installer
# IMAGE_DIGEST is produced in Phase 1; export it there before Phase 4.
```

---

## Phase 0 — Prerequisites
- A GCP project with **billing enabled**.
- A **Gemini Enterprise app** provisioned (gives you the engine id for `GE_ENGINE`).
- An account that can create a deployment SA and grant it roles.

---

## Phase 1 — 🟡 Make the image available (Endor/Marketplace's job; stand-in)
Build the agent image from the committed source into the deploy project's Artifact
Registry via Cloud Build (policy-allowed; no `docker push`).

```bash
gcloud services enable artifactregistry.googleapis.com cloudbuild.googleapis.com --project=$PROJECT
```
> New projects run Cloud Build as `<PROJECT_NUM>-compute@developer.gserviceaccount.com`;
> grant it `roles/cloudbuild.builds.builder` if the build 403s on the source bucket.

```bash
cd $BUNDLE_DIR/../.. && PROJECT=$PROJECT REGION=$REGION REPO=endor-agents TAG=v1 ./marketplace-readiness/deploy/build_and_push_image.sh
```

The script creates the `endor-agents` repo, builds from the committed ref, and
prints a **pinned `@sha256:` digest**. Export it for Phase 4:
```bash
export IMAGE_DIGEST=$REGION-docker.pkg.dev/$PROJECT/endor-agents/oss-a2ui@sha256:<digest-from-above>
```

---

## Phase 2 — Enable the one pre-deploy API (Infra Manager)
Everything else is auto-enabled by the deployment package. Infra Manager runs the
deploy itself, so it must be on first.

```bash
gcloud services enable config.googleapis.com --project=$PROJECT
```

---

## Phase 3 — Create the deployment service account + grant its roles
Infra Manager runs the Terraform **as** this SA, so it needs the roles to create the
resources (and to grant the installer SA its roles).

```bash
gcloud iam service-accounts create auri-deployer --project=$PROJECT --display-name="Endor AURI Marketplace deployer (Infra Manager)"
```

```bash
SA="auri-deployer@$PROJECT.iam.gserviceaccount.com"; for R in roles/config.agent roles/compute.admin roles/iam.serviceAccountAdmin roles/iam.serviceAccountUser roles/resourcemanager.projectIamAdmin roles/secretmanager.admin roles/serviceusage.serviceUsageAdmin roles/storage.objectViewer; do gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role="$R" --condition=None >/dev/null && echo "granted $R"; done
```

> Why each role: `config.agent` (Infra Manager runs as it), `compute.admin` (the VM),
> `iam.serviceAccountAdmin` (create the installer/runtime SAs), `iam.serviceAccountUser`
> (attach installer SA to the VM), `resourcemanager.projectIamAdmin` (grant the installer
> SA run/discoveryengine/artifactregistry roles), `secretmanager.admin` (create the two
> secrets + grant the runtime SA), `serviceusage.serviceUsageAdmin` (enable the rest of
> the APIs on a vanilla project), `storage.objectViewer` (fetch the `--local-source`
> bundle from the Infra Manager staging bucket).

---

## Phase 4 — Deploy via Cloud Infrastructure Manager
This is how Marketplace runs the package. Make sure your active gcloud project is the
deploy project (`gcloud config set project $PROJECT`) so `--local-source` stages into
the right bucket.

```bash
gcloud infra-manager deployments apply projects/$PROJECT/locations/$REGION/deployments/$DEPLOYMENT --service-account=projects/$PROJECT/serviceAccounts/auri-deployer@$PROJECT.iam.gserviceaccount.com --local-source=$BUNDLE_DIR --input-values=project_id=$PROJECT,goog_cm_deployment_name=$DEPLOYMENT,region=$REGION,container_image=$IMAGE_DIGEST,source_image=projects/debian-cloud/global/images/family/debian-12,ge_engine_id=$GE_ENGINE --labels=goog-cm-deployment=$DEPLOYMENT
```

Watch it reach `ACTIVE`:
```bash
gcloud infra-manager deployments describe projects/$PROJECT/locations/$REGION/deployments/$DEPLOYMENT --format='value(state,latestRevision)'
```

---

## Phase 5 — Watch the installer do its job
The VM boots, deploys the agent to Cloud Run, and registers it in GE. Watch:
```bash
gcloud compute instances get-serial-port-output $DEPLOYMENT-vm --zone=$REGION-a --project=$PROJECT 2>/dev/null | grep endor-auri
```
Then confirm the Cloud Run service exists and get its URL:
```bash
gcloud run services describe $DEPLOYMENT-a2ui --region=$REGION --project=$PROJECT --format='value(status.url)'
```

---

## Phase 6 — Add the real Endor API key (customer step)
The deploy seeds **placeholder** credentials so it registers immediately; until a
real key is set, queries return "Endor rejected the service credentials."

```bash
printf '%s' 'YOUR_ENDOR_API_KEY'    | gcloud secrets versions add endor-oss-api-key    --data-file=- --project=$PROJECT
printf '%s' 'YOUR_ENDOR_API_SECRET' | gcloud secrets versions add endor-oss-api-secret --data-file=- --project=$PROJECT
gcloud run services update $DEPLOYMENT-a2ui --region=$REGION --project=$PROJECT --update-env-vars=RESTART_TS=$(date +%s)
```

---

## Phase 7 — Grant users + test in the Gemini Enterprise UI
1. In the **Gemini Enterprise** console (your GE app), grant your user access to the
   agent **Endor AURI for Developers**.
2. Open the GE chat, pick the agent (logo + short description should render), and run
   the **Sample prompts** below.

---

## Sample prompts (demo/POV script)
The agent answers open-source vulnerability, package-risk, CVE, and safe-upgrade
questions from Endor's public OSS intelligence. Packages use purl form
(`mvn://group:artifact@version`, `npm://pkg@version`, `pypi://pkg@version`,
`go://module@version`).

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
- `Give me the Endor package risk for mvn://org.apache.logging.log4j:log4j-core@2.14.1`

**Safe-upgrade recommendation (should emit the interactive A2UI upgrade card)**
- `Is mvn://org.apache.logging.log4j:log4j-core@2.14.1 vulnerable? Recommend a safe upgrade.`
- `What version should I upgrade npm://lodash@4.17.20 to?`

---

## Phase 8 — Verify (optional, from CLI)
```bash
URL=$(gcloud run services describe $DEPLOYMENT-a2ui --region=$REGION --project=$PROJECT --format='value(status.url)')
curl -s "$URL/.well-known/agent-card.json" | head -c 300
```

---

## Phase 9 — Teardown (when done)
```bash
# 1) remove the GE agent registration (in the console, or via the Discovery Engine API)
# 2) destroy the deployment:
gcloud infra-manager deployments delete projects/$PROJECT/locations/$REGION/deployments/$DEPLOYMENT --quiet
# 3) the Cloud Run service is created imperatively by the installer, so delete it too:
gcloud run services delete $DEPLOYMENT-a2ui --region=$REGION --project=$PROJECT --quiet
# 4) optional: delete the built image + deployer SA
```

---

## Results (dry run on a vanilla GCP project) — ✅ PASSED
- ✅ Infra Manager + the deployment SA role set deployed **cleanly on a vanilla
  project** (API enablement, SA creation, secrets, VM all via the package).
- ✅ The installer's `gcloud run deploy` pulled the image with only same-project
  permissions (the AR-reader self-grant in the bundle) — no manual AR grant needed.
- ✅ GE registration landed with the **short description + rendered logo**
  (confirmed the GitHub raw PNG `icon.uri` renders in the GE UI — closes the icon issue).
- ✅ Real Endor data returned (log4j-core vulns + risk scores); only manual post-deploy
  steps were **adding the Endor key + granting users**, as documented.

### Findings folded into the docs
1. Image build needs the Cloud Build SA (`<PROJECT_NUM>-compute@developer`) to have
   `roles/cloudbuild.builds.builder` (see README).
2. Infra Manager `--local-source` needs the deploy SA to have
   `roles/storage.objectViewer`, and the active gcloud project must be the deploy
   project (else `--local-source` stages into the wrong bucket).
3. Minor UX polish (not a blocker): the package-risk answer surfaces raw internal
   field names (e.g. `pkg_version_stats...`) — candidate for cleaner formatting.

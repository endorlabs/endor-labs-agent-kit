#!/bin/bash
# Endor AURI VM installer.
# Rendered by Terraform (templatefile) before it reaches the VM: Terraform fills
# its own placeholders; shell variables are escaped for the template.
# On boot this VM: installs gcloud, deploys the agent to Cloud Run (HTTPS), and
# registers it in Gemini Enterprise. It then serves no traffic itself.
set -euxo pipefail
exec > >(tee /var/log/endor-auri-install.log) 2>&1
echo "[endor-auri] installer starting $(date -u)"
export DEBIAN_FRONTEND=noninteractive

md(){ curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/$${1}"; }
PROJECT=$(md "project/project-id")
TOKEN=$(md "instance/service-accounts/default/token" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 1. Ensure gcloud CLI is present (base image is Debian). Wait out boot-time apt.
if ! command -v gcloud >/dev/null 2>&1; then
  for _ in $(seq 1 60); do
    if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
       && ! fuser /var/lib/apt/lists/lock >/dev/null 2>&1 \
       && ! pgrep -x apt-get >/dev/null 2>&1 \
       && ! pgrep -x unattended-upgr >/dev/null 2>&1; then break; fi
    echo "[endor-auri] waiting for apt/dpkg..."; sleep 5
  done
  dpkg --configure -a || true
  apt-get update -y
  apt-get install -y -o DPkg::Lock::Timeout=300 apt-transport-https ca-certificates gnupg curl python3
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" > /etc/apt/sources.list.d/google-cloud-sdk.list
  apt-get update -y
  apt-get install -y -o DPkg::Lock::Timeout=300 google-cloud-cli
fi

# 2. Deploy the agent to Cloud Run (HTTPS automatic). Creds mount from Secret Manager
#    (placeholder values are fine here — the agent registers; add the real key later).
gcloud run deploy "${service_name}" \
  --image="${container_image}" \
  --region="${region}" --project="$${PROJECT}" \
  --service-account="${runtime_sa_email}" \
  --allow-unauthenticated --port=8080 --cpu=1 --memory=512Mi \
  --set-env-vars="OSS_ROUTER=${oss_router},OSS_CLIENT=rest,OSS_UI_PROTOCOL=a2ui,ENDOR_API_BASE_URL=${endor_api_base_url}" \
  --set-secrets="ENDOR_API_CREDENTIALS_KEY=${endor_api_key_secret_id}:latest,ENDOR_API_CREDENTIALS_SECRET=${endor_api_secret_secret_id}:latest" \
  --quiet

URL=$(gcloud run services describe "${service_name}" --region="${region}" --project="$${PROJECT}" --format='value(status.url)')
echo "[endor-auri] Cloud Run URL: $${URL}"

# 3. Register in Gemini Enterprise (idempotent) when a GE engine is provided.
if [ -n "${ge_engine_id}" ]; then
  CARD=$(curl -s "$${URL}/.well-known/agent-card.json")
  python3 - "$${TOKEN}" "${ge_engine_id}" "${agent_display_name}" "$${CARD}" "${agent_icon_b64}" <<'PYEOF'
import sys, json, urllib.request, urllib.error
token, engine, display, card, icon = sys.argv[1:6]
base = f"https://discoveryengine.googleapis.com/v1alpha/{engine}/assistants/default_assistant/agents"
def http(method, url, body=None):
    req = urllib.request.Request(url,
        data=(json.dumps(body).encode() if body else None),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method)
    return json.load(urllib.request.urlopen(req))
try:
    existing = http("GET", base).get("agents", [])
    if any(a.get("displayName") == display for a in existing):
        print("[endor-auri] agent already registered"); sys.exit()
    desc = json.loads(card).get("description", "")[:900]
    body = {"displayName": display, "description": desc,
            "a2aAgentDefinition": {"jsonAgentCard": card}}
    if icon:
        body["icon"] = {"content": icon}  # inline icon so GE renders it reliably
    r = http("POST", base, body)
    print("[endor-auri] registered:", r.get("name"))
except urllib.error.HTTPError as e:
    print("[endor-auri] register error", e.code, e.read().decode()[:300])
PYEOF
else
  echo "[endor-auri] no ge_engine_id set — skipping GE registration (register manually with $${URL}/.well-known/agent-card.json)"
fi
echo "[endor-auri] install complete"

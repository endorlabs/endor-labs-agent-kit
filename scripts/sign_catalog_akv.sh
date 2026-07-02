#!/usr/bin/env bash
# Sign catalog.json with the Azure Key Vault catalog-signing key (ECDSA-P256 / ES256)
# and emit a detached DER signature next to it.
#
# No private key is stored anywhere: CI authenticates to Azure via OIDC federation
# (azure/login) and the key never leaves the HSM. The Key Vault key + federation are
# provisioned under AI-418; this script runs only when CATALOG_SIGNING_ENABLED=true.
# See RELEASES.md.
set -euo pipefail

catalog="${1:-catalog.json}"
signature="${2:-catalog.json.sig}"
: "${CATALOG_SIGNING_VAULT:?set CATALOG_SIGNING_VAULT (Azure Key Vault name)}"
: "${CATALOG_SIGNING_KEY:?set CATALOG_SIGNING_KEY (Key Vault key name)}"

# AKV signs a precomputed digest; ES256 takes the SHA-256 digest as base64url (unpadded).
digest_b64url="$(openssl dgst -sha256 -binary "$catalog" | basenc --base64url | tr -d '=')"

raw_b64url="$(az keyvault key sign \
  --vault-name "$CATALOG_SIGNING_VAULT" \
  --name "$CATALOG_SIGNING_KEY" \
  --algorithm ES256 \
  --digest "$digest_b64url" \
  --query 'result' -o tsv)"

# AKV returns a raw P1363 (r||s) signature; convert to DER for the pinned-public-key
# verifiers (openssl dgst -verify, apiserver ecdsa.VerifyASN1).
python - "$raw_b64url" "$signature" <<'PY'
import base64
import sys

from endor_agent_kit.catalog_signing import der_from_raw_p1363

raw_b64url, out_path = sys.argv[1], sys.argv[2]
padding = "=" * (-len(raw_b64url) % 4)
raw = base64.urlsafe_b64decode(raw_b64url + padding)
with open(out_path, "wb") as handle:
    handle.write(der_from_raw_p1363(raw))
PY

echo "wrote detached signature: $signature"

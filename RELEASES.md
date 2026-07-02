# Catalog releases and signing

This repo publishes a signed `catalog.json` that apiserver (AI-351) fetches,
verifies, and serves as the Endor agent catalog. `catalog.json` follows the
`internal.endor.ai/endor/v1` `EndorAgent` wire shape; it is a generated, committed
artifact (like `manifest.json`) and is covered by the CI drift check.

## Cutting a release

The catalog ships on its own cadence, independent of the Python package version.

1. Make sure `main` is green (validate, tests, drift, guardrails, id-stability).
2. Tag the release `agents-v<semver>` (e.g. `agents-v1.0.0`) and push the tag.
3. `.github/workflows/agent-kit-release.yml` runs on the tag and:
   - re-runs the full gate (validate every recipe, tests, regenerate + drift-check
     `catalog.json`/`manifest.json`, guardrails, provenance);
   - stamps `catalog_version` = the tag into `catalog.json`
     (`endor-agent-kit stamp-catalog-version`);
   - signs `catalog.json` (gated -- see below);
   - verifies the signature against the pinned public key and aborts on failure;
   - creates the GitHub Release at the tag, attaching `catalog.json`, the detached
     `catalog.json.sig`, and the public key (plus the tag's auto source archive).

`catalog_version` is only present in the released artifact; the committed
`catalog.json` omits it because no tag exists at commit time.

## Signing

- **Algorithm:** ECDSA-P256 (ES256). Chosen so apiserver can reuse the existing
  `pkg/artifacts` ECDSA-P256 verification instead of new crypto. (The monorepo's
  general `artifacts/verify.go` also uses ECDSA-P256; note this catalog path uses a
  dedicated key, not the EV Authenticode cert used for Windows binaries.)
- **Key custody:** HSM-backed in Azure Key Vault. The private key never leaves the
  HSM and is **never stored in GitHub**. CI authenticates to Azure via OIDC
  federation (`azure/login`, `id-token: write`) -- the same pattern used to sign
  endorctl binaries today (`doc/src/infrastructure/code-signing.md`). This is a
  deliberate choice over a GitHub Actions secret holding a raw key.
- **Signature form:** a detached signature over the raw `catalog.json` bytes,
  written to `catalog.json.sig` in ASN.1 DER. Azure Key Vault returns a raw P1363
  (`r||s`) signature; `scripts/sign_catalog_akv.sh` converts it to DER so the
  pinned-public-key verifiers (`openssl dgst -verify`, Go `ecdsa.VerifyASN1`)
  accept it.

### Verification

Offline, against the pinned public key -- this is exactly what apiserver mirrors:

```bash
endor-agent-kit verify-catalog-signature \
  --catalog catalog.json \
  --signature catalog.json.sig \
  --public-key keys/catalog-signing-public-key.pem
```

## Infrastructure prerequisite (AI-418)

Signing is **gated** behind the `CATALOG_SIGNING_ENABLED` repository variable and
stays off until the Azure infrastructure is provisioned under
[AI-418](https://endorlabs.atlassian.net/browse/AI-418):

1. An ECDSA-P256 signing key in Azure Key Vault (reuse an existing vault via the
   `endorlabs-azure-keyvault` Terraform module; `sign` + `verify` only).
2. GitHub OIDC federation for `endorlabs/endor-labs-agent-kit` -- a federated
   credential granting the release job `sign` on that key, plus the repository
   variables below.
3. The exported ES256 **public** key committed to
   `keys/catalog-signing-public-key.pem` (a CODEOWNERS-reviewed change) and shipped
   to apiserver for pinning.

Until then, the release job **refuses to publish**: tagging `agents-v*` while
`CATALOG_SIGNING_ENABLED` is not `true` fails the workflow rather than shipping an
unsigned `catalog.json` to a release. The catalog is still committed and
drift-gated on every PR; there is just no signed release to cut yet. The release
job also verifies the tagged commit is contained in `main` before building, so a
tag on an unreviewed commit cannot produce a release.

| Repository variable | Purpose |
| --- | --- |
| `CATALOG_SIGNING_ENABLED=true` | Enables the Azure Key Vault signing + verification steps. |
| `CATALOG_SIGNING_AZURE_CLIENT_ID` / `CATALOG_SIGNING_AZURE_TENANT_ID` / `CATALOG_SIGNING_AZURE_SUBSCRIPTION_ID` | OIDC federation identifiers (not a signing key). |
| `CATALOG_SIGNING_VAULT` | Azure Key Vault name. |
| `CATALOG_SIGNING_KEY` | Key Vault key name. |

## Key rotation

The public key is pinned in consumers (apiserver, endorctl), so rotation is a
coordinated change:

1. Provision the new ECDSA-P256 key in Azure Key Vault and export its public key.
2. Open a CODEOWNERS-reviewed PR replacing `keys/catalog-signing-public-key.pem`
   and pointing `CATALOG_SIGNING_KEY` at the new key.
3. Ship the new public key to apiserver + endorctl and release them so consumers
   accept signatures from the new key before it signs a catalog.
4. Cut the next `agents-v<semver>` release; verify the new signature end to end.
5. Retire the old key in Key Vault once no consumer pins it.

Because consumers only ever know the **public** key, migrating the private key's
custody (e.g. to a different vault) is a no-contract-change swap.

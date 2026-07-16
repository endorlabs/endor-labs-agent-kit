# Catalog releases and signing

This repo publishes a signed `catalog.json` -- the Endor agent catalog, following
the `internal.endor.ai/endor/v1` `EndorAgent` wire shape. It is a generated,
committed artifact (like `manifest.json`) and is covered by the CI drift check.
Each GitHub Release attaches `catalog.json`, a detached `catalog.json.sig`, and the
public verification key.

## Cutting a release

The catalog ships on its own cadence, independent of the Python package version.

1. Make sure `main` is green (validate, tests, drift, guardrails, id-stability).
2. Tag the release `agents-v<semver>` (e.g. `agents-v1.0.0`) and push the tag.
3. `.github/workflows/agent-kit-release.yml` runs on the tag and:
   - re-runs the full gate (validate every recipe, tests, regenerate + drift-check
     `catalog.json`/`manifest.json`, guardrails, provenance);
   - stamps `catalog_version` = the tag into `catalog.json`;
   - signs `catalog.json` and verifies the signature against the pinned public key,
     aborting on failure;
   - creates the GitHub Release at the tag with the artifacts above.

The release job refuses to publish an unsigned catalog, and only releases a commit
that has already merged to `main`.

`catalog_version` is only present in the released artifact; the committed
`catalog.json` omits it because no tag exists at commit time.

## Signing

- **Algorithm:** ECDSA P-256 (ES256).
- **Key custody:** HSM-backed in Azure Key Vault. The private key never leaves the
  HSM and is never stored in GitHub; CI signs via short-lived OIDC-federated
  access. Only the public verification key is committed, at
  `keys/catalog-signing-public-key.pem`.
- **Signature form:** a detached signature over the raw `catalog.json` bytes,
  written to `catalog.json.sig` in ASN.1 DER.

## Verifying a released catalog

```bash
endor-agent-kit verify-catalog-signature \
  --catalog catalog.json \
  --signature catalog.json.sig \
  --public-key keys/catalog-signing-public-key.pem
```

Or with OpenSSL:

```bash
openssl dgst -sha256 -verify keys/catalog-signing-public-key.pem \
  -signature catalog.json.sig catalog.json
```

## Key rotation

The public key is pinned by consumers, so rotation is coordinated: provision a new
key, ship its public half to consumers and release them, then cut the next
`agents-v<semver>` release signed by the new key and retire the old one. Because
consumers only ever know the public key, moving the private key's custody is a
no-contract-change swap.

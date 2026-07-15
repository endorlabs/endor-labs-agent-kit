# Catalog signing keys

This directory holds the **public** key used to verify the signed `catalog.json`
release artifact. No private key material lives here or anywhere in the repo --
signing is HSM-backed via Azure Key Vault over OIDC-federated CI (see
`RELEASES.md`).

## `catalog-signing-public-key.pem`

The ECDSA-P256 (ES256) **public** key exported from the HSM-backed catalog-signing
key in Azure Key Vault. The release workflow verifies each signed `catalog.json`
against this pinned key before publishing.

- This is only the **public** half; no private key material lives here or
  anywhere in the repo. The private key never leaves the Key Vault HSM and is
  used only via OIDC-federated CI (see `RELEASES.md`).
- Committing it is a security-critical, CODEOWNERS-reviewed action.

Consumers pin this public key to verify the catalog. Rotation is documented in
`RELEASES.md`.

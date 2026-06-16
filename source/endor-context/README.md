# Endor Context Provenance

This directory records the Endor Labs upstream API and documentation context
used by the Agent Kit maintainers. It is a release and CI freshness gate, not
runtime context that agents fetch while helping a user.

`provenance.json` records:

- the public Endor OpenAPI URL and SHA-256 digest
- the public `/meta/version` response fields used as a warning-only version
  signal
- selected canonical Endor documentation URLs that generated prompts and
  release docs depend on

Run the local shape check without network access:

```bash
endor-agent-kit verify-endor-context
```

Run the upstream freshness check before release or after Endor API/doc changes:

```bash
endor-agent-kit verify-endor-context --upstream
```

When upstream Endor changes are intentional and the agent guidance still reads
correctly, refresh the committed provenance:

```bash
endor-agent-kit refresh-endor-context
endor-agent-kit verify-endor-context --upstream
python -m pytest -q tests/test_endor_context.py
```

The scheduled `Refresh Endor context` workflow reports drift and validates the
refreshed file in the runner. It does not push a branch or open a PR; maintainers
refresh locally and send the update through the normal signed PR process.

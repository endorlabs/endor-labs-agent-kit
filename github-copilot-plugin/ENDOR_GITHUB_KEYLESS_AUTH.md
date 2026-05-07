# Endor GitHub Keyless Auth For Copilot Agents

GitHub Copilot cloud agent and AgentHQ run in a GitHub Actions-backed
environment. Endor Labs can authenticate that workload with GitHub Actions OIDC
when `endorctl` is started with GitHub action token support enabled.

## Endor Labs Setup

In Endor Labs, create an auth policy:

- Identity provider: `GitHub Action OIDC`
- Permission: the least-privileged role that can read the tenant data needed by
  the agent; `Code Scanner` is the baseline role Endor documents for GitHub
  Actions keyless authentication
- Claim key: `user`
- Claim value: the GitHub organization or owner that contains the target
  repository

## Target Repository Setup

In the GitHub repository where Copilot cloud agent will run, create the
`copilot` environment and add:

- Environment variable: `COPILOT_MCP_ENDOR_NAMESPACE`
- Optional environment variable: `COPILOT_MCP_ENDOR_API`

Then add `.github/workflows/copilot-setup-steps.yml` to the target repository:

```yaml
name: "Copilot Setup Steps"

on:
  workflow_dispatch:
  push:
    paths:
      - .github/workflows/copilot-setup-steps.yml
  pull_request:
    paths:
      - .github/workflows/copilot-setup-steps.yml

jobs:
  copilot-setup-steps:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    environment: copilot
    steps:
      - name: Configure Endor keyless auth
        run: |
          echo "ENDOR_GITHUB_ACTION_TOKEN_ENABLE=true" >> "$GITHUB_ENV"
          echo "ENDOR_NAMESPACE=${{ vars.COPILOT_MCP_ENDOR_NAMESPACE }}" >> "$GITHUB_ENV"
          echo "ENDOR_API=${{ vars.COPILOT_MCP_ENDOR_API || 'https://api.endorlabs.com' }}" >> "$GITHUB_ENV"
```

## Plugin MCP Configuration

Enterprise GitHub Copilot plugin agents in this kit pass the same values into
their local Endor MCP server:

```yaml
env:
  ENDOR_GITHUB_ACTION_TOKEN_ENABLE: "true"
  ENDOR_NAMESPACE: $COPILOT_MCP_ENDOR_NAMESPACE
  ENDOR_API: ${COPILOT_MCP_ENDOR_API:-https://api.endorlabs.com}
```

This path intentionally uses Endor's GitHub Actions OIDC support rather than
long-lived Endor API keys. It does not add an AgentHQ MCP `oidc` block, because
`endorctl` performs the GitHub Actions OIDC exchange with Endor directly when
`ENDOR_GITHUB_ACTION_TOKEN_ENABLE=true`.

## Verification

Start a Copilot cloud agent session and expand the setup logs:

1. `Copilot Setup Steps` should run before MCP startup.
2. The `endor-cli-tools` MCP server should start.
3. Tenant lookups should succeed without Endor API key secrets.

If Endor reports an auth failure, confirm the target repository owner matches
the Endor auth policy claim and that the setup job has `id-token: write`.

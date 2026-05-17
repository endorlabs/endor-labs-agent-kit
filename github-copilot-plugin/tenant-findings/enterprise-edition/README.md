# Endor Labs Tenant Findings Enterprise Edition

Use this agent when the user asks about findings inside an Endor Labs tenant:
reachable findings, project findings, severity summaries, fix availability,
vulnerable packages, or which imported project findings should be prioritized.
Enterprise Edition uses GitHub keyless authentication with read-only Endor MCP
and endorctl API lookups.

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-tenant-findings-enterprise`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package also enables Copilot's `execute` tool for the documented read-only Endor lookups.
- The Endor MCP server is configured for GitHub Actions keyless auth. The target repository still needs the `copilot` environment and setup workflow described in `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`.
- AgentHQ app wrapping and any OIDC token exchange endpoints are configured outside this generated package.

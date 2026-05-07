# Endor Labs Tenant Findings Enterprise Edition

Use this agent when the user asks about findings that already exist inside an
Endor Labs tenant, including reachable findings for an imported project.
Examples: "What reachable findings are in this project?", "List high severity
findings for project app-java-demo", or "Summarize the reachable Endor findings
for this repository."

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-tenant-findings-enterprise`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package enables Copilot's `execute` tool only for documented read-only
  Endor lookups.
- In GitHub Copilot cloud agent or AgentHQ, the target repository must be set up
  for Endor GitHub Actions keyless authentication. See
  `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`.

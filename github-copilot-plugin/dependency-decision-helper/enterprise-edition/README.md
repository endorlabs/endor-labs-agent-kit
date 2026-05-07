# Dependency Decision Helper Enterprise Edition

Use this agent when the user asks whether to add, upgrade, or use a specific
package version. Examples: "Is lodash 4.17.20 safe?", "Should I use requests
2.28.0?", "Check log4j-core 2.14.1 before I add it." Returns a dependency
verdict with evidence, conditions, alternatives, and any data gaps.

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-dependency-decision-helper-enterprise`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package also enables Copilot's `execute` tool for the documented read-only Endor lookups.
- The Endor MCP server is configured for GitHub Actions keyless auth. The target repository still needs the `copilot` environment and setup workflow described in `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`.

# Dependency Decision Helper Developer Edition

Use this agent when the user asks whether to add, upgrade, or use a specific
package version. Examples: "Is lodash 4.17.20 safe?", "Should I use requests
2.28.0?", "Check log4j-core 2.14.1 before I add it." Returns a dependency
verdict with evidence, conditions, alternatives, and any data gaps.

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-dependency-decision-helper-developer`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package enables only the Endor MCP tools required by the agent.
- AgentHQ app wrapping and any OIDC token exchange endpoints are configured outside this generated package.

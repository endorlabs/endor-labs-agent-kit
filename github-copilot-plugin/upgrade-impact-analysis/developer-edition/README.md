# Endor Labs Upgrade Impact Analysis Developer Edition

Use this agent when the user asks for Endor Labs Upgrade Impact Analysis:
safe upgrade paths, upgrade risk, findings fixed or introduced, Code Impact
Analysis, breaking changes, manifest targeting, or whether a dependency
upgrade should happen now. Enterprise Edition mirrors AURI's read-only UIA
workflow by querying precomputed VersionUpgrade resources. Developer Edition
is a lighter MCP-only explicit package-version comparator.

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-upgrade-impact-analysis-developer`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package enables only the Endor MCP tools required by the agent.
- AgentHQ app wrapping and any OIDC token exchange endpoints are configured outside this generated package.

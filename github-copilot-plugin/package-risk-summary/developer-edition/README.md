# Endor Labs Package Risk Summary Developer Edition

Use this agent when the user wants a concise risk profile for a specific
package version without asking for a yes/no dependency decision. Examples:
"Summarize npm lodash 4.17.20 risk", "Give me the risk picture for
log4j-core 2.14.1", "What should I know about this package version before I
review it?" Returns an evidence-backed package risk summary with
vulnerabilities, malware or typosquat signals, package scores, license notes,
recommended next checks, and any data gaps.

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-package-risk-summary-developer`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package enables only the Endor MCP tools required by the agent.
- AgentHQ app wrapping and any OIDC token exchange endpoints are configured outside this generated package.

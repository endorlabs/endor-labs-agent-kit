# Dependency Decision Helper Developer Edition

Use this agent when the user asks whether to add, upgrade, or use a specific
package version. Examples: "Is lodash 4.17.20 safe?", "Should I use requests
2.28.0?", "Check log4j-core 2.14.1 before I add it." Returns a dependency
verdict with evidence, conditions, alternatives, and any data gaps.

## Install

Update placeholders in `agent.yaml`, `environment.yaml`, and
`session-template.yaml`, then create the agent and environment in
Claude Managed Agents.

```bash
ant beta:agents create < agent.yaml
ant beta:environments create < environment.yaml
```

Use `session-template.yaml` as the starting point for session creation after
you have the created agent ID, environment ID, and any required vault IDs.

## Requirements

- Anthropic Console or `ant` CLI access to Claude Managed Agents.
- A remote Endor MCP server URL configured in agent.yaml.
- An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.
- No pre-built Bash or filesystem tools are enabled for this edition.

## Example User Message

```text
Assess npm lodash version 4.17.20.
```

## Notes

- This edition uses the Managed Agents MCP connector only.
- The generated `agent.yaml` intentionally uses a placeholder MCP URL that must be replaced.
- Unavailable MCP, vault, auth, or account-tier signals are reported in data_gaps.

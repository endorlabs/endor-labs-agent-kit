# Endor Labs Upgrade Impact Analysis Developer Edition

Use this agent when the user asks for Endor Labs Upgrade Impact Analysis:
safe upgrade paths, upgrade risk, findings fixed or introduced, Code Impact
Analysis, breaking changes, manifest targeting, or whether a dependency
upgrade should happen now. The agent can use Endor MCP evidence and, when
available, read-only VersionUpgrade context for AURI-style UIA signals.

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
Assess upgrading npm lodash from 4.17.20 to 4.17.21.
```

## Notes

- This edition uses the Managed Agents MCP connector only.
- The generated `agent.yaml` intentionally uses a placeholder MCP URL that must be replaced.
- Unavailable MCP, vault, auth, or account-tier signals are reported in data_gaps.

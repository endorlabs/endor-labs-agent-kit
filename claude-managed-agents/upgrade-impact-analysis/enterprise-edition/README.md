# Endor Labs Upgrade Impact Analysis Enterprise Edition

Use this agent when the user asks for Endor Labs Upgrade Impact Analysis:
safe upgrade paths, upgrade risk, findings fixed or introduced, Code Impact
Analysis, breaking changes, manifest targeting, or whether a dependency
upgrade should happen now. Enterprise Edition mirrors AURI's read-only UIA
workflow by querying precomputed VersionUpgrade resources. Developer Edition
is a lighter MCP-only explicit package-version comparator.

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
- An environment that can install and authenticate endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example User Message

```text
Show the safest upgrade path for project <project_uuid> package lodash, including CIA, findings fixed, manifest files, and breaking changes.
```

## Notes

- This edition uses MCP first, then read-only endorctl api lookups for richer signals.
- The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.
- Bash use remains limited by prompt to the documented Endor lookup commands.

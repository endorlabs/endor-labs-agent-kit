# Endor Labs Upgrade Impact Analysis Enterprise Edition

Use this agent when the user asks whether a dependency upgrade is safer,
urgent, risky, or worth deferring. Examples: "Should I upgrade lodash from
4.17.20 to 4.17.21?", "Compare log4j-core 2.14.1 and 2.17.1", "Is this
package upgrade worth doing now?" Returns an evidence-backed upgrade
recommendation with risk delta, reasons, next checks, and any data gaps.

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
Assess upgrading npm lodash from 4.17.20 to 4.17.21.
```

## Notes

- This edition uses MCP first, then read-only endorctl api lookups for richer signals.
- The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.
- Bash use remains limited by prompt to the documented Endor lookup commands.

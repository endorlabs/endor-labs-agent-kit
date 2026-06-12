# Findings Browser

Use this agent when the user wants to browse, filter, summarize, or inspect
existing Endor Labs findings. Findings Browser uses read-only Endor evidence
to list matching findings, explain applied filters, surface pagination and
truncation limits, and identify data gaps without starting new scans or
performing remediation actions.

## Start Here

This is the Claude Managed Agents generated agent for `findings-browser`.

| Reader | First move |
| --- | --- |
| Human operator | Update generated YAML placeholders, then create the managed agent and environment. Then use the example prompt below: Help me use this Endor Labs agent. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/findings-browser/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

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
- An environment that can install and authenticate endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example User Message

```text
Help me use this Endor Labs agent.
```

## Architecture

![Findings Browser architecture](architecture.svg)

This diagram shows the generated agent contract, host responsibilities, and external systems required at runtime.

## Notes

- This agent uses read-only endorctl api lookups and does not require Endor MCP.
- The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.
- Bash use remains limited by prompt to the documented Endor lookup commands.

# Dependency Reviewer

Use this agent when the user wants an exact package decision, a package risk
summary, or a repository dependency review. It selects one bounded task
profile, gathers only the evidence that profile needs, and returns a
read-only decision or review with explicit data gaps.

## Start Here

This is the Claude Managed Agents generated agent for `dependency-reviewer`.

| Reader | First move |
| --- | --- |
| Human operator | Update generated YAML placeholders, then create the managed agent and environment. Then use the example prompt below: Summarize the risk of npm lodash version 4.17.20 with the package-risk profile. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/dependency-reviewer/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

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
Summarize the risk of npm lodash version 4.17.20 with the package-risk profile.
```

## Architecture

![Dependency Reviewer architecture](architecture.svg)

This diagram shows the generated agent contract, host responsibilities, and external systems required at runtime.

## Notes

- This agent uses MCP first, then read-only `endorctl agent api --agent-id dependency-reviewer` lookups for richer signals.
- The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.
- Bash use remains limited by prompt to the documented Endor lookup commands.

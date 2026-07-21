# Findings Browser

Use this agent when the user wants to browse, filter, summarize, or inspect
existing Endor Labs findings. Findings Browser uses read-only Endor evidence
to list matching findings, explain applied filters, surface pagination and
truncation limits, and identify data gaps without starting new scans or
performing remediation actions.

## Start Here

This is the Claude Code generated agent for `findings-browser`.

| Reader | First move |
| --- | --- |
| Human operator | Copy the generated subagent into `.claude/agents/` and restart Claude Code if needed. Then use the example prompt below: @agent-findings-browser help |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/findings-browser/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy `findings-browser.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-findings-browser help
```

## Architecture

![Findings Browser architecture](architecture.svg)

This diagram shows the generated agent contract, host responsibilities, and external systems required at runtime.

## Notes

- This agent uses read-only `endorctl agent api --agent-id findings-browser` lookups and does not require Endor MCP.
- Bash use is limited by prompt to the documented Endor lookup commands.

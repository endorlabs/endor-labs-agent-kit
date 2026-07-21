# Remediation Planning

Preview safe remediation options without opening PRs.

## Start Here

This is the Claude Code generated agent for `remediation-planning`.

| Reader | First move |
| --- | --- |
| Human operator | Copy the generated subagent into `.claude/agents/` and restart Claude Code if needed. Then use the example prompt below: @agent-remediation-planning preview remediation options for this repository |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/remediation-planning/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy `remediation-planning.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-remediation-planning preview remediation options for this repository
```

## Architecture

![Remediation Planning architecture](architecture.svg)

This dry-run workflow resolves project or finding context, gathers Endor remediation evidence, and returns a plan only. It does not edit files, push branches, or open PRs/MRs.

## Notes

- This agent uses read-only `endorctl agent api --agent-id remediation-planning` lookups and does not require Endor MCP.
- Bash use is limited by prompt to the documented Endor lookup commands.

# Endor Labs Repository Dependency Reviewer

Use this agent inside a source repository when the user wants a read-only
dependency risk review based on local manifests. It inspects dependency files,
resolves exact package coordinates when possible, checks those coordinates
with Endor MCP tools, and reports risky dependencies, unresolved versions,
recommended next checks, and data gaps.

## Start Here

This is the Claude Code generated agent for `repository-dependency-reviewer`.

| Reader | First move |
| --- | --- |
| Human operator | Copy the generated subagent into `.claude/agents/` and restart Claude Code if needed. Then use the example prompt below: @agent-repository-dependency-reviewer help |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/repository-dependency-reviewer/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy `repository-dependency-reviewer.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor MCP access through the subagent's bundled MCP server config.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-repository-dependency-reviewer help
```

## Notes

- This agent uses MCP first, then read-only `endorctl agent api --agent-id repository-dependency-reviewer` lookups for richer signals.
- Bash use is limited by prompt to the documented Endor lookup commands.

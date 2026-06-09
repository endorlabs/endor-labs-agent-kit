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
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/repository-dependency-reviewer/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy `repository-dependency-reviewer.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor MCP access through the subagent's bundled MCP server config.
- Read-only access to dependency manifests in the target workspace.
- No shell access or authenticated endorctl setup is required for this agent.

## Example

```text
@agent-repository-dependency-reviewer help
```

## Notes

- This agent uses Endor MCP tools plus Claude Code read-only file inspection.
- It records unavailable non-MCP signals in data_gaps rather than fabricating evidence.

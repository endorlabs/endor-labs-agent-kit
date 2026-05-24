# Dependency Decision Helper

Use this agent when the user asks whether to add, upgrade, or use a specific
package version. Examples: "Is lodash 4.17.20 safe?", "Should I use requests
2.28.0?", "Check log4j-core 2.14.1 before I add it." Returns a dependency
verdict with evidence, conditions, alternatives, and any data gaps.

## Install

Copy `dependency-decision-helper.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor MCP access through the subagent's bundled MCP server config.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-dependency-decision-helper assess npm lodash version 4.17.20
```

## Notes

- This agent uses MCP first, then read-only endorctl api lookups for richer signals.
- Bash use is limited by prompt to the documented Endor lookup commands.

# Dependency Decision Helper Developer Edition

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
- No shell access or authenticated endorctl setup is required for this edition.

## Example

```text
@agent-dependency-decision-helper assess npm lodash version 4.17.20
```

## Notes

- This edition uses Endor MCP tools only.
- It records unavailable non-MCP signals in data_gaps rather than fabricating evidence.

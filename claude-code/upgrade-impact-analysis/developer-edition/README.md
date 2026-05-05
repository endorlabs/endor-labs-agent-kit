# Endor Labs Upgrade Impact Analysis Developer Edition

Use this agent when the user asks for Endor Labs Upgrade Impact Analysis:
safe upgrade paths, upgrade risk, findings fixed or introduced, Code Impact
Analysis, breaking changes, manifest targeting, or whether a dependency
upgrade should happen now. Enterprise Edition mirrors AURI's read-only UIA
workflow by querying precomputed VersionUpgrade resources. Developer Edition
is a lighter MCP-only explicit package-version comparator.

## Install

Copy `upgrade-impact-analysis.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor MCP access through the subagent's bundled MCP server config.
- No shell access or authenticated endorctl setup is required for this edition.

## Example

```text
@agent-upgrade-impact-analysis assess npm lodash from 4.17.20 to 4.17.21
```

## Notes

- This edition uses Endor MCP tools only.
- It records unavailable non-MCP signals in data_gaps rather than fabricating evidence.

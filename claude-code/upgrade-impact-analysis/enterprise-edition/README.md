# Endor Labs Upgrade Impact Analysis Enterprise Edition

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
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-upgrade-impact-analysis show the safest upgrade path for project <project_uuid> package lodash, including CIA and manifest files
```

## Notes

- This edition uses MCP first, then read-only endorctl api lookups for richer signals.
- Bash use is limited by prompt to the documented Endor lookup commands.

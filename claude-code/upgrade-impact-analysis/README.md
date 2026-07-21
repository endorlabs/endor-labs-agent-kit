# Endor Labs Upgrade Impact Analysis

Use this agent when the user asks for Endor Labs Upgrade Impact Analysis:
safe upgrade paths, upgrade risk, findings fixed or introduced, Code Impact
Analysis, breaking changes, manifest targeting, or whether a dependency
upgrade should happen now. The artifact queries Endor's read-only
VersionUpgrade workflow through the agent-attributed read-only CLI transport.

## Start Here

This is the Claude Code generated agent for `upgrade-impact-analysis`.

| Reader | First move |
| --- | --- |
| Human operator | Copy the generated subagent into `.claude/agents/` and restart Claude Code if needed. Then use the example prompt below: @agent-upgrade-impact-analysis show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA and manifest files |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/upgrade-impact-analysis/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy `upgrade-impact-analysis.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-upgrade-impact-analysis show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA and manifest files
```

## Architecture

![Endor Labs Upgrade Impact Analysis architecture](architecture.svg)

This read-only agent resolves a human project selector to the Endor project used for VersionUpgrade queries. Claude Managed Agents do not inspect local git by default, so sessions should provide a repository URL, owner/repo, or Endor project name instead of requiring a project UUID.

## Notes

- This agent uses read-only `endorctl agent api --agent-id upgrade-impact-analysis` lookups and does not require Endor MCP.
- Bash use is limited by prompt to the documented Endor lookup commands.

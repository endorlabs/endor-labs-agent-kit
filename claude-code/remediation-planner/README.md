# Remediation Planner

Preview safe remediation options without opening PRs.

## Install

Copy `remediation-planner.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-remediation-planner preview remediation options for this repository
```

## Architecture

![Remediation Planner architecture](architecture.svg)

This dry-run workflow resolves project or finding context, gathers Endor remediation evidence, and returns a plan only. It does not edit files, push branches, or open PRs/MRs.

## Notes

- This agent uses read-only endorctl api lookups and does not require Endor MCP.
- Bash use is limited by prompt to the documented Endor lookup commands.

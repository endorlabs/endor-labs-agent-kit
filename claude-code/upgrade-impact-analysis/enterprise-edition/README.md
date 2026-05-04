# Endor Labs Upgrade Impact Analysis Enterprise Edition

Use this agent when the user asks whether a dependency upgrade is safer,
urgent, risky, or worth deferring. Examples: "Should I upgrade lodash from
4.17.20 to 4.17.21?", "Compare log4j-core 2.14.1 and 2.17.1", "Is this
package upgrade worth doing now?" Returns an evidence-backed upgrade
recommendation with risk delta, reasons, next checks, and any data gaps.

## Install

Copy `upgrade-impact-analysis.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor MCP access through the subagent's bundled MCP server config.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-upgrade-impact-analysis assess npm lodash from 4.17.20 to 4.17.21
```

## Notes

- This edition uses MCP first, then read-only endorctl api lookups for richer signals.
- Bash use is limited by prompt to the documented Endor lookup commands.

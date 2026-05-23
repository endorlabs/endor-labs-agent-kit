# Endor Labs Package Risk Summary

Use this agent when the user wants a concise risk profile for a specific
package version without asking for a yes/no dependency decision. Examples:
"Summarize npm lodash 4.17.20 risk", "Give me the risk picture for
log4j-core 2.14.1", "What should I know about this package version before I
review it?" Returns an evidence-backed package risk summary with
vulnerabilities, malware or typosquat signals, package scores, license notes,
recommended next checks, and any data gaps.

## Install

Copy `package-risk-summary.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor MCP access through the subagent's bundled MCP server config.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example

```text
@agent-package-risk-summary summarize npm lodash version 4.17.20
```

## Notes

- This agent uses MCP first, then read-only endorctl api lookups for richer signals.
- Bash use is limited by prompt to the documented Endor lookup commands.

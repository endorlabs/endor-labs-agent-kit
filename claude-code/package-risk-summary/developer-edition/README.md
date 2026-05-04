# Endor Labs Package Risk Summary Developer Edition

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
- No shell access or authenticated endorctl setup is required for this edition.

## Example

```text
@agent-package-risk-summary summarize npm lodash version 4.17.20
```

## Notes

- This edition uses Endor MCP tools only.
- It records unavailable non-MCP signals in data_gaps rather than fabricating evidence.

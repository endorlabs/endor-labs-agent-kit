# Endor Labs Package Risk Summary Enterprise Edition

Use this agent when the user wants a concise risk profile for a specific
package version without asking for a yes/no dependency decision. Examples:
"Summarize npm lodash 4.17.20 risk", "Give me the risk picture for
log4j-core 2.14.1", "What should I know about this package version before I
review it?" Returns an evidence-backed package risk summary with
vulnerabilities, malware or typosquat signals, package scores, license notes,
recommended next checks, and any data gaps.

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-package-risk-summary-enterprise`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package also enables Copilot's `execute` tool for the documented read-only Endor lookups.
- The Endor MCP server is configured for GitHub Actions keyless auth. The target repository still needs the `copilot` environment and setup workflow described in `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`.

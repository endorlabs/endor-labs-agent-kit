# Endor Labs Upgrade Impact Analysis Enterprise Edition

Use this agent when the user asks for Endor Labs Upgrade Impact Analysis:
safe upgrade paths, upgrade risk, findings fixed or introduced, Code Impact
Analysis, breaking changes, manifest targeting, or whether a dependency
upgrade should happen now. Enterprise Edition mirrors AURI's read-only UIA
workflow by querying precomputed VersionUpgrade resources. Developer Edition
is a lighter MCP-only explicit package-version comparator.

## Install

From this package directory:

```bash
copilot plugin install .
```

Uninstall with `copilot plugin uninstall endor-labs-upgrade-impact-analysis-enterprise`.

## Notes

- The custom agent is in `agents/` and embeds its Endor MCP server configuration.
- This package also enables Copilot's `execute` tool for the documented read-only Endor lookups.
- The Endor MCP server is configured for GitHub Actions keyless auth. The target repository still needs the `copilot` environment and setup workflow described in `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`.

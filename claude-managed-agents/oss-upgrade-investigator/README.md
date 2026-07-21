# OSS Upgrade Investigator

Use this agent to investigate safe OSS upgrade paths, upgrade risk, findings
fixed or introduced, Code Impact Analysis, breaking changes, manifest
targeting, or whether a dependency upgrade should happen now. It queries
Endor's read-only VersionUpgrade workflow through the agent-attributed CLI
transport.

## Start Here

This is the Claude Managed Agents generated agent for `oss-upgrade-investigator`.

| Reader | First move |
| --- | --- |
| Human operator | Update generated YAML placeholders, then create the managed agent and environment. Then use the example prompt below: Show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA, findings fixed, manifest files, and breaking changes. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/oss-upgrade-investigator/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Update placeholders in `agent.yaml`, `environment.yaml`, and
`session-template.yaml`, then create the agent and environment in
Claude Managed Agents.

```bash
ant beta:agents create < agent.yaml
ant beta:environments create < environment.yaml
```

Use `session-template.yaml` as the starting point for session creation after
you have the created agent ID, environment ID, and any required vault IDs.

## Requirements

- Anthropic Console or `ant` CLI access to Claude Managed Agents.
- An environment that can install and authenticate endorctl for the read-only API lookups documented in endorctl-setup.md.

## Example User Message

```text
Show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA, findings fixed, manifest files, and breaking changes.
```

## Architecture

![OSS Upgrade Investigator architecture](architecture.svg)

This read-only agent resolves a human project selector to the Endor project used for VersionUpgrade queries. Claude Managed Agents do not inspect local git by default, so sessions should provide a repository URL, owner/repo, or Endor project name instead of requiring a project UUID.

## Notes

- This agent uses read-only `endorctl agent api --agent-id oss-upgrade-investigator` lookups and does not require Endor MCP.
- The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.
- Bash use remains limited by prompt to the documented Endor lookup commands.

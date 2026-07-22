# Troubleshooting

Use this agent when the user needs help diagnosing and fixing Endor Labs
errors, warnings, missing integrations, scan failures, slow scans, or
unhealthy configuration. Troubleshooting gathers the smallest useful
read-only Endor evidence, classifies the issue across scan, integration,
authentication, dependency resolution, container, reachability, policy, and
workflow lanes, then returns low-friction repair guidance without mutating
Endor, source-provider, or repository state.

## Start Here

This is the Claude Managed Agents generated agent for `troubleshooting`.

| Reader | First move |
| --- | --- |
| Human operator | Update generated YAML placeholders, then create the managed agent and environment. Then use the example prompt below: Diagnose this Endor scan failure from redacted error text and read-only tenant evidence. Keep the workflow read-only. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/troubleshooting/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Recommended Model

This is a release-QA target, not a requirement or model allowlist.
Agent Kit does not block compatible customer-selected host models.

- Recommended model: `sonnet`.
- Selection mode: `pinned`.
- Recommended reasoning/effort: `host default`.
- Generated behavior: recipe sonnet alias compiles to claude-sonnet-4-6.
- Override behavior: managed host configuration remains authoritative.
- Provider guidance: <https://code.claude.com/docs/en/sub-agents>.

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
Diagnose this Endor scan failure from redacted error text and read-only tenant evidence. Keep the workflow read-only.
```

## Architecture

![Troubleshooting architecture](architecture.svg)

This read-only agent diagnoses Endor Labs errors, warnings, scan failures, slow scans, missing integrations, and unhealthy configuration from user-provided issue text plus read-only Endor evidence. It returns a troubleshooting verdict, issue lanes, evidence queries, root-cause hypotheses, low-friction repair guidance, validation steps, and gated future action contracts for anything that would mutate Endor, source-provider, registry, CI, or repository state.

## Notes

- This agent diagnoses Endor Labs errors, warnings, missing integrations, scan failures, slow scans, and unhealthy configuration from user-provided issue text plus read-only Endor evidence.
- It returns a troubleshooting verdict, issue lanes, evidence queries, root-cause hypotheses, low-friction repair guidance, validation steps, and gated future action contracts.
- The generated environment allows api.endorlabs.com for read-only Endor lookups. It still must not run scans, create scan log requests, change credentials, edit scan profiles, update integrations, post comments, open PRs/MRs, or mutate Endor state.

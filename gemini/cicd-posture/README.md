# CI/CD And Supply Chain Posture Gemini CLI Bundle

Use this agent when the user wants a read-only CI/CD and supply chain
posture assessment for an Endor namespace, GitHub organization, repository
set, or current repository. The agent combines existing Endor SCPM, CI/CD,
GitHub Actions, and supply-chain findings with read-only GitHub configuration
evidence and optional local CI file inspection, then returns deterministic
scores, critical overrides, evidence queries, and data gaps without mutating
Endor, GitHub, or repository state.

## Start Here

This is the Gemini CLI generated skill and subagent bundle for `cicd-posture`.

| Reader | First move |
| --- | --- |
| Human operator | Prefer the generated Gemini extension under `plugins/gemini/endor-labs-agent-kit`, then restart Gemini CLI. Then use the example prompt below: Use @cicd-posture to assess CI/CD and supply chain posture for namespace <namespace>. Keep it read-only and validate the deterministic score. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/cicd-posture/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install Through The Generated Extension

Prefer the generated extension package under `plugins/gemini/endor-labs-agent-kit`.

```bash
gemini extensions install /path/to/endor-labs-agent-kit/plugins/gemini/endor-labs-agent-kit
```

Restart Gemini CLI after installing or updating the extension.

## Manual Fallback

Copy this bundle into a custom Gemini extension or install the skill and
subagent manually under your Gemini configuration.

## Requirements

- Gemini CLI with access to the current workspace.
- The Endor access path declared by the recipe.
- No mutating repository, source-provider, or Endor writes for this workflow.

## Example

```text
Use @cicd-posture to assess CI/CD and supply chain posture for namespace <namespace>. Keep it read-only and validate the deterministic score.
```

## Example Workflow

```text
Use @cicd-posture to assess CI/CD and supply chain posture for Endor namespace <namespace> and GitHub org <org>. Include Endor SCPM, CICD, GHACTIONS, and SUPPLY_CHAIN findings, branch protection, CODEOWNERS, action pinning, permissions, risky triggers, self-hosted runners, update automation, deterministic scores, critical overrides, evidence_queries, and data_gaps. Do not run scans or mutate anything.
```

```text
Use @cicd-posture for these repositories only: <owner/repo>, <owner/repo>. Compute raw_counts, dimension_scores, score_validation, and recommended human actions without editing workflows or branch protection.
```

## Architecture

![CI/CD And Supply Chain Posture architecture](architecture.svg)

This read-only agent assesses CI/CD and supply chain posture from existing Endor SCPM, CI/CD, GitHub Actions, and supply-chain findings plus read-only GitHub configuration evidence. It returns deterministic dimension scores, critical overrides, evidence queries, recommended human actions, and data gaps without running scans, changing branch protection, editing workflows, dispatching workflows, or mutating Endor state.

## Notes

- `SKILL.md` and the subagent markdown are generated from the source recipe and should not be hand-edited in installed copies.
- The plugin package installs the skill under `skills/<agent>/` and the subagent under `agents/<agent>.md`.
- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.
- This read-only workflow must report unavailable signals in `data_gaps`.

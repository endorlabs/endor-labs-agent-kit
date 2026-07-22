# CI/CD And Supply Chain Posture Codex Skill

Use this agent when the user wants a read-only CI/CD and supply chain
posture assessment for an Endor namespace, GitHub organization, repository
set, or current repository. The agent combines existing Endor SCPM, CI/CD,
GitHub Actions, and supply-chain findings with read-only GitHub configuration
evidence and optional local CI file inspection, then returns deterministic
scores, critical overrides, evidence queries, and data gaps without mutating
Endor, GitHub, or repository state.

## Start Here

This is the Codex generated skill for `cicd-posture`.

| Reader | First move |
| --- | --- |
| Human operator | Copy this generated skill directory into `$HOME/.agents/skills/` and start a new Codex session. Then use the example prompt below: Use the cicd-posture skill to assess CI/CD and supply chain posture for namespace <namespace>. Keep it read-only and validate the deterministic score. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/cicd-posture/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Recommended Model

This is a release-QA target, not a requirement or model allowlist.
Agent Kit does not block compatible customer-selected host models.

- Recommended model: `gpt-5.6-luna`.
- Selection mode: `pinned`.
- Recommended reasoning/effort: `medium`.
- Generated behavior: custom-agent TOML pins gpt-5.6-luna and tier-specific reasoning effort.
- Override behavior: explicit Codex model and reasoning settings win.
- Provider guidance: <https://developers.openai.com/codex/subagents>.

## Install

Copy this generated skill directory into your Codex skills directory:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R /path/to/endor-labs-agent-kit/codex/cicd-posture \
  "$HOME/.agents/skills/cicd-posture"
```

Start a new Codex session after installing or replacing the skill.

## Requirements

- Codex with access to the current workspace.
- The Endor access path declared by the recipe.
- No mutating repository, source-provider, or Endor writes for this skill.

## Example

```text
Use the cicd-posture skill to assess CI/CD and supply chain posture for namespace <namespace>. Keep it read-only and validate the deterministic score.
```

## Example Workflow

```text
Use the cicd-posture skill to assess CI/CD and supply chain posture for Endor namespace <namespace> and GitHub org <org>. Include Endor SCPM, CICD, GHACTIONS, and SUPPLY_CHAIN findings, branch protection, CODEOWNERS, action pinning, permissions, risky triggers, self-hosted runners, update automation, deterministic scores, critical overrides, evidence_queries, and data_gaps. Do not run scans or mutate anything.
```

```text
Use the cicd-posture skill for these repositories only: <owner/repo>, <owner/repo>. Compute raw_counts, dimension_scores, score_validation, and recommended human actions without editing workflows or branch protection.
```

## QA Smoke Test

Use a fresh Codex session after installing the skill. Run a planning-only
prompt first and verify the response references the Codex skill, preserves
approval gates, and does not claim file edits, PR/MR creation, comments, or
Endor policy writes.

## Architecture

![CI/CD And Supply Chain Posture architecture](architecture.svg)

This read-only agent assesses CI/CD and supply chain posture from existing Endor SCPM, CI/CD, GitHub Actions, and supply-chain findings plus read-only GitHub configuration evidence. It returns deterministic dimension scores, critical overrides, evidence queries, recommended human actions, and data gaps without running scans, changing branch protection, editing workflows, dispatching workflows, or mutating Endor state.

## Notes

- `SKILL.md` is generated from the source recipe and should not be hand-edited in installed copies.
- This read-only skill does not include `actions.yaml`; future mutating workflows must declare explicit action contracts before publication.
- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.

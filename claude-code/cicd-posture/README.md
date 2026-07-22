# CI/CD And Supply Chain Posture

Use this agent when the user wants a read-only CI/CD and supply chain
posture assessment for an Endor namespace, GitHub organization, repository
set, or current repository. The agent combines existing Endor SCPM, CI/CD,
GitHub Actions, and supply-chain findings with read-only GitHub configuration
evidence and optional local CI file inspection, then returns deterministic
scores, critical overrides, evidence queries, and data gaps without mutating
Endor, GitHub, or repository state.

## Start Here

This is the Claude Code generated agent for `cicd-posture`.

| Reader | First move |
| --- | --- |
| Human operator | Copy the generated subagent into `.claude/agents/` and restart Claude Code if needed. Then use the example prompt below: @agent-cicd-posture assess CI/CD and supply chain posture for namespace <namespace> |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/cicd-posture/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Recommended Model

This is a release-QA target, not a requirement or model allowlist.
Agent Kit does not block compatible customer-selected host models.

- Recommended model: `sonnet`.
- Selection mode: `pinned`.
- Recommended reasoning/effort: `host default`.
- Generated behavior: agent frontmatter defaults to sonnet.
- Override behavior: Claude environment or per-invocation subagent override wins.
- Provider guidance: <https://code.claude.com/docs/en/sub-agents>.

## Install

Copy `cicd-posture.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.
- Read-only GitHub.com credentials through `gh` or exported GitHub repository inventory JSON.

## Setup Checklist

### 1. Install The Subagent

Run this from the target repository or admin workspace where Claude Code
will perform the read-only posture review:

```bash
mkdir -p .claude/agents
cp /path/to/endor-labs-agent-kit/claude-code/cicd-posture/cicd-posture.md \
  .claude/agents/cicd-posture.md
```

### 2. Verify Read-Only Access

Run these read-only checks when live GitHub evidence is available:

```bash
endorctl --version
gh auth status        # GitHub repository configuration evidence
```

CI/CD Posture does not need an Endor MCP server. If Endor finding access,
GitHub repository configuration, workflow files, branch protection,
CODEOWNERS, or local CI files are unavailable, the agent should report
the missing signal in `data_gaps`.

### 3. Keep The Posture Review Read-Only

The agent may list existing Endor findings and fetch GitHub repository
configuration, workflow files, CODEOWNERS, and CI evidence. It should
not run scans, clone repositories, dispatch workflows, edit files, change
branch protection or repository settings, or open PRs/MRs.

## Example

```text
@agent-cicd-posture assess CI/CD and supply chain posture for namespace <namespace>
```

## Example Workflow

Use these copy/paste prompts after the agent is installed.

```text
@agent-cicd-posture assess CI/CD and supply chain posture for Endor namespace <namespace> and GitHub org <org>. Include Endor SCPM, CICD, GHACTIONS, and SUPPLY_CHAIN findings, branch protection, CODEOWNERS, action pinning, permissions, risky triggers, self-hosted runners, update automation, deterministic scores, critical overrides, evidence_queries, and data_gaps. Do not run scans or mutate anything.
```

```text
@agent-cicd-posture assess these repositories only: <owner/repo>, <owner/repo>. Compute raw_counts, dimension_scores, score_validation, and recommended human actions without editing workflows or branch protection.
```

The result should show the raw counts behind every dimension score, explain
any critical override, and include the validator command needed to recheck
the deterministic score before the report is trusted.

## Architecture

![CI/CD And Supply Chain Posture architecture](architecture.svg)

This read-only agent assesses CI/CD and supply chain posture from existing Endor SCPM, CI/CD, GitHub Actions, and supply-chain findings plus read-only GitHub configuration evidence. It returns deterministic dimension scores, critical overrides, evidence queries, recommended human actions, and data gaps without running scans, changing branch protection, editing workflows, dispatching workflows, or mutating Endor state.

## Notes

- This agent assesses CI/CD and supply chain posture from existing Endor findings plus read-only GitHub repository configuration evidence.
- It uses read-only Endor and GitHub lookups to produce dimension scores, critical overrides, evidence queries, recommended actions, and data gaps.
- It must not run scans, clone repositories, dispatch workflows, change branch protection or repository settings, open PRs/MRs, or mutate Endor state.

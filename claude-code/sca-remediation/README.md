# SCA Remediation

Plan and remediate dependency vulnerabilities with Endor SCA findings, VersionUpgrade/UIA evidence, separate low-risk PR lanes, deterministic risk decisions, local validation, and approved PR/MR creation.

## Start Here

This is the Claude Code generated agent for `sca-remediation`.

| Reader | First move |
| --- | --- |
| Human operator | Copy the generated subagent into `.claude/agents/` and restart Claude Code if needed. Then use the example prompt below: @agent-sca-remediation check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR until I approve. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `actions.yaml`, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/sca-remediation/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy `sca-remediation.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor tenant access through authenticated `endorctl agent api --agent-id sca-remediation`.
- A local workspace checkout for any repository the agent will patch.
- Git and source-provider credentials that can push a branch and open the requested pull request or merge request.

## Setup Checklist

### 1. Install The Subagent

Run this from the target repository where Claude Code will operate:

```bash
mkdir -p .claude/agents
cp /path/to/endor-labs-agent-kit/claude-code/sca-remediation/sca-remediation.md \
  .claude/agents/sca-remediation.md
```

### 2. Verify Local Access

Run the checks that match your source provider:

```bash
git remote -v
endorctl --version
endorctl host-check
gh auth status        # GitHub repositories
glab auth status      # GitLab repositories
```

Claude Code does not need an Endor MCP server for this agent. If `endorctl`,
agent-attributed Endor API authentication, local dependency-manager tooling, or
source-provider credentials are not authenticated, the agent should report
the missing setup in `data_gaps`.

### 3. Prepare For Approval Gates

The agent shows UIA evidence, risk_decision, target files, diff,
validation plan, branch, and PR/MR body before mutating. Approve file
edits and PR/MR creation as separate steps.

Validation commands are selected from the repository's actual package
manager and build metadata. The agent should not assume a Maven, npm,
Python, Go, .NET, Ruby, Rust, or any other ecosystem layout until it
has inspected the local manifests and documented build instructions.

## Example

```text
@agent-sca-remediation check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR until I approve.
```

## Example Workflow

Use these copy/paste prompts after the agent is installed.

### 1. Rank Without Mutating

```text
@agent-sca-remediation check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR/MR. Rank package-level fixes and show the UIA evidence for the best first fix.
```

### 2. List Other Low-Risk PRs

```text
@agent-sca-remediation show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and the risky solver. Do not edit files, create branches, push, or open a PR/MR.
```

### 3. Prepare One Patch

```text
@agent-sca-remediation prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.
```

### 4. Open The PR/MR After Approval

```text
@agent-sca-remediation apply the approved patch, run local validation, and then ask me before pushing a branch or opening the PR/MR. Use the AURI-style PR/MR body with emoji sections, UIA evidence, validation status, and a folded advisory/finding list.
```

Do not call a high-count finding bucket low risk unless the response shows
the actual VersionUpgrade/UIA evidence. Prefer a package-level fix when one
package upgrade clears findings across multiple manifests. Future PR/MR bodies
should include the folded `Advisories This Upgrade Fixes` section, and should
scope compatibility claims to Endor UIA/CIA plus validation that actually ran.
If CIA is indeterminate or risk is medium/high, the agent should produce a
deterministic `risk_decision` from Endor evidence plus local source usage
instead of recommending a manual release-note skim.
The selection/plan gate is not complete until that `risk_decision` is
present; low UIA risk, zero conflicts, and a simple manifest edit are
inputs to the verdict, not replacements for it.
Keep low-risk non-breaking UIA candidates separate from P0/exploited
findings and from the risky solver. Hidden P0 duplicates should be
reported separately and excluded from `most_findings_in_one_pr`.
Choose validation commands from the repository's actual ecosystem and
manifest layout; do not carry Maven or any other package-manager
commands across runs unless the current repository proves that layout.
Use the branch convention `remediation/sca/<package>-<target-version>`
unless the user explicitly asks for a different branch name.

## QA Smoke Test

When validating this agent, isolate the run from user-level Claude skills so
the result proves the Agent Kit artifact itself is doing the work.

```bash
export CLAUDE_CONFIG_DIR="$(mktemp -d)"
claude -p --agent sca-remediation --permission-mode bypassPermissions \
  "Check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR until I approve."
```

The run log should not reference user-level skills or Endor MCP tooling.
If it does, the test is contaminated and should be rerun in a clean
Claude configuration.

## Architecture

![SCA Remediation architecture](architecture.svg)

This mutating Claude Code agent resolves repository context, queries Endor SCA findings, requires VersionUpgrade/UIA evidence before recommending a best first fix, keeps non-breaking low-risk UIA PR candidates separate from the P0/exploited queue and risky solver, resolves risky or CIA-indeterminate upgrades into a deterministic risk_decision, prepares local dependency changes, runs ecosystem-appropriate validation when possible, and opens a PR/MR only after explicit approval. It does not use or require an Endor MCP server.

## Notes

- This agent preserves the SCA remediation workflow capabilities as a mutating agent.
- The agent may query Endor SCA findings and VersionUpgrade/UIA evidence, list separate non-breaking low-risk PR-ready candidates, inspect local manifests, produce a deterministic risk_decision, prepare dependency changes, run validation, open a change request, and post a remediation comment when approved.
- Confirm the selected package, UIA evidence, risk_decision, target files, generated diff, validation status, branch, and PR/MR body before allowing mutations.
- `actions.yaml` lists the semantic side effects and any external adapter requirements.

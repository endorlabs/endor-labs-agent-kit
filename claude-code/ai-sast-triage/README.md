# AI SAST Triage

Parse Endor AI SAST findings, use exploit reproduction and remediation guidance as patch context, fetch source at the pinned commit, and open change requests when requested.

## Start Here

This is the Claude Code generated agent for `ai-sast-triage`.

| Reader | First move |
| --- | --- |
| Human operator | Copy the generated subagent into `.claude/agents/` and restart Claude Code if needed. Then use the example prompt below: @agent-ai-sast-triage triage AI SAST findings for this repository. Do not open a PR until I approve the patch. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `actions.yaml`, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/ai-sast-triage/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy `ai-sast-triage.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Endor tenant access through authenticated `endorctl agent api --agent-id ai-sast-triage`.
- A local workspace checkout for any repository the agent will patch.
- Git and source-provider credentials that can push a branch and open the requested pull request or merge request.
- GitHub or GitLab credentials that can read PR/MR reviews and comments from the target repository.
- A configured AppSec approver list when the agent is allowed to create Endor exception policies in standalone mode.
- Endor policy-write access for direct exception-policy creation after verified AppSec approval.

## Setup Checklist

### 1. Install The Subagent

Run this from the target repository where Claude Code will operate:

```bash
mkdir -p .claude/agents
cp /path/to/endor-labs-agent-kit/claude-code/ai-sast-triage/ai-sast-triage.md \
  .claude/agents/ai-sast-triage.md
```

Or ask an LLM with filesystem access to do it:

```text
Install the Endor Labs AI SAST Triage agent in this repository.

Agent Kit root: /path/to/endor-labs-agent-kit
Agent artifact: claude-code/ai-sast-triage/ai-sast-triage.md
Install path: .claude/agents/ai-sast-triage.md

Preserve the generated agent prompt exactly. After installing it, check
endorctl, git remote, and GitHub/GitLab CLI access, then tell
me the exact prompt to invoke the agent.
```

### 2. Verify Local Access

Run the checks that match your source provider:

```bash
git remote -v
endorctl --version
gh auth status        # GitHub repositories
glab auth status      # GitLab repositories
```

Claude Code does not need an Endor MCP server for this agent. If `endorctl`,
agent-attributed Endor API authentication or source-provider credentials are not
authenticated, the agent should report the missing setup in `data_gaps`.

### 3. Understand Finding Evidence

When Endor AI SAST includes `## Exploit Reproduction`, the agent uses it
for priority, confidence, and safe local validation planning. It must not
run exploit steps against live systems or paste weaponized detail into a
PR/MR body.

When Endor AI SAST includes `## Remediation Guidance`, the agent uses it as
patch context. It can apply the guidance as-is, adapt it to the codebase,
or reject it with a reason when the pinned source or tests show a safer fix.

### 4. Match The AURI PR/MR Body

Remediation PR/MR bodies should follow the AURI AI SAST structure:

- `## 🛡️ Endor Labs AURI Security Fix: <finding title>`
- hidden `<!-- auri:ai-sast-context ... -->` finding/project metadata
- `### 🔧 What changed`
- `### 🔎 Evidence provided by AURI`
- `### ✅ Review checklist`
- `### 📝 Need an exception instead?` with standalone Agent Kit request prompts
- folded `📎 Finding details` table

Severity must be visually indicated everywhere it is shown: Critical `🔴`,
High `🟠`, Medium `🟡`, and Low `🟢`.
Default to one remediation PR/MR per AI SAST finding so review, validation,
rollback, and exception handling stay traceable. Group findings only when
one small, cohesive source change fixes the same root cause in the same
repository/component or when the user explicitly asks for grouping.
The PR/MR title should start with the visual indicator and highest severity
represented, such as `🟡 Medium: Fix ...` for one finding or
`🟠 High: Fix 3 AI SAST findings` for a tightly grouped fix. Bracket-only
titles like `[Medium] Fix ...` should be treated as invalid.

When `endor-agent-kit` is available and temporary file writes are allowed,
use it as the source of truth for generated bodies: validate the normalized
AI SAST JSON, render the PR/MR body, and lint the rendered body before
opening the change request.

### 5. Configure Optional AppSec Approvers

The exception workflow is optional. You can use the agent for triage and
remediation PR/MRs without configuring AppSec approvers or Endor policy-write
access. If your team wants PR/MR-driven exceptions, standalone exception
creation requires an approval artifact in the PR/MR. Give the agent the
allowed approvers before it creates an Endor exception policy. Use GitHub
handles, GitLab usernames, or team slugs:

```text
AppSec approvers: @alice, @bob, @endor-labs/appsec
```

The developer requesting the exception must not approve their own request.

### 6. Approval Comment Format

When the agent requests an exception, an AppSec approver should comment or
review with one of these exact forms:

```text
APPSEC APPROVED: false positive for finding <finding_uuid> - <why this is not exploitable>
APPSEC APPROVED: accept risk for finding <finding_uuid> until YYYY-MM-DD - <owner, mitigation, and why code will not change now>
```

The agent verifies the approver, finding UUID, request type, and expiration
before it renders the Endor policy spec. In standalone Agent Kit, PR/MR comments are approval evidence only; they do not automatically trigger a
policy write unless a user or external automation invokes the installed
agent.

### 7. Optional Policy Creation Gate

The agent may create a scoped Endor exception policy only after all of these
are true:

- AppSec approval evidence is verified from the PR/MR.
- Existing Endor policies are checked by generated policy name and finding UUID.
- The policy spec is shown in the Claude Code session.
- The user explicitly confirms policy creation.
- Endor returns a policy UUID.

If an active matching exception policy already exists for the same finding,
project, and reason, the agent should reuse that policy and should not
create a duplicate. The PR/MR decision comment should show the policy name
first, keep the policy UUID for API traceability, and display a human-readable
Endor project label instead of raw `$uuid=...` selector syntax.

## Example

```text
@agent-ai-sast-triage triage AI SAST findings for this repository. Do not open a PR until I approve the patch.
```

## Example Workflow

Use these copy/paste prompts after the agent is installed. Replace the
placeholders with the finding UUID, PR/MR URL, date, and AppSec approvers
from your environment.

### 1. Triage Without Mutating

```text
@agent-ai-sast-triage triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy. Show confirmed true positives, likely false positives, inconclusive findings, exploit-driven priority, remediation-guidance usage, and data gaps.
```

### 2. Open One Remediation PR

```text
@agent-ai-sast-triage remediate finding <finding_uuid> for this repository. Use Endor Exploit Reproduction and Remediation Guidance as context, but verify the fix against the source. Show me the patch, branch name, PR/MR title, and PR/MR body before pushing. After I approve, open exactly one PR/MR.
```

Use one PR/MR per finding by default. If a single cohesive source change
fixes several findings with the same root cause, use the highest severity
in the title, for example `🟠 High: Fix 3 AI SAST findings`, and list each
finding separately in the body.

### 3. Request Optional Exception Approval

This workflow is optional; use it only when the finding should be excepted
instead of remediated in code.

```text
@agent-ai-sast-triage request an AppSec exception review for finding <finding_uuid> on PR/MR <pr_or_mr_url>. Request type: accept risk until YYYY-MM-DD. Reason: <owner, mitigation, and why code will not change now>. Allowed AppSec approvers: @alice, @bob. Do not create an Endor policy yet. Post or update a PR/MR comment with the exact approval phrase the approver can use.
```

### 4. AppSec Approval Comment

An allowed AppSec approver can use one of these comments or review bodies:

```text
APPSEC APPROVED: false positive for finding <finding_uuid> - <why this is not exploitable>
APPSEC APPROVED: accept risk for finding <finding_uuid> until YYYY-MM-DD - <owner, mitigation, and why code will not change now>
```

The requester, PR author, and agent account must not approve their own
exception request.

### 5. Optional Scoped Endor Exception Policy

```text
@agent-ai-sast-triage verify AppSec approval on PR/MR <pr_or_mr_url> for finding <finding_uuid>. Allowed AppSec approvers: @alice, @bob. If approval is valid and not self-approval, check for an existing active Endor exception policy for this finding/project/reason, then render the Endor exception policy spec for my confirmation. After I confirm, create or reuse the scoped policy and comment on the PR/MR with the policy name, policy UUID, Endor project, approver, expiration, and evidence URL.
```

For render-only exception checks, the agent should emit validator-ready
JSON with `approvals[].approved: true`, `approvals[].expiration_time`,
`exception_policies[].policy_name`, `exception_policies[].idempotency_check`,
and `exception_policies[].policy_spec`. A pending policy should fail only
the explicit-confirmation gate until the user approves the Endor write.

Do not combine remediation and exception approval in normal production use.
If you test both paths for QA, label the exception as temporary validation.
Redact concrete exploit payloads from PR/MR prose and comments.

## QA Smoke Test

When validating this agent, isolate the run from user-level Claude skills so
the result proves the Agent Kit artifact itself is doing the work.

```bash
export CLAUDE_CONFIG_DIR="$(mktemp -d)"
claude -p --agent ai-sast-triage --permission-mode bypassPermissions \
  "Triage AI SAST findings for this repository. Do not open a PR until I approve the patch."
```

The run log should not reference user-level skills such as
`~/.claude/skills/endor-ai-sast`. If it does, the test is contaminated
and should be rerun in a clean Claude configuration.

## Architecture

![AI SAST Triage architecture](architecture.svg)

In Agent Kit, PR/MR creation is host-mediated. Claude Code runs in the target checkout, gathers Endor evidence including exploit reproduction and remediation guidance when present, applies the confirmed diff locally, creates and pushes a branch, then opens the change request with configured source-provider credentials. If the host cannot perform one of those steps, the agent must stop and report the missing capability in `data_gaps`.

## Notes

- This agent preserves the AI SAST triage workflow capabilities as a mutating agent.
- The agent may fetch source context, prepare patches, edit files, run commands, open a change request, verify AppSec approval evidence, and create an Endor exception policy when the workflow requires it.
- Confirm repository and branch targets before allowing write or pull-request actions. Confirm the rendered Endor policy spec before allowing exception-policy creation.
- `actions.yaml` lists the semantic side effects and any external adapter requirements.

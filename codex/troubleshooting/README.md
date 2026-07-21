# Troubleshooting Codex Skill

Use this agent when the user needs help diagnosing and fixing Endor Labs
errors, warnings, missing integrations, scan failures, slow scans, or
unhealthy configuration. Troubleshooting gathers the smallest useful
read-only Endor evidence, classifies the issue across scan, integration,
authentication, dependency resolution, container, reachability, policy, and
workflow lanes, then returns low-friction repair guidance without mutating
Endor, source-provider, or repository state.

## Start Here

This is the Codex generated skill for `troubleshooting`.

| Reader | First move |
| --- | --- |
| Human operator | Copy this generated skill directory into `$HOME/.agents/skills/` and start a new Codex session. Then use the example prompt below: Use the troubleshooting skill to diagnose this Endor issue from redacted error text and read-only tenant evidence. Keep the workflow read-only. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/troubleshooting/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy this generated skill directory into your Codex skills directory:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R /path/to/endor-labs-agent-kit/codex/troubleshooting \
  "$HOME/.agents/skills/troubleshooting"
```

Start a new Codex session after installing or replacing the skill.

## Requirements

- Codex with access to the current workspace.
- The Endor access path declared by the recipe.
- No mutating repository, source-provider, or Endor writes for this skill.

## Example

```text
Use the troubleshooting skill to diagnose this Endor issue from redacted error text and read-only tenant evidence. Keep the workflow read-only.
```

## Example Workflow

```text
Use the troubleshooting skill to diagnose this Endor scan failure. Namespace: <namespace>. Project: <project>. Error: <redacted error text>. Keep the workflow read-only and tell me the lowest-friction fix.
```

```text
Use the troubleshooting skill to troubleshoot slow PR scans in a large monorepo. Check whether incremental PR scans, baselines, scan profile settings, or workflow configuration would improve performance. Do not change the profile or rerun scans.
```

```text
Use the troubleshooting skill to diagnose why users cannot log in through SSO for namespace <namespace>. Inspect read-only identity provider evidence and do not print secrets.
```

## QA Smoke Test

Use a fresh Codex session after installing the skill. Run a planning-only
prompt first and verify the response references the Codex skill, preserves
approval gates, and does not claim file edits, PR/MR creation, comments, or
Endor policy writes.

## Architecture

![Troubleshooting architecture](architecture.svg)

This read-only agent diagnoses Endor Labs errors, warnings, scan failures, slow scans, missing integrations, and unhealthy configuration from user-provided issue text plus read-only Endor evidence. It returns a troubleshooting verdict, issue lanes, evidence queries, root-cause hypotheses, low-friction repair guidance, validation steps, and gated future action contracts for anything that would mutate Endor, source-provider, registry, CI, or repository state.

## Notes

- `SKILL.md` is generated from the source recipe and should not be hand-edited in installed copies.
- This read-only skill does not include `actions.yaml`; future mutating workflows must declare explicit action contracts before publication.
- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.

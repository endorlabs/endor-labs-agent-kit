# Findings Browser Codex Skill

Use this agent when the user wants to browse, filter, summarize, or inspect
existing Endor Labs findings. Findings Browser uses read-only Endor evidence
to list matching findings, explain applied filters, surface pagination and
truncation limits, and identify data gaps without starting new scans or
performing remediation actions.

## Start Here

This is the Codex generated skill for `findings-browser`.

| Reader | First move |
| --- | --- |
| Human operator | Copy this generated skill directory into `$HOME/.agents/skills/` and start a new Codex session. Then use the example prompt below: Use the findings-browser skill to list active critical and high Endor findings for namespace <namespace>. Keep the workflow read-only and do not run a scan. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`, `architecture.svg`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/findings-browser/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy this generated skill directory into your Codex skills directory:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R /path/to/endor-labs-agent-kit/codex/findings-browser \
  "$HOME/.agents/skills/findings-browser"
```

Start a new Codex session after installing or replacing the skill.

## Requirements

- Codex with access to the current workspace.
- The Endor access path declared by the recipe.
- No mutating repository, source-provider, or Endor writes for this skill.

## Example

```text
Use the findings-browser skill to list active critical and high Endor findings for namespace <namespace>. Keep the workflow read-only and do not run a scan.
```

## Example Workflow

```text
Use the findings-browser skill to browse active critical and high findings in Endor namespace <namespace> for repository <owner/repo>. Show applied filters, table rows, pagination notes, evidence_queries, and data_gaps. Do not run scans or mutate anything.
```

```text
Use the findings-browser skill to inspect finding <finding_uuid> in namespace <namespace>. Return the exact finding row and do not infer project-wide counts from the single lookup.
```

## QA Smoke Test

Use a fresh Codex session after installing the skill. Run a planning-only
prompt first and verify the response references the Codex skill, preserves
approval gates, and does not claim file edits, PR/MR creation, comments, or
Endor policy writes.

## Architecture

![Findings Browser architecture](architecture.svg)

This diagram shows the generated agent contract, host responsibilities, and external systems required at runtime.

## Notes

- `SKILL.md` is generated from the source recipe and should not be hand-edited in installed copies.
- This read-only skill does not include `actions.yaml`; future mutating workflows must declare explicit action contracts before publication.
- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.

# Dependency Decision Helper Codex Skill

Use this agent when the user asks whether to add, upgrade, or use a specific
package version. Examples: "Is lodash 4.17.20 safe?", "Should I use requests
2.28.0?", "Check log4j-core 2.14.1 before I add it." Returns a dependency
verdict with evidence, conditions, alternatives, and any data gaps.

## Start Here

This is the Codex generated skill for `dependency-decision-helper`.

| Reader | First move |
| --- | --- |
| Human operator | Copy this generated skill directory into `$HOME/.agents/skills/` and start a new Codex session. Then use the example prompt below: Use the dependency-decision-helper skill to help with this Endor Labs workflow. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file, `endorctl-setup.md`. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/dependency-decision-helper/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

## Install

Copy this generated skill directory into your Codex skills directory:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R /path/to/endor-labs-agent-kit/codex/dependency-decision-helper \
  "$HOME/.agents/skills/dependency-decision-helper"
```

Start a new Codex session after installing or replacing the skill.

## Requirements

- Codex with access to the current workspace.
- The Endor access path declared by the recipe.
- No mutating repository, source-provider, or Endor writes for this skill.

## Example

```text
Use the dependency-decision-helper skill to help with this Endor Labs workflow.
```

## Notes

- `SKILL.md` is generated from the source recipe and should not be hand-edited in installed copies.
- This read-only skill does not include `actions.yaml`; future mutating workflows must declare explicit action contracts before publication.
- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.

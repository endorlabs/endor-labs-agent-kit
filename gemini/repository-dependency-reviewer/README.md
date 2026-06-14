# Endor Labs Repository Dependency Reviewer Gemini CLI Bundle

Use this agent inside a source repository when the user wants a read-only
dependency risk review based on local manifests. It inspects dependency files,
resolves exact package coordinates when possible, checks those coordinates
with Endor MCP tools, and reports risky dependencies, unresolved versions,
recommended next checks, and data gaps.

## Start Here

This is the Gemini CLI generated skill and subagent bundle for `repository-dependency-reviewer`.

| Reader | First move |
| --- | --- |
| Human operator | Prefer the generated Gemini extension under `plugins/gemini/endor-labs-agent-kit`, then restart Gemini CLI. Then use the example prompt below: Use @repository-dependency-reviewer to help with this Endor Labs workflow. |
| Agent installer | Copy the generated files exactly, including the generated prompt or skill file. Do not summarize or rewrite the generated prompt. |
| Maintainer | Change `source/agents/repository-dependency-reviewer/recipe.yaml`, `instructions.md`, evals, action contracts, or `architecture.svg`, then regenerate the catalog. Do not hand-edit generated copies. |

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
Use @repository-dependency-reviewer to help with this Endor Labs workflow.
```

## Notes

- `SKILL.md` and the subagent markdown are generated from the source recipe and should not be hand-edited in installed copies.
- The plugin package installs the skill under `skills/<agent>/` and the subagent under `agents/<agent>.md`.
- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.
- This read-only workflow must report unavailable signals in `data_gaps`.

# Plugin Packaging Design

This is a blast-radius note for adding an Endor Labs Agent Kit plugin route.
It is not an implementation contract yet.

## Current Decision

Codex support is implemented first as generated skills under `codex/<agent>/`.
That keeps the source-first recipe model intact and avoids inventing a plugin
runtime before the host contract is confirmed.

The plugin route should sit alongside generated host artifacts. It should not
replace `.claude/agents/` installs, Claude Managed Agents YAML, or Codex skill
installs until the target plugin host has a stable installation, permission, and
metadata contract.

## Likely Codex Plugin Shape

A Codex plugin package would wrap one or more generated skills:

- `.codex-plugin/plugin.json` for plugin metadata.
- `skills/<agent>/SKILL.md` copied from the generated Codex skill artifact.
- Optional `assets/` for logos and screenshots.
- Optional marketplace metadata outside the plugin when publishing through a
  marketplace.

Do not add MCP servers to the plugin manifest by default. `sca-remediation` and
`ai-sast-triage` are `endorctl_api` workflows, and their safety contract depends
on local terminal/source-provider state plus explicit approval gates.

## Blast Radius

Adding first-class plugin publishing would touch:

- `src/endor_agent_kit/validator.py` for a plugin host or package target.
- `src/endor_agent_kit/publisher.py` for generated plugin directories,
  manifest records, pruning, README rows, and artifact checksums.
- `src/endor_agent_kit/install.py` for drift checks against plugin-installed
  skills.
- `manifest.json` schema expectations, because a plugin package is not the
  same shape as an edition or a single skill artifact.
- Tests for publisher output, pruning, install drift, and generated metadata.

## Safety Requirements

Plugin packaging must preserve the same generated skill text and action
metadata. A plugin installer must not silently grant broader permissions than
the recipe declares.

For mutating agents, file edits, branch pushes, PR/MR creation, PR/MR comments,
approval verification, and Endor policy writes must remain separate gates. A
plugin can improve installation and discovery, but it must not flatten those
gates into a single broad authorization.

## Recommended Next Step

Create a small prototype plugin package outside the published catalog first,
using `codex/ai-sast-triage/` and `codex/sca-remediation/` as inputs. Validate
it through Codex plugin installation and skill invocation before adding a
general `publish-plugin` command or changing the manifest schema.

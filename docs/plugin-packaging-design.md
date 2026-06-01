# Plugin Packaging Design

This is a blast-radius note for adding an Endor Labs Agent Kit plugin route.
The Codex package slice is implemented behind `--include-plugins`; Claude Code
and Gemini package slices remain planned release-critical follow-ups.

## Current Decision

Codex support still publishes generated skills under `codex/<agent>/`, and the
first plugin package slice now wraps the Codex-compatible public workflows under
`plugins/codex/endor-labs-agent-kit/`.

The plugin route should sit alongside generated host artifacts. It should not
replace `.claude/agents/` installs, Claude Managed Agents YAML, or Codex skill
installs until the target plugin host has a stable installation, permission, and
metadata contract.

## Implemented Codex Plugin Shape

The generated Codex plugin package includes:

- `.codex-plugin/plugin.json` for plugin metadata.
- `skills/<agent>/SKILL.md` rendered from the same source recipe body as the
  generated Codex skill artifact.
- `skills/endor-agent-kit-setup/SKILL.md` rendered from
  `source/plugin-support/setup/setup.md`.
- `agents/endor-*-agent.toml` custom-agent files generated from the same recipe
  body, with provenance comments and read-only sandbox hints only for read-only
  workflows.
- `scripts/install_codex_agents.py` for provenance-gated global install, update,
  status, and uninstall of bundled Codex custom agents.
- `assets/logo.svg`.
- Local marketplace metadata at `plugins/codex/.agents/plugins/marketplace.json`.

Do not add MCP servers to the plugin manifest by default. `sca-remediation` and
`ai-sast-triage` are `endorctl_api` workflows, and their safety contract depends
on local terminal/source-provider state plus explicit approval gates.

## Blast Radius

Adding first-class plugin publishing would touch:

- `src/endor_agent_kit/publisher.py` and `src/endor_agent_kit/publication/`
  for generated plugin directories, manifest records, pruning, README rows, and
  artifact checksums.
- `manifest.json` schema expectations, because a plugin package is not the same
  shape as an edition or a single skill artifact. Plugin packages are recorded
  in the separate `plugin_packages` section.
- Tests for publisher output, guardrails, provenance, installer behavior, and
  generated metadata.

Future Claude Code and Gemini package slices should follow the same source-first
publication model rather than introducing hand-assembled packages.

## Safety Requirements

Plugin packaging must preserve the same generated skill text and action
metadata. A plugin installer must not silently grant broader permissions than
the recipe declares.

For mutating agents, file edits, branch pushes, PR/MR creation, PR/MR comments,
approval verification, and Endor policy writes must remain separate gates. A
plugin can improve installation and discovery, but it must not flatten those
gates into a single broad authorization.

## Current Next Step

Validate the generated Codex package through real Codex plugin installation and
new-thread skill/custom-agent visibility. Do not make plugins the primary README
install path until the release-critical Claude Code, Codex, and Gemini host
packages have local host validation.

## Prototype Result - 2026-05-24

The first prototype package used this local marketplace shape:

- `marketplace.json`
- `plugins/endor-agent-kit-security-agents/.codex-plugin/plugin.json`
- `plugins/endor-agent-kit-security-agents/skills/ai-sast-triage/`
- `plugins/endor-agent-kit-security-agents/skills/sca-remediation/`

The package copied the generated Codex skill directories byte-for-byte from
`codex/ai-sast-triage/` and `codex/sca-remediation/`, including each
`SKILL.md`, `README.md`, `actions.yaml`, `architecture.svg`, and
`endorctl-setup.md`.

Validation covered:

- plugin manifest JSON parsing and required metadata fields.
- marketplace path resolution to the local plugin directory.
- Codex skill YAML frontmatter parsing for both packaged skills.
- recursive directory diffs against the generated catalog skill directories.
- absence of plugin-level MCP or app declarations.

Previously unproven and still requiring release validation:

- Codex UI installation from the local marketplace deeplink.
- skill discovery and invocation after plugin installation in a fresh thread.
- bundled custom-agent visibility after setup installs TOML files into
  `${CODEX_HOME:-~/.codex}/agents`.

Do not promote this from opt-in `--include-plugins` to default publication until
the unproven host behavior is validated in Codex without weakening the existing
approval gates.

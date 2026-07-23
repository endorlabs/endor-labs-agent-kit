# Plugin Packaging Design

This is a blast-radius note for adding an Endor Labs Agent Kit plugin route.
The Codex, Claude Code, Gemini, Antigravity, Cursor, and Cursor SDK package
slices are implemented behind `--include-plugins`.

## Current Decision

Claude Code, Codex, and Gemini support still publish generated artifacts under
`claude-code/<agent>/`, `codex/<agent>/`, and `gemini/<agent>/`. The plugin
package slices now wrap host-compatible public workflows under:

- `plugins/codex/endor-labs-agent-kit/`
- `plugins/codex-directory/endor-labs-agent-kit/` for official Codex directory submission
- `plugins/claude/endor-labs-agent-kit/`
- `plugins/claude/ai-plugins/` for legacy Claude Code compatibility
- `plugins/gemini/endor-labs-agent-kit/`
- `plugins/antigravity/endor-labs-agent-kit/`
- `.cursor-plugin/` plus root generated `agents/`, `skills/`, `hooks/`, and
  `assets/logo.png` for Cursor
- `cursor-sdk/` for Cursor Python SDK automation

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
- `assets/logo.png`.
- Public repository marketplace metadata at `.agents/plugins/marketplace.json`.
- Package-local marketplace metadata at
  `plugins/codex/.agents/plugins/marketplace.json` for local validation.

Do not add MCP servers to the plugin manifest by default. `sca-remediation` and
`ai-sast-remediation` are `endorctl_agent_api` workflows, and their safety contract depends
on local terminal/source-provider state plus explicit approval gates.

## Codex Distribution Channels

Codex has two generated packages with the same canonical workflow identities
and different distribution channels:

- `repository`: `plugins/codex/endor-labs-agent-kit/` remains the CLI,
  container, runner, setup, installer, and custom-agent package.
- `official-directory`: `plugins/codex-directory/endor-labs-agent-kit/` is a
  skills-only public submission package with exactly 11 workflow skills.

`CatalogPluginPackage.distribution_channel` defaults to `repository` for old
manifests. Package identity is `(host, name, distribution_channel)`, and
publisher replacement occurs by `(host, distribution_channel)`, so a partial
publication cannot erase the sibling Codex package. Installation checks select
only the repository channel.

The directory package has one `.codex-plugin/plugin.json`, square logo and
composer icon, and `skills/<canonical-id>/` containing only `SKILL.md`,
`agents/openai.yaml`, and the skill-local artifact summarizer. It has no setup
skill, custom-agent TOML, installer, hooks, MCP/apps, staging values, or model
pin. The public skills use the customer's active Codex model. Large-result
instructions resolve the helper from the active `SKILL.md` path rather than the
working directory.

Full publication requires the exact canonical 11-recipe set. A strict subset
skips this package and preserves its directory and manifest record; unexpected
or duplicate Codex recipe IDs fail closed.

## Implemented Claude Code Plugin Shape

The generated Claude Code plugin packages include:

- `.claude-plugin/plugin.json` for plugin metadata.
- `agents/<agent>.md` files generated from the existing Claude Code artifacts.
- `skills/endor-agent-kit-setup/SKILL.md` rendered from
  `source/plugin-support/setup/setup.md`.
- `hooks/hooks.json` plus fail-open advisory hook scripts in the primary
  `endor-labs-agent-kit` package only. These hooks add Claude context for
  prompt routing, dependency installs, and dependency manifest edits; they do
  not block work, call Endor, use the network, run scans, or write files.
- `assets/logo.png`.
- Public-repo marketplace metadata at `.claude-plugin/marketplace.json`.
- Package-local marketplace metadata at
  `plugins/claude/.claude-plugin/marketplace.json` for local validation.

The preferred package id is `endor-labs-agent-kit@endorlabs`. The legacy
`ai-plugins@endorlabs` package is retained as a real generated package so
existing Claude Code users pinned to that id can continue to install and update
without a breaking rename. Both packages expose the same setup skill and agents;
normal users should not enable both ids in the same Claude profile. The legacy
package intentionally does not include hooks.

Claude Code plugin-shipped agents do not support `mcpServers`,
`permissionMode`, or `hooks` in agent frontmatter. The generated package strips
those unsupported fields from packaged agents and makes MCP setup explicit in
the setup skill and agent setup note. It does not add plugin-wide MCP by
default.

## Implemented Gemini CLI Extension Shape

The generated Gemini CLI extension package includes:

- `gemini-extension.json` for extension metadata.
- `GEMINI.md` for minimal package context.
- `skills/<agent>/SKILL.md` rendered from the same source recipe body as the
  generated Gemini skill artifact.
- `skills/endor-agent-kit-setup/SKILL.md` rendered from
  `source/plugin-support/setup/setup.md`.
- `agents/<agent>.md` preview subagents generated from the same recipe body,
  with provenance comments and Gemini host-contract text.
- `assets/logo.png`.

Gemini packages do not declare plugin-wide MCP by default. Setup documents the
observed Gemini CLI 0.44.1 local-install folder trust prompt and requires a
restart after extension installation or update. Gemini CLI installs a local
extension directory; public distribution clones the tagged GitHub repository
and installs `plugins/gemini/endor-labs-agent-kit/` rather than installing the
multi-host repository root. The package does not generate or publish a zip
artifact.

The repository root MCP support surface is separate from the generated Gemini
package. Root `.mcp.json` may include the source-approved `endor-cli-tools` MCP
server metadata so users can opt into MCP setup, and root `GEMINI.md` can point
agents at the correct package. The repository root must not generate
`gemini-extension.json`: Gemini discovers bundled skills from the installed
extension root's `skills/` directory, while the repository root `skills/`
directory is the Cursor package surface. Generated Gemini package metadata under
`plugins/gemini/endor-labs-agent-kit/` remains MCP-free unless provider
validation explicitly changes that package contract.

## Implemented Antigravity CLI Plugin Shape

The generated Antigravity CLI plugin package includes:

- `plugin.json` for plugin metadata.
- `skills/<agent>/SKILL.md` rendered from the Gemini-compatible source recipe
  body with Antigravity host-contract text.
- `skills/endor-agent-kit-setup/SKILL.md` rendered from
  `source/plugin-support/setup/setup.md`.
- `agents/<agent>.md` subagents generated from the same recipe body, with
  provenance comments and Antigravity host-contract text.
- `assets/logo.png`.

Antigravity packages do not declare plugin-wide MCP by default. The setup skill
keeps `antigravity plugin validate`, installation, update, enable/disable, and
uninstall steps explicit and evidence-backed. Antigravity package contents are
derived from the Gemini-compatible recipe set because Google's
transition guidance says Gemini extensions become Antigravity plugins while
retaining skills and subagents.

## Implemented Cursor Package Shape

The source-validation Cursor package includes:

- `.cursor-plugin/plugin.json` for Cursor package metadata.
- `.cursor-plugin/marketplace.json` for public marketplace metadata.
- `agents/<agent>.md` rendered from the source recipe body with Cursor
  plugin-agent frontmatter and host-contract text.
- `agents/endor-agent-kit-setup-agent.md` rendered from
  `source/plugin-support/setup/setup.md`.
- `skills/<agent>/SKILL.md` rendered from the source recipe body with Cursor
  host-contract text and support material.
- `skills/<agent>/architecture.svg` copied from the source agent diagram when
  present.
- `skills/<agent>/actions.yaml` when the source recipe declares action
  contracts.
- `skills/endor-agent-kit-setup/SKILL.md` rendered from
  `source/plugin-support/setup/setup.md`.
- `hooks/hooks.json` plus fail-open advisory hook scripts.
- `.mcp.json` with the source-approved optional MCP server declaration.
- `assets/logo.png`.

Cursor is intentionally not a Gemini wrapper. Its installable package does not
depend on Gemini metadata; the Gemini CLI extension files live under
`plugins/gemini/endor-labs-agent-kit/`. The repository root `GEMINI.md` is
support context only, not an installable Gemini extension manifest.

The Agent Kit source checkout keeps those Cursor components at root for source
guardrails. During `ai-plugins` synchronization, the full Cursor payload is
copied to `plugins/cursor/endor-labs-agent-kit/`. Its conventional package
layout contains `.cursor-plugin/plugin.json`, `agents/`, `skills/`, `hooks/`,
`mcp.json`, and `assets/`. Root `.cursor-plugin/marketplace.json` keeps the
stable `endorlabs` id and points to that nested package; the mirror removes the
root Cursor plugin manifest. This mirror-only boundary lets the official Claude
package safely reserve conventional root `agents/`, `skills/`, and `hooks/`
without changing Cursor's payload.

## Implemented Cursor SDK Automation Shape

The generated Cursor SDK automation package includes:

- `cursor-sdk/README.md` for local and cloud run instructions.
- `cursor-sdk/requirements.txt` with the `cursor-sdk` Python dependency.
- `cursor-sdk/agent_definitions.json` as the machine-readable agent map.
- `cursor-sdk/run_cursor_agent.py` as the runnable Python launcher.
- `cursor-sdk/agents/<agent>.md` generated from the same recipe body with
  Cursor SDK host-contract text.
- `cursor-sdk/agents/<agent>.architecture.svg` when the source recipe has an
  architecture diagram.
- `cursor-sdk/agents/<agent>.actions.yaml` when the source recipe declares
  action contracts.

Cursor SDK automation is a separate lane from Cursor plugin delivery. Use it
for CI, orchestration, backend services, scripted local runs, or Cursor cloud
agents. Use the self-contained Cursor plugin package for customer-facing Cursor
IDE UX. The SDK package is still generated from Agent
Kit source recipes and mirrored into `ai-plugins` as a distribution artifact.

## Blast Radius

First-class plugin publishing touches:

- `src/endor_agent_kit/publisher.py` and `src/endor_agent_kit/publication/`
  for generated plugin directories, manifest records, pruning, README rows, and
  artifact checksums.
- `manifest.json` schema expectations, because a plugin package is not the same
  shape as an edition or a single skill artifact. Plugin packages are recorded
  in the separate `plugin_packages` section.
- Tests for publisher output, guardrails, provenance, installer behavior, and
  generated metadata.

The Gemini package follows the same source-first publication model rather than
introducing hand-assembled packages. Gemini local validation installs from
`plugins/gemini/endor-labs-agent-kit`; public validation clones the tagged
GitHub repository and installs that generated extension directory.

The Antigravity package also follows the source-first publication model. It
installs from `plugins/antigravity/endor-labs-agent-kit` with `plugin.json` at
the package root; no release archive is generated for either target.

The Cursor package follows the same source-first publication model. The Agent
Kit checkout remains root-shaped for generation and source tests; mirror sync
materializes the official self-contained package at
`plugins/cursor/endor-labs-agent-kit/`. Generation updates managed workflow
agents, managed workflow skill directories, and advisory hooks, while
preserving unrelated source-root skills such as
`skills/create-endor-labs-agent/` and excluding them from the public Cursor
package.

The Cursor SDK package follows the same source-first publication model under
`cursor-sdk/`. It does not install anything into the Cursor IDE; it launches
Cursor's Python SDK with generated Agent Kit prompts and an explicit user task.

## Safety Requirements

Plugin packaging must preserve the same generated skill text and action
metadata. A plugin installer must not silently grant broader permissions than
the recipe declares.

For mutating agents, file edits, branch pushes, PR/MR creation, PR/MR comments,
approval verification, and Endor policy writes must remain separate gates. A
plugin can improve installation and discovery, but it must not flatten those
gates into a single broad authorization.

## Release Validation Status

The release gate is now `docs/plugin-release-checklist.md`. Keep this design
note focused on package shape and blast radius.

Validated locally:

- Codex local marketplace installation from `plugins/codex`.
- Codex repo-root marketplace metadata at `.agents/plugins/marketplace.json`.
- Codex custom-agent installer status/install flow with a temporary
  `CODEX_HOME`.
- Gemini extension package install from the generated local extension
  directory.
- Gemini package structure with `gemini-extension.json` at the extension root
  and no zip artifact.
- Antigravity plugin package validation with `antigravity plugin validate`.
- Cursor metadata JSON validation and root skill validation.
- Cursor SDK `agent_definitions.json` validation and launcher `py_compile`.

Still release-critical:

- Claude Code package validation with `claude plugin validate`, local
  marketplace install, and fresh-session agent/skill visibility when the
  `claude` CLI is available.
- Codex public GitHub sparse marketplace validation after the repo is public,
  pushed, and tagged.
- Gemini public GitHub install after the repo is public, pushed, and tagged.
- Antigravity install/list/uninstall validation after the package is generated
  and the installed CLI version is available.
- Cursor public package install validation after the repo is public, pushed,
  and tagged.
- Cursor SDK local or cloud smoke validation after API-key use, target repo,
  namespace provenance, and side-effect boundaries are explicitly approved.

## Prototype Result - 2026-05-24

The first prototype package used this local marketplace shape:

- `marketplace.json`
- `plugins/endor-agent-kit-security-agents/.codex-plugin/plugin.json`
- `plugins/endor-agent-kit-security-agents/skills/ai-sast-remediation/`
- `plugins/endor-agent-kit-security-agents/skills/sca-remediation/`

The package copied the generated Codex skill directories byte-for-byte from
`codex/ai-sast-remediation/` and `codex/sca-remediation/`, including each
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

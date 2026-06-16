# Changelog

All notable changes to Endor Labs Agent Kit and the generated `ai-plugins`
distribution are tracked here.

The current generated package version is `2.1.0`. Merging to `main` does not
automatically increment this version. Maintainers bump `pyproject.toml`
intentionally for a release, regenerate artifacts, and use the same version
across Claude Code, Codex, Gemini CLI, Antigravity CLI, Cursor, and Cursor SDK
package metadata.

## Unreleased

## 2.1.0 - 2026-06-16

### Added

- Added fail-open Claude Code primary-plugin advisory hooks for prompt routing,
  dependency install intent, and dependency manifest edits.
- Added the read-only `findings-browser` source agent for browsing existing
  Endor findings across Claude Code, Claude Managed Agents, Codex, Gemini,
  Portable, Cursor, and Cursor SDK surfaces.
- Added the `cicd-posture` read-only Enterprise source agent for CI/CD and
  supply chain posture assessment from existing Endor findings plus read-only
  GitHub evidence, including deterministic score validation.
- Added release changelog coverage for the Agent Kit source repository and the
  generated `ai-plugins` distribution mirror.
- Added MIT license coverage to the Agent Kit source repository, matching the
  public `ai-plugins` distribution license.
- Added source-to-distribution changelog syncing so generated `ai-plugins` PRs
  carry release notes with package artifacts.

### Fixed

- Fixed the `ai-plugins` distribution sync omitting the generated root `hooks/`
  directory that `.cursor-plugin/plugin.json` references, which shipped a
  dangling Cursor hooks pointer in the public mirror.
- Extended the generated-artifact drift gates and mirror validation to cover
  root `hooks/`, per-package hook manifests and scripts, and dangling
  `.cursor-plugin/plugin.json` references.
- Changed the scheduled Endor context refresh workflow from an automated PR
  creator into a signal-only manual refresh gate, matching repository policy
  that GitHub Actions must not create pull requests.

### Changed

- Updated `cicd-posture` scoring to formula `cicd-posture-v2`, using
  conservative scores for unobserved workflow evidence and less aggressive
  Endor finding saturation.
- Bumped the legacy Claude `ai-plugins` package to `1.2.0` because its content
  gained the `findings-browser` agent; the legacy package still ships no hooks.
- Clarified that Agent Kit maintainer merges open generated `ai-plugins` sync
  PRs, but package version updates are explicit release actions.
- Preserved AURI branding in agent prompts and generated package content.
- Refreshed release-readiness docs for the current package version, MIT license
  status, public mirror path wording, and canonical provider documentation URLs.
- Refreshed provider documentation notes for the Gemini CLI to Antigravity CLI
  transition and clarified that Endor context refreshes use human-authored,
  signed PRs.
- Rechecked Claude Code, Codex, Gemini CLI, Antigravity CLI, Cursor, and Endor
  Labs provider release documentation on 2026-06-16 before cutting 2.1.0.

### Removed

- Removed a stale project-local Codex agent file from `.codex/agents/`; Codex
  plugin agents are generated under `plugins/codex/endor-labs-agent-kit/`.

### Compatibility

- Claude Code keeps both package IDs: new installs should use
  `endor-labs-agent-kit@endorlabs`, while existing `ai-plugins@endorlabs`
  installs remain supported through the legacy package directory.
- Cursor does not have a separate legacy `ai-plugins` package ID. Existing
  customers installing from the `ai-plugins` repository root continue to receive
  the current `.cursor-plugin/`, root `agents/`, root `skills/`, root `hooks/`,
  and `assets/logo.png` package.
- Gemini CLI keeps the generated package at
  `plugins/gemini/endor-labs-agent-kit/`, while the repository root keeps only
  `.mcp.json` and non-installable `GEMINI.md` support context. Root
  `gemini-extension.json` and the old Gemini zip artifact are intentionally not
  generated or supported.

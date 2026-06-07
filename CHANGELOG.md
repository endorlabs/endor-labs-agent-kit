# Changelog

All notable changes to Endor Labs Agent Kit and the generated `ai-plugins`
distribution are tracked here.

The current generated package version is `0.2.0`. Merging to `main` does not
automatically increment this version. Maintainers bump `pyproject.toml`
intentionally for a release, regenerate artifacts, and use the same version
across Claude Code, Codex, Gemini CLI, Antigravity CLI, Cursor, and Cursor SDK
package metadata.

## Unreleased

### Added

- Added release changelog coverage for the Agent Kit source repository and the
  generated `ai-plugins` distribution mirror.
- Added MIT license coverage to the Agent Kit source repository, matching the
  public `ai-plugins` distribution license.
- Added source-to-distribution changelog syncing so generated `ai-plugins` PRs
  carry release notes with package artifacts.

### Changed

- Clarified that Agent Kit maintainer merges open generated `ai-plugins` sync
  PRs, but package version updates are explicit release actions.
- Preserved AURI branding in agent prompts and generated package content.
- Refreshed release-readiness docs for the current package version, MIT license
  status, public mirror path wording, and canonical provider documentation URLs.

### Removed

- Removed a stale project-local Codex agent file from `.codex/agents/`; Codex
  plugin agents are generated under `plugins/codex/endor-labs-agent-kit/`.

### Compatibility

- Claude Code keeps both package IDs: new installs should use
  `endor-labs-agent-kit@endorlabs`, while existing `ai-plugins@endorlabs`
  installs remain supported through the legacy package directory.
- Cursor does not have a separate legacy `ai-plugins` package ID. Existing
  customers installing from the `ai-plugins` repository root continue to receive
  the current `.cursor-plugin/`, root `agents/`, root `skills/`, and
  `assets/logo.svg` package.
- Gemini CLI keeps the generated package at
  `plugins/gemini/endor-labs-agent-kit/` and the root compatibility files
  `GEMINI.md` and `gemini-extension.json` in `ai-plugins`. The old Gemini zip
  artifact is intentionally not generated or supported.

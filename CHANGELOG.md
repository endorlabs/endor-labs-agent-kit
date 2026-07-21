# Changelog

All notable changes to Endor Labs Agent Kit and the generated `ai-plugins`
distribution are tracked here.

The current generated package version is `2.1.0`. Merging to `main` does not
automatically increment this version. Maintainers bump `pyproject.toml`
intentionally for a release, regenerate artifacts, and use the same version
across Claude Code, Codex, Gemini CLI, Antigravity CLI, Cursor, and Cursor SDK
package metadata.

## Unreleased

### Added

- Added customer-owned Agent Policy Packs with a public JSON Schema, template
  and examples, `validate-policy-pack` and `evaluate-policy-pack` CLI commands,
  trusted fact preflight, and generated policy outputs across all source agents.
- Added an OpenAPI-derived Endor API resource and enum registry with a generator
  for validating source instructions, knowledge-pack query fields, and rendered
  `--field-mask` values.

### Changed

- Renamed and consolidated the public catalog to 11 canonical agents. The new
  catalog wire schema v2 carries `legacy_ids` for backend-compatible alias
  resolution, and Dependency Reviewer now selects one bounded
  `package-decision`, `package-risk`, or `repository-review` profile instead of
  chaining three overlapping agents.
- Renamed AI SAST Triage to AI SAST Remediation, Remediation Planner to
  Remediation Planning, Upgrade Impact Analysis to OSS Upgrade Investigator,
  Endor Troubleshooter to Troubleshooting, Probe Droid to Configuration
  Automation, Malware Response Agent to Malware Responder, and the display name
  Endor Labs Vulnerability Explainer to Vulnerability Explainer.
- Refreshed the pinned Endor OpenAPI and client/service provenance to
  v1.7.1069, including `ECOSYSTEM_VSCODE` registry coverage.
- Enhanced `findings-browser` with compact complete-count queries and
  `FINDING_TAGS_*` filters for exploited, fix-available, and reachable findings.
- Extended `malware-response` to query tenant `FINDING_CATEGORY_MALWARE`
  evidence and distinguish Endor classifications from external intelligence.
- Extended `cicd-posture` to prefer Endor-ingested repository, CODEOWNERS, and
  tag-protection evidence before falling back to the read-only GitHub API.
- Prioritized exploited findings in `sca-remediation` before VersionUpgrade/UIA
  evidence selects an upgrade candidate.

### Fixed

- Made policy comparisons fail closed on invalid operand types, added trusted
  `invalid_facts` provenance, and introduced explicit numeric dotted-version
  operators instead of coercing version strings through generic comparisons.
- Added policy fact preflight for scope and `when` applicability facts, marked
  WebSphere packs as reference-only, and report their missing evidence as the
  blocking `unavailable` decision.
- Hardened field-mask validation to bind masks to individual commands, scan
  source agent instructions, resolve service-backed resource schemas, and fail
  loudly when an Endor resource mask cannot be validated.
- Report malformed policy-pack YAML as concise CLI validation errors instead
  of Python tracebacks.
- Recomputed workflow policy decisions from a separately trusted fact bag and
  rejected omitted, additional, or modified agent-reported evaluations.
- Aligned runtime policy-pack validation with the public JSON schema by
  rejecting unknown fields, malformed conditions, and missing policy messages.
- Restored compact generated namespace preflight wording required by catalog
  guardrails, including Endor namespace/config provenance and credential input
  literals.
- Extended Endor API registry drift checks to validate knowledge-pack field
  lists as well as every rendered `--field-mask`, and wired the check into
  blocking Agent Kit CI.
- Pinned the OpenAPI JSON under `source/endor-context/` so registry checks run
  offline against the same spec recorded in provenance.
- Scoped Project Resolution Preflight injection to recipes that declare
  `project_resolution`, keeping package-level and workspace-independent agents
  out of project-resolution guidance.
- Clarified generated data-gap taxonomy and findings-browser filter guidance so
  unavailable evidence and QA-only defaults stay machine-readable.

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

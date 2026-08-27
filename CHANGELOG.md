# Changelog

All notable changes to Endor Labs Agent Kit and the generated `ai-plugins`
distribution are tracked here.

The current generated package version is `2.2.2`. Merging to `main` does not
automatically increment this version. Maintainers bump `pyproject.toml`
intentionally for a release, regenerate artifacts, and use the same version
across Claude Code, Codex, Gemini CLI, Antigravity CLI, Cursor, and Cursor SDK
package metadata.

## 2.2.2 - 2026-08-27

### Fixed

- PR 51 review hardening of the dependency-graph audit gate:
  `dependency_graph_audit.manifest` is now required for every
  content-bearing status (only `unavailable` passes manifest-free), the
  audited-manifest membership set is anchored by the required
  `change_requests[0].inventory.key.manifest` so a selection that omits its
  optional manifest lists can no longer launder an arbitrary audited
  manifest, and a selected remediation with zero package-manager detections
  fails closed demanding the audit object instead of skipping the audit
  requirement entirely. Managers without an audit profile (Composer, Swift)
  report `package_manager: null` with `status: "unavailable"` and remediate
  normally, deliberately capped at `approved_with_validation_required` —
  never `approved_low_risk` — because no manager-specific graph-safety audit
  backs the change.
- The `dependency_graph_audit` JSON skeleton in the sca-remediation
  instructions listed only `maven | gradle`; it now carries all 13 supported
  managers, and a drift test pins the skeleton tokens to
  `SUPPORTED_PROFILES` so the two cannot diverge again.
- `_dependency_graph_audit_schema` now derives its vocabulary (statuses,
  classifications, semantic effects, manager names, Maven type union,
  graph/runtime kinds, and the output caps) from the audit engine's
  constants in `package_managers/_base.py` instead of restating them as
  literals, with a lockstep test guarding the wiring; the engine's
  disguise-folding and version-normalization helpers are exported on the
  package surface (`fold_disguises`, `normalize_version_token`).
- The substitution rules in the shared audit engine each ran with an
  untested twin: new tests drive every substitution classification,
  semantic-effect coupling, validation-requirement, and status-forcing
  branch (including both `replacement_conflict_or_incomplete` rules),
  taking `package_managers/_base.py` to 100% statement and branch coverage.
- Cross-family dependency-graph audit hardening (close-out sweep over the
  per-family red-team residuals): every replacement pattern is now
  ASCII-only, so fullwidth lookalike digits can no longer satisfy an
  "exact version" pin in the Maven/Gradle, Node, Python, or Go families
  (NuGet, Bundler, and Cargo already compiled with `re.ASCII`); a payload
  with a null `selected_remediation` and no `selection_blocked` can no
  longer claim a created or reused change request, and a supplied
  `dependency_graph_audit` is now always validated even when the selection
  is nulled out (previously the entire remediation block was skipped); and
  a declared replacement that restates the audited package at the
  remediation's own vulnerable version — a deceptive no-op "replacing" the
  vulnerable state with itself — is rejected engine-wide, while legitimate
  same-name alias pins at a different version keep validating. A follow-up
  adversarial pass over the first version of these fixes found and closed
  three bypasses in them: the restatement guard now anchors on the trusted
  selection identity (selected package name plus from_version and the
  inventory current_version, case- and version-normalized so trailing-`.0`
  padding, `v` prefixes, and casing cannot dodge it) instead of only the
  model-controlled optional `coordinate` field; a
  `dependency_graph_audit` supplied as a non-object and a
  `change_requests` supplied as a non-array now fail closed as shape
  errors instead of being silently coerced away.

### Added

- Rust Cargo dependency-graph safety audit for SCA remediation: a single
  `cargo` profile on the shared kind-bucket engine, mechanism-driven
  (`type` null, `cargo.<construct>` in `mechanism`, required
  `semantic_effect`). Cargo is the only manager for crates.io — no
  registry-family split, canonical inventory ecosystem `cargo`, strong
  `Cargo.toml`/`Cargo.lock` signals (`.cargo/config.toml` carries the
  source-replacement mechanism but is deliberately not a detection signal:
  a bare `config.toml` basename is too generic). Cargo unifies
  semver-compatible requirements, so an exact `=` requirement added only
  to constrain a transitive's unified resolution is forced mediation
  (`cargo.transitive_pin`), a `Cargo.lock` held at a version fresh
  resolution would not pick is an override with `lockfile_override`
  (`cargo.lockfile_pin`; authoritative under `--locked`/`--frozen`), and
  `[patch]`/`[replace]` split by shape — same-crate version redirects are
  forced mediation (`cargo.patch_version`), git/path redirects and
  `.cargo/config.toml` source replacements are overrides with
  `source_override` (`cargo.patch_source`, `cargo.source_replacement`).
  Cargo is the first single-manager family with BOTH removal and
  substitution buckets: feature disables (`cargo.feature_suppression`)
  allow `asset_or_feature_suppression` or `dependency_removal` — chosen by
  whether an optional dependency node actually left the graph — and a
  dependency alias (`name = { package = "other-crate" }`,
  `cargo.package_rename`) is a substitution requiring an exact bare
  `crate@version` replacement (requirement operators, wildcards, partial
  versions, git refs, and scheme prefixes rejected).

- Ruby Bundler dependency-graph safety audit for SCA remediation: a single
  `bundler` profile on the shared kind-bucket engine, mechanism-driven like
  Gradle, Node, Python, Go, and NuGet (`type` null, `bundler.<construct>`
  in `mechanism`, required `semantic_effect`). Bundler is the only manager
  for the RubyGems registry, so there is no registry-family split and no
  shared weak signals — but the canonical inventory ecosystem is the
  registry token `gem`, not the manager name. `Gemfile`/`Gemfile.lock`
  (and `gems.rb`/`gems.locked`) are strong basename signals and `.gemspec`
  is a strong suffix signal. Bundler resolves one unified constraint set,
  so a Gemfile entry added only to force a transitive's resolved version
  is forced mediation (`bundler.transitive_pin`); a hand-edited
  `Gemfile.lock` is an override with `lockfile_override`
  (`bundler.lockfile_edit`; the lockfile rules resolution under
  frozen/deployment mode); and a per-gem `git:`/`github:`/`path:` redirect
  (`bundler.source_redirect`) or `source`-block/mirror swap
  (`bundler.gem_source`) is an override with `source_override` — a fork
  redirect keeps the gem name, so it is never a substitution. The removal
  bucket is suppression-only: `require: false` (`bundler.require_false`)
  keeps the gem resolved and pinned in `Gemfile.lock` while suppressing its
  automatic require at boot, so it is `asset_or_feature_suppression` under
  the same removal safety rules, and `dependency_removal` and
  `dependency_substitution` are never claimable through Bundler
  mechanisms. Replacements are exact bare `gem@version` coordinates
  (Gem::Version strings); requirement operators, wildcards, git refs, and
  scheme prefixes are rejected.

- NuGet (.NET) dependency-graph safety audit for SCA remediation: a single
  `nuget` profile on the shared kind-bucket engine, mechanism-driven like
  Gradle, Node, Python, and Go (`type` null, `nuget.<construct>` in
  `mechanism`, required `semantic_effect`). NuGet is a single-manager
  family: MSBuild project files (`.csproj`/`.fsproj`/`.vbproj`),
  props/targets layers, `packages.lock.json`, `packages.config`, and
  `nuget.config` are all unambiguous strong signals (the first profile to
  exercise the engine's manifest-suffix channel), and the canonical
  inventory ecosystem is `nuget`. MSBuild layers version authority across
  files the project never shows — the parent-POM analog — so a direct
  `PackageReference` added only to pin a transitive (`nuget.transitive_pin`,
  direct-wins), a centrally pinned transitive
  (`nuget.central_transitive_pin`), a `VersionOverride`
  (`nuget.version_override`), and a `Directory.Build.props`/`.targets`
  layer (`nuget.build_props_layer`) are all forced version mediation, while
  the project's own `PackageReference` and Central Package Management
  `PackageVersion` are native. A hand-edited `packages.lock.json` is an
  override with `lockfile_override` (`nuget.lockfile_edit`; integrity holds
  only under `RestoreLockedMode`) and a `nuget.config` source redirect is
  an override with `source_override` (`nuget.restore_source`). NuGet is the
  first mechanism-driven family with a removal bucket, split by what leaves
  the graph: `<PackageReference Remove>` is true `dependency_removal`
  (`nuget.package_remove`), while `ExcludeAssets`/`PrivateAssets`
  suppresses asset flow but never removes the resolved node, so it is
  `asset_or_feature_suppression` (`nuget.exclude_assets`) under the same
  removal safety rules. There is no substitution bucket — a package-ID swap
  is a manifest edit, and `dependency_substitution` is never claimable
  through NuGet mechanisms. Replacements are exact bare `package@version`
  coordinates (three- or four-part versions, prerelease allowed); floating
  versions, bracket ranges, and scheme prefixes are rejected.

- Go modules dependency-graph safety audit for SCA remediation: a single
  `go` profile on the shared kind-bucket engine, mechanism-driven like
  Gradle, Node, and Python (`type` null, `go.<construct>` in `mechanism`,
  required `semantic_effect`). Go is a single-manager family — no
  registry-family split — so the canonical inventory ecosystem is `go` and
  `go.mod`/`go.sum`/`go.work` are unambiguous strong signals. The `replace`
  directive splits by shape: a same-path version redirect is forced version
  mediation (`go.replace_version`), a filesystem/workspace/vendor redirect is
  an override with `source_override` (`go.replace_path`, `go.work_replace`,
  `go.vendor_override`), and a different-module-path redirect is a
  substitution requiring an exact `module@version` replacement
  (`go.replace_module`); a hand-edited `go.sum` is an override with
  `lockfile_override` (`go.sum_edit`); and `exclude` mediates MVS version
  selection (`go.exclude_directive`) — it removes a version from the
  candidate set, never the module node, so `dependency_removal` is never
  claimable through Go mechanisms. Replacements accept full semver,
  pseudo-versions, and `+incompatible`, but reject `@latest`/branch/major-only
  queries and scheme prefixes.

- Python dependency-graph safety audit for SCA remediation: pip, Poetry,
  Pipenv, and uv profiles on the shared kind-bucket engine, mechanism-driven
  like Gradle and Node (`type` null, `<manager>.<construct>` in `mechanism`,
  required `semantic_effect`). Manager identity comes from lockfiles
  (`poetry.lock`, `Pipfile`/`Pipfile.lock`, `uv.lock`/`uv.toml`); pip is the
  family baseline with no lockfile and claims no manager-specific manifests —
  pip identity comes from the audit's declared manager over family-shared
  signals (`pyproject.toml`, `setup.py`/`setup.cfg`,
  requirements/constraints files, the `pypi` ecosystem token, and `pypi://`
  coordinates), so a Poetry-exported `requirements.txt` next to `poetry.lock`
  resolves to Poetry instead of failing closed as conflicting managers. The
  duplicate-inventory ecosystem token is the registry-level `pypi` for every
  Python manager. Constraints pins, direct pins of transitives, uv
  `override-dependencies`/`constraint-dependencies`, hand-edited lockfiles
  (`lockfile_override`), and VCS/URL/path/editable installs plus
  `[tool.uv.sources]` redirects (`source_override`) are forced-mediation
  overrides; Python replacements are exact `name==version` PEP 440 pins; and
  there is no Python removal or substitution construct, so
  `dependency_removal` and `dependency_substitution` are never claimable
  through Python mechanisms.

- Node.js dependency-graph safety audit for SCA remediation: npm, Yarn, and
  pnpm profiles on the shared kind-bucket engine, mechanism-driven like Gradle
  (`type` null, `<manager>.<construct>` in `mechanism`, required
  `semantic_effect`). Manager identity comes from lockfiles
  (`package-lock.json`/`npm-shrinkwrap.json`, `yarn.lock`/`.yarnrc*`,
  `pnpm-lock.yaml`/`pnpm-workspace.yaml`); `package.json`, the npm ecosystem
  token, and `npm://` coordinates are registry-family signals shared by all
  three, narrowed by the audit's declared manager and otherwise failing
  closed. The duplicate-inventory ecosystem token is the registry-level `npm`
  for every Node manager. First uses of the reserved `lockfile_override`
  (hand-edited lockfiles) and `source_override` (git/file/link/portal
  redirections) semantic effects; alias redirections require an exact bare
  `name@version` replacement; there is no Node removal construct, so
  `dependency_removal` is never claimable through Node mechanisms.

- Gradle dependency-graph safety audit for SCA remediation: mechanism-driven
  manipulations (`type` null, `gradle.<construct>` in `mechanism`, required
  `semantic_effect`) covering version catalogs, constraints, and platforms as
  native controls; enforcedPlatform, resolutionStrategy.force, forced direct
  dependencies, and rich-version rules as forced mediation; bare exclusions as
  blocking removals; and dependency substitutions and component metadata rules
  as replacement-requiring substitutions with configuration-scoped
  dependencyInsight plus runtime/linkage validation. Gradle detection uses
  ecosystem and build-file signals, with registry-level `mvn://` coordinates
  no longer treated as Maven-only evidence. A self-declared audit is validated
  even when every detection signal is unrecognizable, declared replacements
  must be exact `group:artifact` coordinates, deeply nested payload fields can
  no longer crash text coercion, and the manipulation walk is bounded so huge
  payloads cannot inflate the error list.

### Changed

- Extracted the Maven dependency-graph audit into a package-manager profile
  registry with a shared audit engine, preparing the seam for Gradle and later
  ecosystems, and added optional cross-ecosystem `semantic_effect` and
  `mechanism` manipulation fields to the SCA structured-output contract.
- Consolidated the Maven and Gradle audit instructions into one shared
  "Dependency Graph Safety Audit" section with a per-manager mechanism table
  and short per-manager exception lines, and defined transitive path depth
  normatively: the selected dependency path spans the selected package's full
  transitive closure (within the 12-coordinate cap), and pre-existing direct
  declarations of the selected package's transitive dependencies are audited
  rather than omitted as unrelated. Added one discriminating eval per manager
  family for the pre-existing-transitive-pin case.

### Fixed

- Closed two NuGet red-team findings, both engine-wide: `_manifest_basename`
  now strips trailing dots and spaces together in one pass the way Windows
  path resolution folds them (a `Service.csproj .` or `poetry.lock  ..  `
  disguise kept a residual trailing space, lost its strong signal, and let a
  smuggled conflicting manifest dodge the ambiguity fail-closed gate), and
  package-manager detection now reads `patch_plan[].file` as a manifest
  signal (scrubbing every other channel while pointing the patch plan at a
  real manifest previously skipped the dependency-graph audit entirely).
  The NuGet replacement pattern is also compiled ASCII-only so fullwidth
  lookalike digits cannot ride into an "exact" `package@version` pin.

- Closed two replay-confirmed emission gaps surfaced by the Go fix-forward
  substitution case: branch normalization now also replaces `+` with `-` (a
  Go `+incompatible` target version becomes `-incompatible`, keeping branch
  names inside the `remediation/sca/<package>-<target-version>` convention),
  and when no VersionUpgrade record backs the selected remediation the
  finding counters (`findings_fixed`, `finding_instances_fixed`,
  `unique_advisories_fixed`) are derived from the findings being remediated
  instead of being omitted.

- Closed two more red-team-confirmed fail-open seams found while hardening
  the Go profile, both engine-wide: ecosystem-token normalization now shares
  the manifest channel's NFKC + format-character folding, so a conflicting
  second-manager `inventory.key.ecosystem` disguised with a fullwidth
  lookalike or zero-width space can no longer slip past the ambiguity
  fail-closed gate; and the self-declared pass-through now tests the raw
  `manipulations` value instead of its list coercion, so a content-bearing
  manipulation emitted as a bare object or string (rather than an array) can
  no longer ride through unvalidated when the declared manager is
  unresolvable and the status is `unavailable`.

- Closed two more red-team-confirmed fail-open seams found while hardening
  the Python profiles, both engine-wide: manifest basename normalization now
  NFKC-folds compatibility lookalikes, removes zero-width/format characters,
  and ignores Windows-style trailing dots, so a disguised conflicting
  lockfile (`uv.lock` with a zero-width space, `uv.lock.`) can no longer
  dodge the ambiguity fail-closed gate or validate a wrong-manager audit;
  and the unavailable/`approved_low_risk` coupling is now enforced
  profile-independently, so the honest unsupported-manager pass-through
  (`unavailable`, no manipulations, unresolvable manager) can no longer
  accompany an `approved_low_risk` risk decision.

- Closed red-team-confirmed fail-open seams in the graph-safety gate: an
  audit whose declared `package_manager` resolves to no supported profile
  (null, case variants, aliases like `node`, or non-string values) now fails
  closed whenever the audit reports a non-unavailable status or any
  manipulations, instead of silently skipping validation when every detection
  signal is scrubbed; Node replacement coordinates must pin a full immutable
  semver (mutable dist-tags like `pkg@latest` and x-ranges like `pkg@1.x` are
  rejected); and whitespace-padded lockfile names still register as strong
  manager signals so conflicting lockfiles cannot dodge the ambiguity
  fail-closed gate.
- Required `change_requests[0].inventory.lookup_method` and `checked_at` to be
  filled (never null) even when the source-provider lookup is unavailable;
  live replays showed prompt-only hosts nulling both in the unavailable path,
  which the strict selection-plan contract rejects.
- Resolved a contract inconsistency between the risk solver and the
  selection-plan projection: the solver offered `approved_low_risk` when
  targeted validation ran in the current run, but the projection omits the
  `validation` records the deterministic gate needs to verify that claim, so
  the status was structurally unreachable at the plan gate (found by the first
  execution-enabled live replay). The canonical instructions now state the
  selection-plan ceiling is `approved_with_validation_required` even when
  validation already passed, with executed outcomes summarized in
  `risk_decision.reason`; `approved_low_risk` belongs to the apply and
  validate gates where `validation` entries are returned.
- Spelled out the override classification pairing in the canonical
  instructions: an unexplained or advisory-dodging forced mediation is
  `unverified` -> `blocked`, and `mediation_declared` never pairs with
  `blocked`; a live Node replay emitted the incoherent pair and the gate
  correctly rejected it.
- Pinned the manipulation `replacement` format in the canonical instructions
  to a bare `group:artifact[:version]` coordinate; a live replay emitted a
  `mvn://...@version` form that the deterministic coordinate check correctly
  rejects.
- Hardened Maven SCA remediation plans against unexplained direct dependency
  overrides and exclusions by requiring a bounded selected-path audit plus
  resolved-graph and targeted runtime/linkage evidence.
- Closed fail-open seams in the deterministic SCA graph-safety gate: exclusion
  classifications are now whitelist-constrained (a bare exclusion can no longer
  pass as `not_needed_verified` or `version_control` without evidence), the
  audit `status` and manipulation `type`/`classification` tokens are
  enum-checked, native control types cannot carry mediation classifications,
  every normalized output cap is enforced deterministically, and Maven
  detection now cross-checks manifests and coordinates instead of trusting the
  free-form inventory ecosystem string (which must be exactly `maven`).
- Documented the exact `dependency_graph_audit` JSON contract, enum vocabulary,
  and selection-plan gate statuses in the canonical instructions so prompt-only
  hosts emit contract-valid audits, and aligned the evidence-plan stop
  condition with the audit's dependency-path scope.
- Serialized compiled profile contracts in logical field order so shipped
  `profile-contracts/*.json` files round-trip through
  `profile_contract_from_dict` again.
- Closed second-round gate seams found by adversarial re-probe of the hardened
  validator: `selection_blocked` can no longer accompany an approved risk
  decision or a created/reused change request and any supplied audit is still
  validated; non-array audit containers now error instead of coercing to
  empty; the inventory ecosystem token must be literally `maven` (case and
  prefix variants rejected); Maven signals in `selected_option` now trigger
  the audit requirement; and payload-driven crashes were fixed (non-dict
  inventory candidates, deep-nesting recursion in branch collection, and
  non-serializable values in text coercion).
- Isolated the validation-isolation test fixtures from operator-level git
  configuration such as a global excludesFile that ignores `vendor/` paths.

## 2.2.1 - 2026-08-01

### Changed

- Removed unused private QA and backend telemetry evidence inputs from
  automated `ai-plugins` publication.

### Fixed

- Normalized Codex Plugins Directory skill metadata so generated submission
  packages pass OpenAI's text-normalization validation without manual ZIP edits.

## 2.2.0 - 2026-07-30

### Added

- Added the Codex Plugins Directory setup skill alongside all 11 workflow
  skills, with explicit local `endorctl` authentication and secret-handling
  guidance and no hosted MCP, connector, app, or plugin OAuth requirement.
- Added customer-owned Agent Policy Packs with a public JSON Schema, template
  and examples, `validate-policy-pack` and `evaluate-policy-pack` CLI commands,
  trusted fact preflight, and generated policy outputs across all source agents.
- Added an OpenAPI-derived Endor API resource and enum registry with a generator
  for validating source instructions, knowledge-pack query fields, and rendered
  `--field-mask` values.
- Added host-specific recommended model defaults with explicit customer override
  precedence across Claude, Codex, Gemini, Antigravity, Cursor, and portable hosts.

### Changed

- Projected complete package-level Claude Code, Codex, Cursor, and Antigravity
  installs into every public catalog agent. Each provider command installs the
  full Agent Kit, while incomplete package records fail closed and are omitted.
- Added byte-identical catalog categories for the 11 canonical agents across
  Remediation, Research & Investigate, Compliance, Troubleshooting, and
  Incident Response so the Endor UI can group agents consistently.
- Refreshed the public catalog descriptions for all 11 canonical agents to
  clarify scope, evidence, mutation boundaries, and approval requirements.
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
  v1.7.1088, retaining `ECOSYSTEM_VSCODE` registry coverage and the expanded
  Codex, Cursor, Gemini, and Antigravity install-host enum.
- Enhanced `findings-browser` with compact complete-count queries and
  `FINDING_TAGS_*` filters for exploited, fix-available, and reachable findings.
- Extended `malware-responder` to query tenant `FINDING_CATEGORY_MALWARE`
  evidence and distinguish Endor classifications from external intelligence.
- Extended `cicd-posture` to prefer Endor-ingested repository, CODEOWNERS, and
  tag-protection evidence before falling back to the read-only GitHub API.
- Prioritized exploited findings in `sca-remediation` before VersionUpgrade/UIA
  evidence selects an upgrade candidate.
- Routed generated Endor API commands through `endorctl agent api` with canonical
  agent identifiers so backend telemetry can attribute agent-originated calls.
- Made exact-SHA QA and backend telemetry release evidence advisory in the
  automated `ai-plugins` publication workflow while retaining strict manual
  validation.
- Added profile-aware execution bounds, compact evidence plans, and deterministic
  artifact summaries that avoid returning complete large inventories to the model.

### Fixed

- Removed stale mirror-root `manifest.json` files during `ai-plugins` sync so
  Codex directory validation uses the exact source manifest pinned in mirror
  provenance.
- Defaulted interactive agent responses to human-readable Markdown while
  preserving strict JSON for explicit machine-readable requests.
- Aligned Antigravity manifests and install commands with the documented
  `agy plugin` contract.
- Removed unsupported metadata from Cursor marketplace plugin entries and added
  a release gate that enforces Cursor's current `name`, `source`, and optional
  `description` entry contract.
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
  unavailable evidence and bounded-run defaults stay machine-readable.
- Hardened plugin hooks and disposable provider installations so all supported
  hosts load the canonical generated agents without competing workflow skills.
- Made SCA remediation inventory output deterministic across package, manifest,
  finding, and proposed change-request fields.

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

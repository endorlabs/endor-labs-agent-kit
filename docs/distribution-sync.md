# Distribution Sync

Use this guide when syncing generated Agent Kit artifacts into the public
`endorlabs/ai-plugins` distribution repo. Normal publication is automated by
`.github/workflows/publish-ai-plugins-pr.yml`; use the manual commands here as a
fallback or for local dry-run validation.

## Repo Boundary

| Repo | Owns |
| --- | --- |
| `endor-labs-agent-kit` | Source recipes, compiler/publisher code, guardrails, tests, provenance, generated catalog, and source documentation. |
| `ai-plugins` | Public host metadata, the unpacked Codex directory package, the official Claude root package, a self-contained Cursor marketplace package, Cursor SDK automation package, release-facing README, and checked-in distribution artifacts. |

Normal package sync copies source-owned host packages first. The mirror-only
provider boundary then reserves conventional root `agents/`, `skills/`, and
`hooks/` for Claude, while generating the complete Cursor package under
`plugins/cursor/endor-labs-agent-kit/`. Root
`.cursor-plugin/marketplace.json` keeps the stable `endorlabs` id and points to
that nested source; the mirror has no root `.cursor-plugin/plugin.json` and no
root `.mcp.json`. The root `CHANGELOG.md` is also synced so release notes travel
with generated distribution PRs.

## Automated Publication

After a maintainer merges an Agent Kit source PR to `main`, the publish workflow
validates Agent Kit, regenerates the catalog, verifies provenance, syncs the
generated distribution surfaces into `ai-plugins`, and opens or updates an
`ai-plugins` PR. This does not auto-increment package versions; maintainers bump
`pyproject.toml` intentionally when a release version should change.

Required GitHub secret in `endor-labs-agent-kit`:

```text
AI_PLUGINS_SYNC_TOKEN
```

The token must be a fine-grained PAT or GitHub App installation token with
`contents:write` and `pull-requests:write` on `endorlabs/ai-plugins`.

Real publication also requires two non-secret, sanitized JSON repository variables:

```text
AGENT_QA_ACCEPTANCE_JSON=<passing benchmark-acceptance.json>
ENDOR_AGENT_BACKEND_ACCEPTANCE_JSON=<passing backend telemetry acceptance bundle>
```

The first must bind its treatment arm to the exact publishing source SHA. The second must prove catalog schema v2, all canonical and legacy identities, attributed `endorctl agent api`, and Audit Log correlation. See `docs/backend-agent-telemetry-acceptance.md`. Manual `dry_run=true` validation does not require these variables and cannot publish.

Optional Endor Labs signing variables:

```text
ENDOR_ARTIFACT_SIGNING_ENABLED=true
ENDOR_NAMESPACE=<endor namespace>
ENDOR_ARTIFACT_NAME_PREFIX=github.com/endorlabs/ai-plugins/agent-kit-catalog-provenance
```

The workflow writes `provenance/agent-kit-catalog.intoto.json`,
`provenance/manifest.sha256`, `provenance/agent-kit-manifest.json`, and
`provenance/agent-kit-source.json` into the generated `ai-plugins` PR. When signing is
enabled, it signs the provenance bundle with the Endor Labs GitHub Action
signing flow and immediately verifies the signature with
`endorlabs/github-action/verify`. Signing and verification are skipped for
`dry_run=true`.

## Source Repo Regeneration

For an agent identity migration, confirm the target backend accepts catalog
wire schema v2 and resolves every `legacy_ids` entry before distributing the
new catalog. See `docs/agent-identity-migration.md`. Do not use generated
duplicate agents as an alias mechanism.

Run from the Agent Kit source repo:

```bash
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
python -m pytest -q
python scripts/smoke_test_provider_installations.py --root .
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
git diff --check
```

Use `PYTHONPATH=src python3 -m endor_agent_kit.cli ...` if the local console
script is not installed.

## Mirror Sync

Run from the `ai-plugins` repo after Agent Kit regeneration is clean. Set
`AGENT_KIT_REPO` to your local Endor Labs Agent Kit source checkout:

```bash
AGENT_KIT_REPO="/path/to/endor-labs-agent-kit"

python3 "$AGENT_KIT_REPO/scripts/sync_ai_plugins_distribution.py" \
  --source "$AGENT_KIT_REPO" \
  --target .
```

Do not copy the Agent Kit root `skills/create-endor-labs-agent/` helper into
`ai-plugins`. Do not treat root `GEMINI.md` as a Cursor package file or as an
installable Gemini extension manifest; Gemini CLI uses
`plugins/gemini/endor-labs-agent-kit/`. The sync script removes stale root
`gemini-extension.json` files from `ai-plugins` because the multi-host repo root
is not a Gemini extension root. The sync script copies `CHANGELOG.md`; update it
in Agent Kit source before opening a release-oriented distribution PR.

## Mirror Validation

Run from `ai-plugins`:

```bash
AGENT_KIT_REPO="/path/to/endor-labs-agent-kit"

for skill in skills/* plugins/cursor/endor-labs-agent-kit/skills/*; do
  python3 scripts/quick_validate.py "$skill"
done
python3 scripts/validate_mirror_provenance.py
python3 scripts/validate_marketplace_host_boundaries.py
python3 scripts/build_codex_directory_submission.py validate --root .
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool .cursor-plugin/marketplace.json >/dev/null
python3 -m json.tool plugins/cursor/endor-labs-agent-kit/.cursor-plugin/plugin.json >/dev/null
python3 -m json.tool cursor-sdk/agent_definitions.json >/dev/null
python3 -m json.tool hooks/hooks.json >/dev/null
python3 -m json.tool plugins/cursor/endor-labs-agent-kit/mcp.json >/dev/null
python3 -m json.tool plugins/cursor/endor-labs-agent-kit/hooks/hooks.json >/dev/null
python3 -m json.tool plugins/claude/endor-labs-agent-kit/hooks/hooks.json >/dev/null
python3 -m json.tool plugins/codex/endor-labs-agent-kit/hooks/hooks.json >/dev/null
python3 -m json.tool plugins/gemini/endor-labs-agent-kit/hooks/hooks.json >/dev/null
python3 -m json.tool plugins/antigravity/endor-labs-agent-kit/hooks.json >/dev/null
test ! -e plugins/claude/ai-plugins/hooks
for hook_script in hooks/*.sh plugins/*/*/hooks/*.sh; do
  bash -n "$hook_script"
done
python3 - <<'PY'
import py_compile

py_compile.compile("cursor-sdk/run_cursor_agent.py", cfile="/tmp/run_cursor_agent.pyc", doraise=True)
PY
test ! -e gemini-extension.json
test -f plugins/gemini/endor-labs-agent-kit/gemini-extension.json
test ! -e plugins/gemini/endor-labs-agent-kit.zip
test ! -e .cursor-plugin/plugin.json
test ! -e cursor/endor-labs-agent-kit
for provider in antigravity claude codex codex-directory gemini; do
  diff -qr "$AGENT_KIT_REPO/plugins/$provider" "./plugins/$provider"
done
diff -q "$AGENT_KIT_REPO/plugins/README.md" ./plugins/README.md
diff -qr "$AGENT_KIT_REPO/agents" ./plugins/cursor/endor-labs-agent-kit/agents
diff -qr "$AGENT_KIT_REPO/cursor-sdk" ./cursor-sdk
diff -qr "$AGENT_KIT_REPO/plugins/claude/endor-labs-agent-kit/agents" ./agents
diff -qr "$AGENT_KIT_REPO/plugins/claude/endor-labs-agent-kit/hooks" ./hooks
diff -qr "$AGENT_KIT_REPO/plugins/claude/endor-labs-agent-kit/skills" ./skills
diff -qr "$AGENT_KIT_REPO/hooks" ./plugins/cursor/endor-labs-agent-kit/hooks
diff -q "$AGENT_KIT_REPO/.mcp.json" ./plugins/cursor/endor-labs-agent-kit/mcp.json
diff -qr "$AGENT_KIT_REPO/assets" ./plugins/cursor/endor-labs-agent-kit/assets
test ! -e .mcp.json
for skill in "$AGENT_KIT_REPO"/skills/*; do
  name=${skill##*/}
  [ "$name" = "create-endor-labs-agent" ] && continue
  diff -qr "$skill" "./plugins/cursor/endor-labs-agent-kit/skills/$name"
done
diff -q "$AGENT_KIT_REPO/assets/logo.png" assets/logo.png
diff -q "$AGENT_KIT_REPO/CHANGELOG.md" CHANGELOG.md
git diff --check
```

Provider CLI validation is release-gated by availability of the relevant host
CLIs and public refs. Use `docs/plugin-release-checklist.md` for the full
release matrix.

## Claude And Cursor Marketplace Boundary

The official Anthropic entry retains the stable technical id
`ai-plugins@claude-plugins-official` and points at the generated mirror root.
`scripts/sync_ai_plugins_distribution.py` therefore generates a mirror-only
provider boundary after the normal package sync:

- `.claude-plugin/plugin.json`, which displays **Endor Labs Agent Kit** and
  relies on Claude's conventional component discovery;
- root `agents/`, `skills/`, and `hooks/`, which are byte-identical to the
  canonical Claude package and therefore expose Sonnet agents, setup, and
  Claude hook events;
- `plugins/cursor/endor-labs-agent-kit/`, a self-contained Cursor package with
  its own `.cursor-plugin/plugin.json`, Composer agents, skills, hooks,
  `mcp.json`, and assets;
- `.cursor-plugin/marketplace.json`, which keeps the stable `endorlabs` id and
  points to that nested package.

The mirror root intentionally has no `.mcp.json` or root Cursor plugin manifest.
Cursor receives the source-approved MCP config as conventional `mcp.json`
inside its package. Claude receives no Cursor agent, skill, hook, or MCP path;
Cursor receives no root Claude component path.

The overlay deliberately omits `version` so the upstream git SHA remains the
resolved plugin version. It must not be copied back over the Agent Kit source
repository's root guard. Validate it in the mirror with:

```bash
python3 scripts/validate_marketplace_host_boundaries.py
```

After a mirror release, Anthropic's scheduled SHA-bump automation can advance
the existing official entry through its validation and safety checks. Do not
submit a second official entry or request a slug rename for routine releases.

## Codex Directory Archive

Option A keeps only the unpacked directory under
`plugins/codex-directory/endor-labs-agent-kit/` in Git. After the mirror PR is
merged, manually dispatch `Build Codex directory submission` in `ai-plugins`
with the exact 40-character mirror commit SHA. The workflow checks out that
immutable commit, reads the pinned Agent Kit source SHA, validates every file
against `provenance/agent-kit-manifest.json`, and builds:

- `endor-labs-agent-kit-codex-directory-<version>.zip`
- the ZIP SHA-256 file
- a validation report
- a non-self-referential attestation containing both repository SHAs and all
  relevant package/archive digests

Leave `publish_release_assets=false` for validation. Set it to true with an
existing release tag only when release-asset publication is separately
authorized. The ZIP is never committed or reconstructed manually. See
`docs/codex-directory-submission.md` for the portal packet and external gates.

## Safety Notes

- Do not create or publish a Gemini zip artifact.
- Do not commit the Codex public-directory ZIP; build it only from an immutable
  `ai-plugins` SHA through the review-gated workflow.
- Do not enable both Claude package ids in the same profile for normal use.
- Do not enable the official `ai-plugins@claude-plugins-official` package with
  either Endor-hosted Claude id in the same profile.
- Do not couple Cursor package sync to Gemini CLI extension files.
- Do not add plugin-wide MCP unless a source decision and provider validation explicitly support it.
- The Agent Kit source root `.mcp.json` may declare the source-approved
  `endor-cli-tools` MCP server. In `ai-plugins`, mirror sync writes that config
  as `plugins/cursor/endor-labs-agent-kit/mcp.json` so the official Claude root
  does not auto-load it. Do not generate a root
  `gemini-extension.json`; Gemini discovers bundled skills from the installed
  extension root's `skills/` directory, and the repository root's `skills/`
  directory is the Claude setup surface in the mirror. Generated host package manifests
  under `plugins/*/endor-labs-agent-kit/` must still stay MCP-free unless that
  host package explicitly validates MCP. Setup guidance remains CLI-first and
  must not start, register, or rely on MCP without explicit user approval.
- Do not run live `endorctl agent api --agent-id <canonical-recipe-id>` smoke tests without explicit user approval and namespace provenance.

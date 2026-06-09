# Distribution Sync

Use this guide when syncing generated Agent Kit artifacts into the public
`endorlabs/ai-plugins` distribution repo. Normal publication is automated by
`.github/workflows/publish-ai-plugins-pr.yml`; use the manual commands here as a
fallback or for local dry-run validation.

## Repo Boundary

| Repo | Owns |
| --- | --- |
| `endor-labs-agent-kit` | Source recipes, compiler/publisher code, guardrails, tests, provenance, generated catalog, and source documentation. |
| `ai-plugins` | Public host metadata, Cursor package metadata, root Cursor agents and support skills, Cursor SDK automation package, release-facing README, and checked-in distribution artifacts. |

Normal package sync should make `ai-plugins/plugins/` byte-for-byte identical to
`endor-labs-agent-kit/plugins/`. Cursor package sync should make
`ai-plugins/.cursor-plugin/`, generated root workflow `agents/`, generated root
workflow `skills/`, and `assets/logo.svg` match this repo. Cursor SDK sync
should make `ai-plugins/cursor-sdk/` match this repo. The root `CHANGELOG.md`
is also synced so release notes travel with generated distribution PRs.

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

Optional Endor Labs signing variables:

```text
ENDOR_ARTIFACT_SIGNING_ENABLED=true
ENDOR_NAMESPACE=<endor namespace>
ENDOR_ARTIFACT_NAME_PREFIX=github.com/endorlabs/ai-plugins/agent-kit-catalog-provenance
```

The workflow writes `provenance/agent-kit-catalog.intoto.json` and
`provenance/manifest.sha256` into the generated `ai-plugins` PR. When signing is
enabled, it signs the provenance bundle with the Endor Labs GitHub Action
signing flow and immediately verifies the signature with
`endorlabs/github-action/verify`. Signing and verification are skipped for
`dry_run=true`.

## Source Repo Regeneration

Run from the Agent Kit source repo:

```bash
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
python -m pytest -q
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
`ai-plugins`. Do not treat root `GEMINI.md` or root `gemini-extension.json` as
Cursor package files; Gemini CLI uses `plugins/gemini/endor-labs-agent-kit/`.
The sync script copies `CHANGELOG.md`; update it in Agent Kit source before
opening a release-oriented distribution PR.

## Mirror Validation

Run from `ai-plugins`:

```bash
AGENT_KIT_REPO="/path/to/endor-labs-agent-kit"

for skill in skills/*; do python3 scripts/quick_validate.py "$skill"; done
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool .cursor-plugin/marketplace.json >/dev/null
python3 -m json.tool .cursor-plugin/plugin.json >/dev/null
python3 -m json.tool cursor-sdk/agent_definitions.json >/dev/null
python3 - <<'PY'
import py_compile

py_compile.compile("cursor-sdk/run_cursor_agent.py", cfile="/tmp/run_cursor_agent.pyc", doraise=True)
PY
python3 -m json.tool gemini-extension.json >/dev/null
test -f plugins/gemini/endor-labs-agent-kit/gemini-extension.json
test ! -e plugins/gemini/endor-labs-agent-kit.zip
diff -qr "$AGENT_KIT_REPO/plugins" ./plugins
diff -qr "$AGENT_KIT_REPO/.cursor-plugin" ./.cursor-plugin
diff -qr "$AGENT_KIT_REPO/agents" ./agents
diff -qr "$AGENT_KIT_REPO/cursor-sdk" ./cursor-sdk
for skill in "$AGENT_KIT_REPO"/skills/*; do
  name=${skill##*/}
  [ "$name" = "create-endor-labs-agent" ] && continue
  diff -qr "$skill" "./skills/$name"
done
diff -q "$AGENT_KIT_REPO/assets/logo.svg" assets/logo.svg
diff -q "$AGENT_KIT_REPO/CHANGELOG.md" CHANGELOG.md
git diff --check
```

Provider CLI validation is release-gated by availability of the relevant host
CLIs and public refs. Use `docs/plugin-release-checklist.md` for the full
release matrix.

## Safety Notes

- Do not create or publish a Gemini zip artifact.
- Do not enable both Claude package ids in the same profile for normal use.
- Do not couple Cursor package sync to Gemini CLI extension files.
- Do not add plugin-wide MCP unless a source decision and provider validation explicitly support it.
- The root `.mcp.json` file and root `gemini-extension.json` may declare the
  source-approved `endor-cli-tools` MCP server so users can opt into Endor MCP
  setup. The root Gemini manifest must point skills at
  `./plugins/gemini/endor-labs-agent-kit/skills`, not the root Cursor skills.
  Generated host package manifests under `plugins/*/endor-labs-agent-kit/` must
  still stay MCP-free unless that host package explicitly validates MCP. Setup
  guidance remains CLI-first and must not start, register, or rely on MCP without
  explicit user approval.
- Do not run live `endorctl api` smoke tests without explicit user approval and namespace provenance.

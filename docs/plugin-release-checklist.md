# Plugin Release Checklist

Use this checklist before publishing Endor Labs Agent Kit plugin packages and
SDK automation packages for Claude Code, Codex, Gemini CLI, Antigravity CLI,
Cursor, and Cursor SDK.

## Release Scope

Release all generated plugin packages together. Do not publish only one host
package for a normal v1 release.

Generated package roots:

- Claude Code: `plugins/claude/endor-labs-agent-kit/`
- Claude Code legacy compatibility: `plugins/claude/ai-plugins/`
- Codex: `plugins/codex/endor-labs-agent-kit/`
- Gemini CLI: `plugins/gemini/endor-labs-agent-kit/`
- Antigravity CLI: `plugins/antigravity/endor-labs-agent-kit/`
- Cursor: `.cursor-plugin/`, root generated `agents/`, root generated
  `skills/`, and `assets/logo.svg`
- Cursor SDK: `cursor-sdk/`

Generated marketplace and release files:

- Claude public marketplace: `.claude-plugin/marketplace.json`
- Claude local marketplace: `plugins/claude/.claude-plugin/marketplace.json`
- Codex public marketplace: `.agents/plugins/marketplace.json`
- Codex local marketplace: `plugins/codex/.agents/plugins/marketplace.json`
- Gemini manifest: `plugins/gemini/endor-labs-agent-kit/gemini-extension.json`
- Antigravity manifest: `plugins/antigravity/endor-labs-agent-kit/plugin.json`
- Cursor marketplace and manifest: `.cursor-plugin/marketplace.json`,
  `.cursor-plugin/plugin.json`
- Cursor SDK definitions: `cursor-sdk/agent_definitions.json`

## Version Gate

Use one release version across package manifests and the GitHub release tag.
Gemini CLI release docs recommend keeping `gemini-extension.json` version and
the GitHub release tag in sync.

Merging to `main` does not automatically bump the package version. The publish
workflow opens or updates an `ai-plugins` sync PR from the merged Agent Kit
commit; maintainers must intentionally update `pyproject.toml`, regenerate, and
review `CHANGELOG.md` when a release version changes.

For the current package version, use an exact tag that matches the generated
package version, not a `v`-prefixed tag, unless the generator and package
manifests are intentionally changed to emit a `v` prefix.

```bash
VERSION="$(python3 - <<'PY'
from pathlib import Path
import re

text = Path("pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
if not match:
    raise SystemExit("missing pyproject version")
print(match.group(1))
PY
)"
test "$VERSION" = "$(jq -r .version plugins/gemini/endor-labs-agent-kit/gemini-extension.json)"
test "$VERSION" = "$(jq -r .version plugins/antigravity/endor-labs-agent-kit/plugin.json)"
test "$VERSION" = "$(jq -r .version plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json)"
test "$VERSION" = "$(jq -r .version plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json)"
test "$VERSION" = "$(jq -r .version .cursor-plugin/plugin.json)"
test "$VERSION" = "$(jq -r .version cursor-sdk/agent_definitions.json)"
test "1.0.1" = "$(jq -r .version plugins/claude/ai-plugins/.claude-plugin/plugin.json)"
test -f CHANGELOG.md
```

## Generate

Regenerate source-owned artifacts from recipes:

```bash
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
```

Confirm the Gemini package is directory-only and no zip artifact exists:

```bash
test -f plugins/gemini/endor-labs-agent-kit/gemini-extension.json
test -f plugins/gemini/endor-labs-agent-kit/skills/endor-agent-kit-setup/SKILL.md
test ! -e plugins/gemini/endor-labs-agent-kit.zip
test -f .cursor-plugin/plugin.json
test -f agents/endor-agent-kit-setup-agent.md
test -f agents/endor-probe-droid-agent.md
test -f skills/endor-agent-kit-setup/SKILL.md
test -f skills/ai-sast-triage/architecture.svg
test -f cursor-sdk/README.md
test -f cursor-sdk/run_cursor_agent.py
test -f cursor-sdk/agent_definitions.json
test -f cursor-sdk/agents/endor-probe-droid-agent.md
```

## Repository Gates

Run these from the repository root:

```bash
pytest
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
git status --short --ignored plugins/gemini plugins/antigravity
```

The final status check must show the Gemini extension directory and
Antigravity package directory as tracked or untracked, not ignored. It must not
show a Gemini zip artifact.

## ai-plugins Publication

Normal `ai-plugins` publication is a generated PR from
`.github/workflows/publish-ai-plugins-pr.yml` after an Agent Kit maintainer
merge to `main`. The workflow validates source recipes, runs tests,
regenerates with `--include-plugins`, verifies guardrails and provenance, syncs
generated distribution surfaces with `scripts/sync_ai_plugins_distribution.py`,
and opens or updates the mirror PR.

Before release, verify:

- `AI_PLUGINS_SYNC_TOKEN` is configured with `contents:write` and
  `pull-requests:write` on `endorlabs/ai-plugins`.
- Endor signing variables are configured when signing is required:
  `ENDOR_ARTIFACT_SIGNING_ENABLED=true`, `ENDOR_NAMESPACE`, and optional
  `ENDOR_ARTIFACT_NAME_PREFIX`.
- Signing and signature verification are skipped for manual dry runs and both
  run for non-dry-run publication workflows when signing is enabled.
- The generated `ai-plugins` PR includes `provenance/agent-kit-catalog.intoto.json`
  and `provenance/manifest.sha256`.
- The generated `ai-plugins` PR includes the current `CHANGELOG.md`.
- The PR body links to the source Agent Kit commit and lists validation,
  manifest digest, and provenance bundle digest.

Use `docs/distribution-sync.md` only for local dry runs or manual fallback.

## Cursor

Local release validation:

```bash
python3 -m json.tool .cursor-plugin/marketplace.json >/dev/null
python3 -m json.tool .cursor-plugin/plugin.json >/dev/null
for agent in endor-agent-kit-setup-agent endor-ai-sast-triage-agent endor-troubleshooter-agent endor-probe-droid-agent endor-sca-remediation-agent; do
  test -f "agents/$agent.md"
done
for skill in ai-sast-triage endor-agent-kit-setup endor-troubleshooter probe-droid sca-remediation; do
  test -f "skills/$skill/SKILL.md"
done
for skill in ai-sast-triage endor-troubleshooter probe-droid sca-remediation; do
  test -f "skills/$skill/architecture.svg"
done
```

Cursor package files are generated at repository root because the public
package source is `./`. Keep Cursor validation separate from Gemini validation:
Cursor uses `.cursor-plugin/`, root `agents/`, and root `skills/`; Gemini uses
`plugins/gemini/endor-labs-agent-kit/GEMINI.md` and
`plugins/gemini/endor-labs-agent-kit/gemini-extension.json`.

## Cursor SDK

Local release validation:

```bash
python3 -m json.tool cursor-sdk/agent_definitions.json >/dev/null
python3 - <<'PY'
import py_compile

py_compile.compile("cursor-sdk/run_cursor_agent.py", cfile="/tmp/run_cursor_agent.pyc", doraise=True)
PY
test -f cursor-sdk/requirements.txt
for agent in endor-agent-kit-setup-agent endor-ai-sast-triage-agent endor-troubleshooter-agent endor-probe-droid-agent endor-sca-remediation-agent; do
  test -f "cursor-sdk/agents/$agent.md"
done
```

Cursor SDK runs require `CURSOR_API_KEY` and consume Cursor SDK billing. Do not
run local or cloud SDK smoke tests in release validation unless the requester
has approved the API-key use, target repository, namespace provenance, and any
possible agent side effects. Use the Cursor IDE plugin package for
customer-facing Cursor UX; use `cursor-sdk/` for automation, CI,
orchestration, and backend services.

## Claude Code

Local release validation:

```bash
claude plugin validate plugins/claude/endor-labs-agent-kit
claude plugin validate plugins/claude/ai-plugins
claude --plugin-dir plugins/claude/endor-labs-agent-kit
```

Inside Claude Code, validate the package-local marketplace from the repository
root:

```text
/plugin marketplace add ./plugins/claude
/plugin install endor-labs-agent-kit@endorlabs
/plugin install ai-plugins@endorlabs
/plugin list
/agents
/reload-plugins
```

`ai-plugins@endorlabs` is a legacy compatibility package for existing Claude
Code users. Do not enable both Claude plugin ids in the same profile for normal
use because they expose the same setup skill and agents.

Release notes and install docs must state that `ai-plugins@endorlabs` remains
available for existing users, `endor-labs-agent-kit@endorlabs` is preferred for
new installs, and the plugin does not auto-disable, uninstall, or edit Claude
settings for either id.

Public repository validation after tag push:

```text
/plugin marketplace add endorlabs/ai-plugins@<tag> --sparse .claude-plugin plugins/claude
/plugin install endor-labs-agent-kit@endorlabs
/plugin install ai-plugins@endorlabs
/plugin list
/agents
```

Direct public-repo installation does not require submitting to a website. Submit
to the Claude community marketplace only if Endor Labs wants discovery through
Anthropic's reviewed community catalog.

## Codex

Local release validation:

```bash
codex plugin marketplace add ./plugins/codex
codex plugin list --marketplace endor-labs-agent-kit
codex plugin add endor-labs-agent-kit@endor-labs-agent-kit
codex plugin remove endor-labs-agent-kit@endor-labs-agent-kit
```

Validate bundled custom-agent installation without touching the user's real
Codex home:

```bash
TMP_CODEX_HOME="$(mktemp -d)"
python3 plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py --status --codex-home "$TMP_CODEX_HOME"
python3 plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py --install --yes --codex-home "$TMP_CODEX_HOME"
python3 plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py --status --codex-home "$TMP_CODEX_HOME"
rm -rf "$TMP_CODEX_HOME"
```

Public repository validation after tag push:

```bash
codex plugin marketplace add endorlabs/ai-plugins --ref "$VERSION" --sparse .agents --sparse plugins/codex/endor-labs-agent-kit
codex plugin list --marketplace endor-labs-agent-kit
codex plugin add endor-labs-agent-kit@endor-labs-agent-kit
codex plugin remove endor-labs-agent-kit@endor-labs-agent-kit
```

Codex custom agents are installed by the setup skill from the plugin package.
The Codex plugin manifest intentionally does not declare an unsupported `agents`
field.

## Gemini CLI

Local release validation:

```bash
gemini extensions install /absolute/path/to/endor-labs-agent-kit/plugins/gemini/endor-labs-agent-kit --consent --skip-settings
gemini extensions list
gemini extensions uninstall endor-labs-agent-kit
gemini extensions list
```

Gemini CLI 0.44.1 may still show a folder trust prompt for local paths even with
`--consent`. Inspect the package source and approve only the expected generated
folder.

Create or update the GitHub release/tag without adding a Gemini zip asset:

```bash
gh release create "$VERSION" \
  --title "Endor Labs Agent Kit $VERSION" \
  --notes "Endor Labs Agent Kit plugin package release."
```

Public repository validation after the release exists:

```bash
gemini extensions install https://github.com/endorlabs/ai-plugins --ref "$VERSION"
gemini extensions list
gemini extensions uninstall endor-labs-agent-kit
```

Do not create or attach a Gemini zip artifact. Use the local extension
directory for local testing and the tagged GitHub repository for public release
installs.

## Antigravity CLI

Local release validation:

```bash
antigravity plugin validate plugins/antigravity/endor-labs-agent-kit
antigravity plugin install /absolute/path/to/endor-labs-agent-kit/plugins/antigravity/endor-labs-agent-kit
antigravity plugin list
antigravity plugin uninstall endor-labs-agent-kit
antigravity plugin list
```

Antigravity CLI currently validates a package directory with `plugin.json` at
the root. Keep Antigravity validation separate from Gemini extension validation:
Gemini uses `gemini-extension.json` and installs from the generated extension
directory or tagged GitHub repository, while Antigravity uses `plugin.json` and
installs from the generated plugin directory in v1.

## Documentation Freshness

Before each release, manually re-check these provider docs because marketplace,
manifest, and public GitHub install behavior can change:

Last checked for this checklist: 2026-06-07.

- Claude Code plugins: `https://code.claude.com/docs/en/plugins`
- Claude Code marketplaces: `https://code.claude.com/docs/en/plugin-marketplaces`
- Claude Code plugin reference: `https://code.claude.com/docs/en/plugins-reference`
- Codex plugins: `https://developers.openai.com/codex/plugins`
- Codex plugin build docs: `https://developers.openai.com/codex/plugins/build`
- Codex subagents: `https://developers.openai.com/codex/subagents`
- Gemini extension authoring: `https://geminicli.com/docs/extensions/writing-extensions/`
- Gemini extension release docs: `https://geminicli.com/docs/extensions/releasing/`
- Gemini subagents: `https://geminicli.com/docs/core/subagents/`
- Antigravity CLI plugins: `https://antigravity.google/docs/cli-plugins`
- Gemini CLI to Antigravity migration: `https://antigravity.google/docs/gcli-migration`
- Google transition announcement: `https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/`
- Cursor plugin schema and package examples: `https://github.com/cursor/plugins`
- Cursor Python SDK: `https://cursor.com/docs/sdk/python`
- Endor Labs `endorctl` install and auth: `https://docs.endorlabs.com/developers-api/cli/install-and-configure`
- Endor Labs `endorctl init`: `https://docs.endorlabs.com/developers-api/cli/commands/init`

Record the provider doc check date in the release notes.

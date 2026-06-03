# Plugin Release Checklist

Use this checklist before publishing Endor Labs Agent Kit plugin packages for
Claude Code, Codex, Gemini CLI, and Antigravity CLI.

## Release Scope

Release all generated plugin packages together. Do not publish only one host
package for a normal v1 release.

Generated package roots:

- Claude Code: `plugins/claude/endor-labs-agent-kit/`
- Claude Code legacy compatibility: `plugins/claude/ai-plugins/`
- Codex: `plugins/codex/endor-labs-agent-kit/`
- Gemini CLI: `plugins/gemini/endor-labs-agent-kit/`
- Antigravity CLI: `plugins/antigravity/endor-labs-agent-kit/`

Generated marketplace and release files:

- Claude public marketplace: `.claude-plugin/marketplace.json`
- Claude local marketplace: `plugins/claude/.claude-plugin/marketplace.json`
- Codex public marketplace: `.agents/plugins/marketplace.json`
- Codex local marketplace: `plugins/codex/.agents/plugins/marketplace.json`
- Gemini manifest: `plugins/gemini/endor-labs-agent-kit/gemini-extension.json`
- Antigravity manifest: `plugins/antigravity/endor-labs-agent-kit/plugin.json`

## Version Gate

Use one release version across package manifests and the GitHub release tag.
Gemini CLI release docs recommend keeping `gemini-extension.json` version and
the GitHub release tag in sync.

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
test "1.0.1" = "$(jq -r .version plugins/claude/ai-plugins/.claude-plugin/plugin.json)"
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

Last checked for this checklist: 2026-06-02.

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
- Endor Labs `endorctl` install and auth: `https://docs.endorlabs.com/developers-api/cli/install-and-configure`
- Endor Labs `endorctl init`: `https://docs.endorlabs.com/endorctl/commands/init/`

Record the provider doc check date in the release notes.

# Plugin Release Checklist

Use this checklist before publishing Endor Labs Agent Kit plugin packages for
Claude Code, Codex, and Gemini CLI.

## Release Scope

Release all generated plugin packages together. Do not publish only one host
package for a normal v1 release.

Generated package roots:

- Claude Code: `plugins/claude/endor-labs-agent-kit/`
- Codex: `plugins/codex/endor-labs-agent-kit/`
- Gemini CLI: `plugins/gemini/endor-labs-agent-kit/`

Generated marketplace and release files:

- Claude public marketplace: `.claude-plugin/marketplace.json`
- Claude local marketplace: `plugins/claude/.claude-plugin/marketplace.json`
- Codex public marketplace: `.agents/plugins/marketplace.json`
- Codex local marketplace: `plugins/codex/.agents/plugins/marketplace.json`
- Gemini release archive: `plugins/gemini/endor-labs-agent-kit.zip`

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
test "$VERSION" = "$(jq -r .version plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json)"
test "$VERSION" = "$(jq -r .version plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json)"
```

## Generate

Regenerate source-owned artifacts from recipes:

```bash
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
```

Confirm the generated zip is tracked and rooted correctly:

```bash
python3 - <<'PY'
from pathlib import Path
import zipfile

archive_path = Path("plugins/gemini/endor-labs-agent-kit.zip")
with zipfile.ZipFile(archive_path) as archive:
    names = set(archive.namelist())
assert "gemini-extension.json" in names
assert "skills/endor-agent-kit-setup/SKILL.md" in names
assert not any(name.startswith("endor-labs-agent-kit/") for name in names)
print("Gemini archive OK")
PY
```

## Repository Gates

Run these from the repository root:

```bash
pytest
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
git status --short --ignored plugins/gemini
```

The final status check must show `plugins/gemini/endor-labs-agent-kit.zip` as
tracked or untracked, not ignored.

## Claude Code

Local release validation:

```bash
claude plugin validate plugins/claude/endor-labs-agent-kit
claude --plugin-dir plugins/claude/endor-labs-agent-kit
```

Inside Claude Code, validate the package-local marketplace from the repository
root:

```text
/plugin marketplace add ./plugins/claude
/plugin install endor-labs-agent-kit@endor-labs-agent-kit
/plugin list
/agents
/reload-plugins
```

Public repository validation after tag push:

```text
/plugin marketplace add endorlabs/endor-labs-agent-kit@<tag> --sparse .claude-plugin plugins/claude
/plugin install endor-labs-agent-kit@endor-labs-agent-kit
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
codex plugin marketplace add endorlabs/endor-labs-agent-kit --ref "$VERSION" --sparse .agents --sparse plugins/codex/endor-labs-agent-kit
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

Create the GitHub release with the generated zip as the single generic Gemini
asset:

```bash
gh release create "$VERSION" plugins/gemini/endor-labs-agent-kit.zip \
  --title "Endor Labs Agent Kit $VERSION" \
  --notes "Endor Labs Agent Kit plugin package release."
```

Public repository validation after the release exists:

```bash
gemini extensions install https://github.com/endorlabs/endor-labs-agent-kit --ref "$VERSION"
gemini extensions list
gemini extensions uninstall endor-labs-agent-kit
```

Gemini CLI 0.44.1 does not install a local zip path directly. Use the local
extension directory for local testing and the GitHub release asset for public
release installs.

## Documentation Freshness

Before each release, manually re-check these provider docs because marketplace,
manifest, and release-asset behavior can change:

Last checked for this checklist: 2026-06-01.

- Claude Code plugins: `https://code.claude.com/docs/en/plugins`
- Claude Code marketplaces: `https://code.claude.com/docs/en/plugin-marketplaces`
- Claude Code plugin reference: `https://code.claude.com/docs/en/plugins-reference`
- Codex plugins: `https://developers.openai.com/codex/plugins`
- Codex plugin build docs: `https://developers.openai.com/codex/plugins/build`
- Codex subagents: `https://developers.openai.com/codex/subagents`
- Gemini extension authoring: `https://geminicli.com/docs/extensions/writing-extensions/`
- Gemini extension release docs: `https://geminicli.com/docs/extensions/releasing/`
- Gemini subagents: `https://geminicli.com/docs/core/subagents/`
- Endor Labs `endorctl` install and auth: `https://docs.endorlabs.com/developers-api/cli/install-and-configure`
- Endor Labs `endorctl init`: `https://docs.endorlabs.com/endorctl/commands/init/`

Record the provider doc check date in the release notes.

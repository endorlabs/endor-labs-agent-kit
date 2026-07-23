# Plugin Release Checklist

Use this checklist before publishing Endor Labs Agent Kit plugin packages and
SDK automation packages for Claude Code, Codex, Gemini CLI, Antigravity CLI,
Cursor, and Cursor SDK.

## Release Scope

Release all generated plugin packages together. Do not publish only one host
package for a normal release.

Generated package roots:

- Claude Code: `plugins/claude/endor-labs-agent-kit/`
- Claude Code legacy compatibility: `plugins/claude/ai-plugins/`
- Codex: `plugins/codex/endor-labs-agent-kit/`
- Codex public directory: `plugins/codex-directory/endor-labs-agent-kit/`
- Gemini CLI: `plugins/gemini/endor-labs-agent-kit/`
- Antigravity CLI: `plugins/antigravity/endor-labs-agent-kit/`
- Cursor: `.cursor-plugin/`, root generated `agents/`, root generated
  `skills/`, root advisory `hooks/`, and `assets/logo.png`
- Cursor SDK: `cursor-sdk/`

Generated marketplace and release files:

- Claude public marketplace: `.claude-plugin/marketplace.json`
- Claude local marketplace: `plugins/claude/.claude-plugin/marketplace.json`
- Codex public marketplace: `.agents/plugins/marketplace.json`
- Codex local marketplace: `plugins/codex/.agents/plugins/marketplace.json`
- Codex directory manifest: `plugins/codex-directory/endor-labs-agent-kit/.codex-plugin/plugin.json`
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
test "$VERSION" = "$(jq -r .version plugins/codex-directory/endor-labs-agent-kit/.codex-plugin/plugin.json)"
test "$VERSION" = "$(jq -r .version .cursor-plugin/plugin.json)"
test "$VERSION" = "$(jq -r .version cursor-sdk/agent_definitions.json)"
test "1.2.0" = "$(jq -r .version plugins/claude/ai-plugins/.claude-plugin/plugin.json)"
test -f plugins/claude/endor-labs-agent-kit/hooks/hooks.json
test ! -e plugins/claude/ai-plugins/hooks
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
test -f agents/endor-cicd-posture-agent.md
test -f agents/endor-malware-responder-agent.md
test -f agents/endor-findings-browser-agent.md
test -f agents/endor-configuration-automation-agent.md
test -f skills/endor-agent-kit-setup/SKILL.md
test -f skills/ai-sast-remediation/architecture.svg
test -f skills/findings-browser/architecture.svg
test -f skills/malware-responder/architecture.svg
test -f cursor-sdk/README.md
test -f cursor-sdk/run_cursor_agent.py
test -f cursor-sdk/agent_definitions.json
test -f cursor-sdk/agents/endor-findings-browser-agent.md
test -f cursor-sdk/agents/endor-cicd-posture-agent.md
test -f cursor-sdk/agents/endor-malware-responder-agent.md
test -f cursor-sdk/agents/endor-configuration-automation-agent.md
python3 scripts/build_codex_directory_submission.py validate --root .
test ! -e dist/endor-labs-agent-kit-codex-directory-"$VERSION".zip
```

## Repository Gates

For releases containing an agent rename or consolidation:

- confirm the Endor backend accepts catalog wire schema v2 and `legacy_ids`
- confirm all nine legacy identifiers resolve to their canonical agents
- confirm only the 11 canonical agents are visible
- verify host installs and telemetry use canonical identifiers
- follow the rollout and rollback contract in `docs/agent-identity-migration.md`

Run these from the repository root:

```bash
pytest
python scripts/check_repository_hygiene.py
python scripts/smoke_test_provider_installations.py --root .
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
endor-agent-kit verify-endor-context --upstream
git status --short --ignored plugins/gemini plugins/antigravity
```

For a real source-to-mirror publish, also require both release evidence bundles:

- private QA `benchmark-acceptance.json` with a passing frozen timing and semantic-quality gate whose treatment commit is the exact 40-character publishing source SHA;
- backend telemetry acceptance conforming to `schemas/backend-agent-telemetry-acceptance.schema.json`, including all canonical IDs, all legacy aliases, attributed `endorctl agent api` transport, and passing Audit Log correlation.

Validate the pair with `scripts/validate_release_evidence.py`; see `docs/backend-agent-telemetry-acceptance.md`. A missing or stale bundle blocks publication. A manual `dry_run=true` may regenerate and validate packages, but cannot publish.

The final status check must show the Gemini extension directory and
Antigravity package directory as tracked or untracked, not ignored. It must not
show a Gemini zip artifact.

If `verify-endor-context --upstream` fails with OpenAPI SHA drift, inspect
`source/endor-knowledge-pack/query-recipes.yaml`, affected Source Recipes,
workflow output contracts, and setup guidance before refreshing
`source/endor-context/provenance.json` and
`source/endor-context/openapiv2.swagger.json`. If it fails with docs URL drift,
update stale links first, then run:

```bash
endor-agent-kit refresh-endor-context
endor-agent-kit verify-endor-context --upstream
python -m pytest -q tests/test_endor_context.py
python scripts/generate_endor_api_registry.py --check --spec source/endor-context/openapiv2.swagger.json
```

The scheduled `Refresh Endor context` workflow is signal-only. It refreshes and
validates the pin in the runner, but it does not push a branch or create a PR.
If it reports drift, refresh locally, inspect the affected prompts and docs, and
commit the updated provenance through the normal signed PR process.

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
- The generated `ai-plugins` PR includes `provenance/agent-kit-catalog.intoto.json`,
  `provenance/manifest.sha256`, `provenance/agent-kit-manifest.json`, and
  `provenance/agent-kit-source.json`.
- The generated `ai-plugins` PR includes the current `CHANGELOG.md`.
- The PR body links to the source Agent Kit commit and lists validation,
  manifest digest, and provenance bundle digest.
- `python scripts/validate_mirror_provenance.py` passes in the generated mirror.
- The package version and `agents-v<version>` tag are new and unused. Never move
  or reuse a published catalog tag; the existing `2.1.0` package version must be
  intentionally advanced before the next release.

Use `docs/distribution-sync.md` only for local dry runs or manual fallback.

## Cursor

Local release validation:

```bash
python3 -m json.tool .cursor-plugin/marketplace.json >/dev/null
python3 -m json.tool .cursor-plugin/plugin.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path

definitions = json.loads(Path("cursor-sdk/agent_definitions.json").read_text(encoding="utf-8"))
for agent in definitions["agents"]:
    agent_name = agent["agent_name"]
    skill_id = agent["id"]
    assert Path("agents", f"{agent_name}.md").is_file(), agent_name
    assert Path("skills", skill_id, "SKILL.md").is_file(), skill_id
PY
test -f skills/ai-sast-remediation/architecture.svg
test -f skills/findings-browser/architecture.svg
test -f skills/malware-responder/architecture.svg
test -f skills/sca-remediation/actions.yaml
```

Cursor package files are generated at repository root because the public
package source is `./`. Keep Cursor validation separate from Gemini validation:
Cursor uses `.cursor-plugin/`, root `agents/`, root `skills/`, root advisory
`hooks/`, and `assets/logo.png`; Gemini uses
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
python3 - <<'PY'
import json
from pathlib import Path

definitions = json.loads(Path("cursor-sdk/agent_definitions.json").read_text(encoding="utf-8"))
for agent in definitions["agents"]:
    agent_name = agent["agent_name"]
    prompt_file = Path("cursor-sdk", agent["prompt_file"])
    assert prompt_file.is_file(), prompt_file
    for suffix in ("architecture.svg", "actions.yaml"):
        companion = Path("cursor-sdk", "agents", f"{agent_name}.{suffix}")
        source_companion = Path("skills", agent["id"], suffix)
        if source_companion.exists():
            assert companion.is_file(), companion
PY
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
python scripts/smoke_test_provider_installations.py --root . --require-claude-cli-validation
claude --plugin-dir plugins/claude/endor-labs-agent-kit
```

The disposable smoke script validates the supported Claude package and a
guard-only temporary copy of the repository-root manifest. Directly running
`claude plugin validate .` validates the root marketplace, not that guard
manifest.

The repository-root Claude manifest is a guard, not a supported workflow
package. Confirm its `SessionStart` warning and `UserPromptSubmit` block direct
users to `plugins/claude/endor-labs-agent-kit`; it must never expose a
Composer-backed Cursor agent.

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

Validate bundled custom-agent and skill installation without touching the user's
real Codex home or user skills directory:

```bash
TMP_CODEX_HOME="$(mktemp -d)"
TMP_CODEX_SKILLS_HOME="$(mktemp -d)"
python3 plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py --status --agents-only --codex-home "$TMP_CODEX_HOME"
python3 plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py --install --agents-only --yes --codex-home "$TMP_CODEX_HOME"
python3 plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py --status --agents-only --codex-home "$TMP_CODEX_HOME"
python3 plugins/codex/endor-labs-agent-kit/scripts/install_codex_agents.py --install --skills-only --yes --codex-home "$TMP_CODEX_HOME" --skills-home "$TMP_CODEX_SKILLS_HOME"
rm -rf "$TMP_CODEX_HOME" "$TMP_CODEX_SKILLS_HOME"
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
field. Before that approval, the plugin must expose only `endor-agent-kit-setup`;
the workflow skills under `bundled-skills/` are explicit fallbacks and must not
compete with named custom-agent delegation.

### Codex public directory

The public-directory package is separate from the repository/CLI package.
Validate its unpacked tree in Agent Kit and the generated mirror:

```bash
python3 scripts/build_codex_directory_submission.py validate --root .
```

After the `ai-plugins` mirror PR is merged, dispatch `Build Codex directory
submission` with the exact immutable 40-character mirror SHA. Keep
`publish_release_assets=false` for the first proof run. Verify that the workflow
artifact contains one plugin-root ZIP, checksum, validation report, and
attestation; the attestation must name both the Agent Kit and `ai-plugins` SHAs.
Only then, under separate release authorization, attach those same files to an
existing release or upload the ZIP to the OpenAI portal. Never commit the ZIP.
Complete the external publisher, permission, URL, reviewer-fixture, and test-case
gates in `docs/codex-directory-submission.md` immediately before submission.

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

As of 2026-06-16, Google documents that Gemini CLI access for unpaid, Google
One, Google AI Pro, and Google AI Ultra consumer users transitions to
Antigravity CLI on 2026-06-18. Keep Gemini package validation in the release
gate for supported enterprise/API-key users and extension compatibility, and
also run the Antigravity validation below as the forward-path CLI check for
affected consumer users.

Create or update the GitHub release/tag without adding a Gemini zip asset:

```bash
gh release create "$VERSION" \
  --title "Endor Labs Agent Kit $VERSION" \
  --notes "Endor Labs Agent Kit plugin package release."
```

Public repository validation after the release exists:

```bash
git clone --depth 1 --branch "$VERSION" https://github.com/endorlabs/ai-plugins ai-plugins-gemini-release
gemini extensions install ./ai-plugins-gemini-release/plugins/gemini/endor-labs-agent-kit
gemini extensions list
gemini extensions uninstall endor-labs-agent-kit
```

Do not create or attach a Gemini zip artifact. Use the local extension
directory for local testing. For public release installs, clone the tagged
GitHub repository and install the generated extension directory, not the
multi-host repository root.

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
installs from the generated plugin directory.

## Documentation Freshness

Before each release, manually re-check these provider docs because marketplace,
manifest, and public GitHub install behavior can change:

Last checked for this checklist: 2026-06-16.

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
- Endor Labs REST API authentication: `https://docs.endorlabs.com/developers-api/rest-api/authentication`
- Endor Labs API query builder: `https://docs.endorlabs.com/developers-api/rest-api/api-query-builder`

Record the provider doc check date in the release notes.

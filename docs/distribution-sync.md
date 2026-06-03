# Distribution Sync

Use this guide when syncing generated Agent Kit artifacts into the public
`endorlabs/ai-plugins` distribution repo.

## Repo Boundary

| Repo | Owns |
| --- | --- |
| `endor-labs-agent-kit` | Source recipes, compiler/publisher code, guardrails, tests, provenance, generated catalog, and source documentation. |
| `ai-plugins` | Public host metadata, root skill-compatible package, release-facing README, and checked-in distribution artifacts. |

Normal package sync should make `ai-plugins/plugins/` byte-for-byte identical to
`endor-labs-agent-kit/plugins/`.

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

Run from the `ai-plugins` repo after Agent Kit regeneration is clean:

```bash
rsync -a --delete /Users/mattbrown/AURI/endor-labs-agent-kit/plugins/ ./plugins/
cp /Users/mattbrown/AURI/endor-labs-agent-kit/.claude-plugin/marketplace.json .claude-plugin/marketplace.json
cp /Users/mattbrown/AURI/endor-labs-agent-kit/.agents/plugins/marketplace.json .agents/plugins/marketplace.json
```

Refresh the root Cursor/root skill-compatible package only from the generated
common skill package, preserving the root host wording in `README.md`,
`GEMINI.md`, `gemini-extension.json`, `.cursor-plugin/`, and `skills/`.

## Mirror Validation

Run from `ai-plugins`:

```bash
for skill in skills/*; do python3 scripts/quick_validate.py "$skill"; done
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
python3 -m json.tool .agents/plugins/marketplace.json >/dev/null
python3 -m json.tool .cursor-plugin/marketplace.json >/dev/null
python3 -m json.tool .cursor-plugin/plugin.json >/dev/null
python3 -m json.tool gemini-extension.json >/dev/null
test -f plugins/gemini/endor-labs-agent-kit/gemini-extension.json
test ! -e plugins/gemini/endor-labs-agent-kit.zip
diff -qr /Users/mattbrown/AURI/endor-labs-agent-kit/plugins ./plugins
git diff --check
```

Provider CLI validation is release-gated by availability of the relevant host
CLIs and public refs. Use `docs/plugin-release-checklist.md` for the full
release matrix.

## Safety Notes

- Do not create or publish a Gemini zip artifact.
- Do not enable both Claude package ids in the same profile for normal use.
- Do not add plugin-wide MCP unless a source decision and provider validation explicitly support it.
- Do not run live `endorctl api` smoke tests without explicit user approval and namespace provenance.

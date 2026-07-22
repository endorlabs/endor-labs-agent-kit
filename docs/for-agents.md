# For Agents

Use this guide when an AI agent is installing, reviewing, editing, or publishing
Endor Labs Agent Kit. It is intentionally explicit about source ownership and
approval gates.

## Decide The Job

| User Intent | Work In | Do Not Start By Editing |
| --- | --- | --- |
| Install a package | `plugins/<host>/endor-labs-agent-kit/README.md` | `source/`, `src/`, `tests/` |
| Install the Cursor package | `.cursor-plugin/`, root `agents/`, root `skills/`, root `hooks/`, and `assets/logo.png` | Gemini extension files or generated package internals |
| Run Cursor SDK automation | `cursor-sdk/README.md` | Cursor IDE plugin metadata or Gemini extension files |
| Install one agent | `<host>/<agent>/README.md` | `source/agents/<agent>/` |
| Change agent behavior | `source/agents/<agent>/recipe.yaml`, `instructions.md`, evals, `architecture.svg`, and `actions.yaml` when schema v2 mutating or explicitly adapter-backed | Generated host directories |
| Change generated docs or package shape | `src/endor_agent_kit/publication/` and tests | Installed plugin cache copies |
| Propose or create a new agent | `docs/contributing-agents.md` and `source/agents/<agent>/` | `ai-plugins` |
| Publish or mirror packages | `docs/plugin-release-checklist.md` and `docs/distribution-sync.md` | `ai-plugins` generated packages before source regeneration |

## Source Of Truth

Agent behavior is source-owned by:

- `source/agents/<agent>/recipe.yaml`
- `source/agents/<agent>/instructions.md`
- `source/agents/<agent>/actions.yaml` when present
- `source/agents/<agent>/evals/cases.yaml`
- `source/agents/<agent>/architecture.svg`
- publication templates in `src/endor_agent_kit/publication/`

Generated files under `claude-code/`, `claude-managed-agents/`, `codex/`,
`gemini/`, `portable/`, `plugins/`, `.cursor-plugin/`, generated root
workflow `agents/`, generated root workflow `skills/`, generated root advisory
`hooks/`, `cursor-sdk/`, `assets/logo.png`, `manifest.json`, and root `README.md` are
outputs. Change the source, regenerate, then review the generated diff.

## Install Without Drift

When installing generated artifacts:

1. Read the generated README in the selected host or package directory.
2. Copy the generated prompt, skill, agent, YAML, or bundle files exactly.
3. Keep sibling support files such as `architecture.svg`, `actions.yaml`,
   `agent.manifest.json`, `output-contract.md`, and `endorctl-setup.md` with the
   artifact when the README lists them.
4. Do not summarize, rewrite, or merge generated prompts.
5. Report any missing Endor auth, namespace, `gh`, MCP, `endorctl`, host CLI, or
   runtime prerequisite before live Endor work.

## Edit Safely

Use this command sequence after source edits:

```bash
python -m pytest -q -m "not publication and not release"
endor-agent-kit validate source/agents/<agent>/recipe.yaml
endor-agent-kit doctor-new-agent source/agents/<agent>/recipe.yaml
endor-agent-kit authoring-check source/agents/<agent>/recipe.yaml
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
python -m pytest -q -m "publication and not release"
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
endor-agent-kit verify-endor-context --upstream
git diff --check
```

Run `python -m pytest -q` for cross-lane changes and before release. The
release lane is available separately with `python -m pytest -q -m "release"`.

If the shell cannot run `endor-agent-kit`, use the local source package with
`PYTHONPATH=src python3 -m endor_agent_kit.cli ...`.

Use `doctor-new-agent` only when the change adds a new public agent under
`source/agents/<agent>/`. For docs-only changes, bug fixes, or existing-agent
edits, skip that command and run the validation commands that match the changed
surface.

## Approval Gates

Never collapse these into one broad approval:

- local file edits
- dependency or manifest changes
- validation command execution
- branch push
- PR/MR creation
- PR/MR comments
- ticket creation
- AppSec approval verification
- Endor exception-policy writes
- scan profile, integration, auth, or package-manager changes

Setup must not run scans, run `endorctl host-check`, install tools, edit shell
profiles, configure global MCP, or write credentials without explicit user
approval.

## External Evidence

Provider install behavior can drift. Before release, re-check the provider docs
listed in `docs/plugin-release-checklist.md`. Public install checks require a
pushed branch or tag. Live tenant lookup smoke tests require explicit approval
and must record namespace provenance.

## Public Distribution Boundary

[🐙 Endor Labs AI Plugins](https://github.com/endorlabs/ai-plugins/tree/main)
is the public distribution mirror. Normal package sync should be generated from
this repo and byte-for-byte identical for `plugins/`. Cursor mirror sync should
copy only `.cursor-plugin/`, generated root workflow `agents`, generated root
workflow `skills/`, generated root advisory `hooks/`, and `assets/logo.png`.
Cursor SDK mirror sync should copy `cursor-sdk/`. Do not copy root Gemini
compatibility manifests as Cursor package output; the multi-host repo root is
not a Gemini extension root. Use
`docs/distribution-sync.md` before editing or syncing that repo.

New agents, skills, hooks, and action contracts must be proposed and reviewed in
this source repo with `docs/contributing-agents.md`. After a maintainer merges
the source PR, the publish workflow opens the generated `ai-plugins` PR.

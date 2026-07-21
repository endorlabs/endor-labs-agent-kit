# Contributing Agents

Use this guide when proposing, reviewing, or merging new Endor Labs Agent Kit
agents, skills, hooks, action contracts, setup guidance, or host publication
changes.

## 🧭 Source And Publication Model

| Step | Repository | Owner | Output |
| --- | --- | --- | --- |
| 1. Propose | `endor-labs-agent-kit` | Contributor | Issue or PR with source recipe intent. |
| 2. Author | `endor-labs-agent-kit` | Contributor | Source files under `source/agents/<agent>/` plus tests/docs. |
| 3. Approve | `endor-labs-agent-kit` | Agent Kit maintainers | Maintainer-reviewed merge to `main`. |
| 4. Publish | `endor-labs-agent-kit` GitHub Actions | CI | Generated mirror branch and PR in `endorlabs/ai-plugins`. |
| 5. Distribute | `ai-plugins` | Distribution maintainers | Public generated package artifacts. |

New agents belong in `endor-labs-agent-kit`, not in `ai-plugins`. The
`ai-plugins` repo is the public distribution mirror. Its generated package
files should be changed only by the Agent Kit publish workflow or by the manual
fallback in `docs/distribution-sync.md`.

## ✅ Maintainer Controls

Configure repository protection so `main` in `endor-labs-agent-kit` requires:

- review from Agent Kit maintainers before merge
- passing Agent Kit CI
- generated catalog drift check
- guardrail and provenance checks
- no direct pushes except approved automation

Recommended protection for `ai-plugins`:

- generated sync PRs come from the Agent Kit workflow branch
  `agent-kit-sync/<source-sha>`
- distribution maintainers approve and merge generated sync PRs
- direct behavior edits in generated package files are rejected unless they are
  accompanied by the source Agent Kit PR that will reproduce them

## 🧱 What Contributors Can Change

| Contribution | Source location | PR template |
| --- | --- | --- |
| New agent | `source/agents/<agent>/` | `agent-source-change.md` |
| Existing agent behavior | `source/agents/<agent>/recipe.yaml`, `instructions.md`, evals, actions, diagram | `agent-source-change.md` |
| Skill or hook support | source recipe, setup support, action contract, publication code | `skill-hook-change.md` |
| Host package shape | `src/endor_agent_kit/publication/` and tests | `publication-workflow-change.md` |
| Mirror automation | `.github/workflows/`, `scripts/sync_ai_plugins_distribution.py`, docs | `publication-workflow-change.md` |

Use `.github/ISSUE_TEMPLATE/agent-proposal.md` when the agent idea needs review
before source files exist.

## 🧪 New Agent Checklist

A new public agent must include:

- `source/agents/<agent>/recipe.yaml`
- `source/agents/<agent>/instructions.md`
- `source/agents/<agent>/evals/cases.yaml`
- `source/agents/<agent>/architecture.svg`
- `source/agents/<agent>/actions.yaml` when the recipe is schema v2 mutating or
  explicitly adapter-backed, including PRs/MRs, comments, tickets, policies, or
  other side-effecting outputs
- tests or output-contract helpers when the agent returns structured data or
  renders review-facing artifacts
- sanitized examples with no customer names, user paths, tenant-specific config
  names, credentials, tokens, or private repository URLs

Run:

```bash
endor-agent-kit validate source/agents/<agent>/recipe.yaml
endor-agent-kit doctor-new-agent source/agents/<agent>/recipe.yaml
endor-agent-kit authoring-check source/agents/<agent>/recipe.yaml --new-agent
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
python -m pytest -q
python scripts/check_new_agent_authoring.py --base-ref origin/main --command endor-agent-kit
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
git diff --check
```

`doctor-new-agent` is the contributor-friendly local gate. It runs recipe
validation plus the stricter new-agent authoring checks, reports missing
`architecture.svg`, eval coverage, action-contract, transport, and source
layout issues, and prints the publish/test commands that should pass before the
Agent Kit PR is opened. The `scripts/check_new_agent_authoring.py` command is
the CI/base-ref companion: it only applies strict new-agent checks to recipes
that are newly added in the PR.

## 📇 Catalog Field Contract

Every recipe carries the fields the signed `catalog.json` (the `EndorAgent` wire
shape apiserver serves) is built from. `endor-agent-kit validate` enforces these
and blocks merge on failure:

| Recipe field | Catalog field | Rule |
| --- | --- | --- |
| `id` | `id` | kebab-case `^[a-z][a-z0-9-]{2,63}$`; canonical telemetry join key. Change only through the reviewed identity-migration contract below. |
| `legacy_ids` | `legacy_ids` | optional unique kebab-case aliases owned by exactly one canonical agent; must not overlap an active `id`. |
| `name` | `name` | non-empty. |
| `version` | `version` | non-empty semver; bump this for behavior changes (never rename `id`). |
| `audience` | `audience` | required; one of `appsec` or `developer` -- the persona surface the agent lists under. |
| `short_description` | `short_description` | required, non-empty; the catalog tile one-liner. |
| `description` | `description` | required; the long detail-view markdown (the existing `description`). |
| `authors` | `authors` | required, non-empty list of **display names only**; email/`@handle`/URL is rejected as PII. |
| `requires_endorctl` | `endorctl_min_version` | required version constraint (`>=`/`>` + full semver, e.g. `>=1.0.0`); the operator is stripped for the catalog. |

`install[]` is derived from the published layout for the `claude-code` and
`claude-managed` hosts; no recipe field is needed. `catalog.json` is a generated,
committed artifact covered by the drift check -- regenerate it with `publish`.

Catalog wire schema v2 carries `legacy_ids` so a backend can resolve an old
identifier to its canonical agent without publishing the old agent as a second
visible entry. Renames require backend alias support before the catalog is
released, an entry in `docs/agent-identity-migration.md`, and tests proving that
each alias has one owner. Consolidations must also document how the canonical
agent routes the former workflows without chaining the legacy agents.

The **merge gate** on `agents/**`-affecting PRs is:

- `endor-agent-kit validate` over every recipe (the field contract above)
- `endor-agent-kit check-id-stability --base-ref origin/<base>` -- fails if an id
  present on `main` is removed without becoming an explicit `legacy_ids` alias
- `CODEOWNERS` review on the recipes, validator, emitter, signing logic, release
  workflow, and pinned key

## 🔁 Automated ai-plugins PR Flow

The workflow `.github/workflows/publish-ai-plugins-pr.yml` runs after merges to
`main` that affect Agent Kit source, publication code, tests, assets, or the sync
workflow.

The workflow:

1. checks out `endor-labs-agent-kit`
2. validates all source recipes
3. runs tests
4. regenerates the catalog with `--include-plugins`
5. fails if generated artifacts drift from the merged source PR
6. verifies guardrails and manifest checksums
7. emits `dist/provenance/agent-kit-catalog.intoto.json`
8. builds `dist/agent-kit-catalog-provenance.tgz`
9. optionally signs the provenance bundle with Endor Labs artifact signing
10. verifies the Endor Labs artifact signature when signing is enabled
11. checks out `endorlabs/ai-plugins`
12. runs `scripts/sync_ai_plugins_distribution.py`
13. validates the mirror
14. opens or updates an `ai-plugins` PR

Required secret:

| Secret | Purpose |
| --- | --- |
| `AI_PLUGINS_SYNC_TOKEN` | Fine-grained token or GitHub App installation token with `contents:write` and `pull-requests:write` on `endorlabs/ai-plugins`. |

Optional repository variables:

| Variable | Purpose |
| --- | --- |
| `ENDOR_ARTIFACT_SIGNING_ENABLED=true` | Enables the Endor Labs signing step. |
| `ENDOR_NAMESPACE` | Endor namespace used by the signing action. |
| `ENDOR_ARTIFACT_NAME_PREFIX` | Optional artifact name prefix. Defaults to `github.com/endorlabs/ai-plugins/agent-kit-catalog-provenance`. |

Signing and signature verification are skipped when the workflow runs with
`dry_run=true`.

## 🔐 Provenance And Signing

Agent Kit already records per-artifact SHA256 digests in `manifest.json`.
`endor-agent-kit verify-provenance --catalog-root .` recomputes those digests.
`endor-agent-kit provenance-statement --catalog-root .` emits a deterministic
in-toto/SLSA-style statement whose subject is `manifest.json`.

The publish workflow treats the provenance bundle as the attestable artifact.
When Endor signing is enabled, it uses the Endor Labs GitHub Action signing
flow documented at
<https://docs.endorlabs.com/scan/containers/artifact-signing>. The official
Endor docs describe GitHub Actions signing with
`endorlabs/github-action/sign` and `endorctl artifact sign` as supported signing
paths. The workflow immediately verifies the signed artifact with
`endorlabs/github-action/verify` and
`certificate_oidc_issuer=https://token.actions.githubusercontent.com`.

For releases where Endor signing is not yet configured, the minimum required
provenance is:

- clean `endor-agent-kit verify-provenance`
- committed `manifest.json`
- generated `provenance/agent-kit-catalog.intoto.json` in the `ai-plugins` PR
- PR body with source commit, validation commands, manifest digest, and
  provenance bundle digest

## 🚫 Do Not

- create a new agent directly in `ai-plugins`
- hand-edit generated package files to change behavior
- merge Agent Kit source PRs without regenerated artifacts
- merge `ai-plugins` generated PRs that do not point back to a merged Agent Kit
  source commit
- add customer-specific paths, tenant names, credentials, or private repository
  URLs to examples
- treat optional Endor signing as a substitute for source review and generated
  drift checks

## 🧰 Manual Fallback

If the publish workflow is unavailable, use `docs/distribution-sync.md`. The
manual process must still produce:

- a clean Agent Kit source checkout
- regenerated Agent Kit artifacts
- passing tests, guardrails, and provenance verification
- mirror validation in `ai-plugins`
- a human-created `ai-plugins` PR that links to the merged Agent Kit commit

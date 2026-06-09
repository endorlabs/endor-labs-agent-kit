# Publication Workflow Change

## Scope

- Area: GitHub Actions / sync script / provenance / signing / distribution docs / release validation

## Required Guarantees

- [ ] Agent Kit remains the source of truth.
- [ ] `ai-plugins` receives generated distribution changes through a PR.
- [ ] Generated package changes are reproducible from `source/agents/` and publication code.
- [ ] Provenance still anchors `manifest.json` and generated artifact checksums.
- [ ] Signing or attestation configuration is opt-in unless the required Endor/GitHub credentials are configured.

## Validation

- [ ] `python -m pytest -q`
- [ ] `endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins`
- [ ] `endor-agent-kit check-guardrails --catalog-root .`
- [ ] `endor-agent-kit verify-provenance --catalog-root .`
- [ ] `python scripts/sync_ai_plugins_distribution.py --source . --target <ai-plugins-checkout> --dry-run`
- [ ] `git diff --check`

## Rollout

- [ ] Branch protection and maintainer review requirements were considered.
- [ ] Required secrets or repository variables are documented.
- [ ] Manual fallback process is documented.

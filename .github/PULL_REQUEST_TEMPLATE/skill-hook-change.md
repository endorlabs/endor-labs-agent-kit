# Skill, Hook, Or Agent Support Change

## Scope

- Related agent(s):
- Change type: skill / hook / setup guidance / action contract / eval / publication template / workflow

## Source Boundary

- [ ] This change lives in Agent Kit source, not in `ai-plugins` generated output.
- [ ] If this changes agent behavior, the related source recipe and instructions were updated.
- [ ] If this changes side effects, `actions.yaml` and approval-gate language were updated.
- [ ] If this changes generated package shape, publication code and tests were updated.

## Validation

- [ ] `endor-agent-kit validate source/agents/<agent>/recipe.yaml`
- [ ] `endor-agent-kit authoring-check source/agents/<agent>/recipe.yaml`
- [ ] `endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins`
- [ ] `python -m pytest -q`
- [ ] `endor-agent-kit check-guardrails --catalog-root .`
- [ ] `endor-agent-kit verify-provenance --catalog-root .`
- [ ] `git diff --check`

## Review Notes

- What should maintainers pay closest attention to?
- Does this require a corresponding `ai-plugins` generated PR after merge?

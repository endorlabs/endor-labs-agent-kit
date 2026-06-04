# Agent Source Change

## Scope

- Agent id:
- Change type: new agent / behavior update / host support / output contract / docs
- Related issue or proposal:

## Source Files

- [ ] `source/agents/<agent>/recipe.yaml`
- [ ] `source/agents/<agent>/instructions.md`
- [ ] `source/agents/<agent>/evals/cases.yaml`
- [ ] `source/agents/<agent>/architecture.svg`
- [ ] `source/agents/<agent>/actions.yaml` if side effects are declared
- [ ] Tests or output-contract helpers updated when behavior changed

## Safety And Review

- [ ] Safety class and mutations match the workflow.
- [ ] Approval gates are explicit for file edits, branch pushes, PR/MR creation, comments, tickets, and Endor policy writes.
- [ ] Secret, tenant, customer, and local-path examples are sanitized.
- [ ] Architecture diagram still matches the workflow boundaries.
- [ ] New agent used `endor-agent-kit authoring-check <recipe> --new-agent`.

## Generated Output

- [ ] Ran `endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins`.
- [ ] Reviewed generated host artifacts and package README output.
- [ ] Did not edit generated host artifacts as the source of truth.

## Validation

- [ ] `python -m pytest -q`
- [ ] `endor-agent-kit check-guardrails --catalog-root .`
- [ ] `endor-agent-kit verify-provenance --catalog-root .`
- [ ] `git diff --check`

## ai-plugins Publication

- [ ] I understand `ai-plugins` is updated by the post-merge publish workflow, not by this PR.

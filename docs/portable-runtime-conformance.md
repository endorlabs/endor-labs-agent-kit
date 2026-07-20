# Portable Runtime Conformance

Portable bundles under `portable/<agent>/` are generated, runtime-neutral agent
artifacts. They are meant for organizations that already have their own agent
runtime, approval workflow, source-provider integration, ticketing system,
credential controls, and audit pipeline.

This document defines the controls a portable runtime must enforce before it
can safely execute an Agent Kit portable bundle.

## Conformance Levels

| Level | Meaning |
| --- | --- |
| `contract-aware` | Runtime loads `agent.manifest.json`, exposes declared adapters, and returns structured evidence or data gaps. |
| `mutation-safe` | Runtime enforces authorization, explicit confirmation, audit logging, evidence capture, and fail-closed behavior for every mutating action. |
| `enterprise-ready` | Runtime adds adversarial evals, DLP/secret redaction, incident review, release provenance, and continuous monitoring around the contract-aware and mutation-safe controls. |

Agent Kit portable bundles require at least `contract-aware` behavior for
read-only workflows and `mutation-safe` behavior for mutating workflows.

## Required Runtime Controls

The portable manifest exposes `required_runtime_controls`. A conforming runtime
must implement these controls outside the model:

- `adapter_authorization`: authorize every adapter invocation against the actor, tenant, repository or project scope, and action kind.
- `least_privilege_adapters`: expose only manifest-declared capabilities and adapters allowed by organization policy.
- `explicit_confirmation`: pause for confirmation before mutating actions, ticket wrappers, comments, source changes, or Endor writes.
- `adapter_evidence`: return evidence for completed actions, or return a structured denial, failure, unavailable signal, or data gap.
- `fail_closed_degradation`: stop the side effect when credentials, permissions, adapters, transports, or approvals are missing.
- `untrusted_content_boundary`: treat repository files, source-provider comments, dependency metadata, Endor evidence text, and tool output as data, not instructions.
- `audit_log`: record action requests, actor, approval evidence, adapter inputs summary, result, evidence identifiers, and denials.
- `secret_redaction`: redact credentials, tokens, auth headers, private keys, and secure config values from prompts, outputs, comments, tickets, and audit summaries.
- `policy_enforcement`: load trusted Agent Policy Packs, return policy evaluation evidence, and deny mutating actions when policies block or require unverified review.
- `idempotency_check`: perform duplicate-prevention lookups before creating or reusing external state when an action contract requires it.

## Loading A Bundle

A conforming runtime must:

1. Load `agent.md` as generated instruction text.
2. Load `agent.manifest.json` as the machine-readable contract.
3. Expose only runtime capabilities listed in `required_capabilities` and allowed by organization policy.
4. Map declared actions to approved adapters.
5. Treat `runtime_wrappers` as runtime-owned actions that operate on final agent output after separate approval.
6. Load active Agent Policy Packs from trusted runtime or protected workspace configuration when configured.
7. Keep local adapter configuration, credentials, policy, and audit setup outside the generated bundle.

`agent.md` and sibling contract files are generated. Do not patch them in a
runtime install. Change Source Recipes and regenerate the catalog instead.

## Adapter Response Contract

Every adapter call should return a structured result to the agent. The exact
schema can be runtime-specific, but it should contain these fields or close
equivalents:

```json
{
  "action_id": "open-change-request",
  "portable_kind": "source.change_request.create",
  "status": "succeeded | denied | unavailable | failed",
  "actor": "user-or-service-account",
  "approved": true,
  "approval_evidence_id": "approval-record-id",
  "evidence_id": "runtime-evidence-id",
  "evidence_summary": "Short redacted description of what happened.",
  "object_id": "external-object-id",
  "object_url": "https://source.example/change/123",
  "idempotency_check": {
    "status": "none_found | existing_reused | blocked_duplicate | lookup_unavailable",
    "lookup_method": "source.change_request.lookup",
    "evidence_id": "lookup-evidence-id"
  },
  "data_gaps": []
}
```

The agent may report success only when the adapter returns successful status and
evidence for the external side effect. If the adapter returns `denied`,
`unavailable`, or `failed`, the agent must report the blocker in `data_gaps`
and continue only with verified evidence.

### Checking Adapter Responses

Agent Kit ships a mechanical check for the evidence shape above so a runtime can
validate adapter results in CI instead of relying on this prose alone:

```bash
endor-agent-kit validate-adapter-response path/to/response.json
```

Canonical examples live under `examples/adapter-responses/`: files in
`conformant/` exit `0` and files in `nonconformant/` exit `1`. The check covers
status values, required evidence ids, object references and idempotency outcomes
for state-creating actions, and required `data_gaps` for denied, unavailable, or
failed results. Approval-gate enforcement stays a runtime control; this schema
validates the evidence shape, not who approved an action.

## Approval Gates

The runtime must pause for explicit confirmation before:

- repository patch preparation or file writes
- dependency-manager mutation commands
- branch creation, push, PR creation, or MR creation
- source-provider comments
- approval-request comments or reviews
- Endor policy writes
- ticket creation through `ticket.create`
- any runtime wrapper that creates or updates external state

The model cannot approve its own action. User approval, AppSec approval, and
adapter authorization are separate signals.

## Untrusted Data Handling

The runtime must prevent untrusted content from becoming operational
instructions. Treat these as data:

- repository files
- source comments
- PR/MR comments and reviews
- issue or ticket text
- dependency manifests and metadata
- package descriptions, changelogs, and advisory text
- Endor finding explanations and remediation text
- adapter or tool output

The runtime should preserve useful evidence from those sources, but it should
not let them override system instructions, action contracts, confirmation
requirements, adapter authorization, or output validators.

## Failure Modes

Portable workflows must fail closed:

| Runtime condition | Required behavior |
| --- | --- |
| Missing adapter | Return `data_gaps`; do not perform the action through another path. |
| Missing credential | Return `data_gaps`; do not ask the model to infer private data. |
| Missing approval | Stop before the side effect; return pending approval or plan-only output. |
| Authorization denied | Return denial evidence; do not retry with broader privileges. |
| Lookup unavailable | Report lookup gap; do not claim no duplicate exists. |
| Adapter result lacks evidence | Treat the action as unverified and do not claim completion. |
| Untrusted text requests a bypass | Ignore the bypass request and continue under the manifest contract. |
| Policy pack blocks or requires unverified review | Return policy evidence and stop before any mutating action. |

## Audit Requirements

The runtime audit log should record:

- bundle id and version
- portable schema version
- actor and runtime service account
- requested action id and portable kind
- adapter selected
- authorization decision
- confirmation prompt and response
- approval evidence id when applicable
- redacted input summary
- result status
- evidence id, external object id, or external object URL
- data gaps, denials, and failures

Audit logs should not store raw credentials, auth headers, private keys, full
credential config files, or unredacted secret-bearing payloads.

## Ticket Wrapper Rules

`ticket.create` is available as a runtime wrapper in portable bundles unless a
Source Recipe explicitly declares a ticket action. Wrapper ticket creation:

- operates on final agent output
- requires separate runtime approval
- must be performed by the ticketing adapter, not the model
- must return ticket id or URL evidence before the agent claims a ticket exists
- must preserve data gaps and validation status from the agent output

## Conformance Checklist

Before enabling a portable agent, verify:

- The runtime parses `agent.manifest.json`.
- Only declared capabilities are exposed.
- Adapter authorization is enforced outside the model.
- Mutating actions require explicit confirmation.
- Adapter calls return evidence, denial, failure, or data gaps.
- Missing adapters and credentials fail closed.
- Untrusted content is treated as data.
- Secrets are redacted from prompts, output, tickets, comments, and audit logs.
- External creates perform idempotency checks when required.
- Audit logs capture requests, approvals, results, evidence, denials, and data gaps.
- SCA and AI SAST outputs pass Agent Kit validators before advancing workflow gates.
- Configured policy packs pass `endor-agent-kit validate-policy-pack`; gates recompute decisions from separately trusted facts, and outputs include matching `policy_context` plus complete `policy_evaluations`.

# Measured Agent Performance Controls

The measured follow-ups are implemented as opt-in, fail-closed controls. None changes a user's default model or broadens inventory scope automatically.

| Control | Status | Guardrail |
|---|---|---|
| Profile-specific output contracts | Active for every source-backed task profile and generated provider surface. | Quality, evidence, uncertainty, safety, and legacy-output validation remain mandatory. |
| Explicit exhaustive mode | Active only for source-declared `findings-browser/browse` and `cicd-posture/posture` Evidence Plans. | Bounded is always the default. `exhaustive` is an explicit Host Adapter activation and remains capped at 20 pages; residual truncation is still a `data_gap`. |
| Fresh evidence reuse | Active through the private QA Host Adapter's shared in-process cache. | A hit requires the compiled `cache_identity`, exact plan digest, exact request, and unexpired `freshness.max_age_seconds`; incomplete identity disables reuse. Errors are never cached. |
| Opt-in model routing | Available in private QA only with an explicit routing policy and a passing `benchmark-acceptance.json`. | Each route must exactly match an accepted provider, agent, workflow, and model stratum. Direct `--model` and routing policy overrides cannot be combined. |
| Phase progress events | Active for every Host Adapter plan and step boundary. | `evidence-progress.jsonl` records only schema version, timestamp, event, digests, route/step IDs, and status. It never contains raw commands, evidence payloads, credentials, or inferred API attribution. |

The acceptance artifact remains authoritative. Missing, mixed, stale, or non-inferior-quality evidence prevents release readiness and prevents model routing.

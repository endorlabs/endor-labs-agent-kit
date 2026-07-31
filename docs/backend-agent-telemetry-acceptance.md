# Backend Agent Telemetry Acceptance

Backend telemetry evidence is an optional release signal for canonical Agent
Kit identities. The backend team owns producing the bundle; Agent Kit only
validates it and never writes backend state.

The bundle must conform to `schemas/backend-agent-telemetry-acceptance.schema.json` and prove all of the following in the selected backend environment:

- catalog wire schema v2 is accepted;
- exactly the 11 canonical Agent Kit IDs are accepted;
- all nine `legacy_ids` resolve to their canonical owner;
- agent-originated Endor calls use `endorctl agent api`;
- Audit Log correlation observes `request_id`, `actor_type`, `canonical_agent_id`, and `on_behalf_of`;
- every canonical agent has at least one correlated sample.

Validate a backend bundle together with the private QA benchmark acceptance artifact:

```bash
python scripts/validate_release_evidence.py \
  --source-commit "$(git rev-parse HEAD)" \
  --qa-acceptance /path/to/benchmark-acceptance.json \
  --backend-acceptance /path/to/backend-agent-telemetry-acceptance.json
```

For automated source-to-mirror publication, maintainers may configure these
non-secret repository variables with the corresponding JSON objects:

- `AGENT_QA_ACCEPTANCE_JSON`
- `ENDOR_AGENT_BACKEND_ACCEPTANCE_JSON`

When both variables are configured, the publication workflow validates them and
reports the result. Missing, stale, mismatched-SHA, alias-incomplete, or
correlation-incomplete evidence produces a warning and does not block
publication. The standalone `scripts/validate_release_evidence.py` command
remains strict and returns a nonzero status for invalid evidence. A manual
`dry_run=true` may still regenerate and validate packages without publishing.

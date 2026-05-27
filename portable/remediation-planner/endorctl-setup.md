# endorctl Setup

The Remediation Planner artifact uses read-only Endor lookups through `endorctl api`.
Install and authenticate `endorctl` before using this artifact.

Required version: `>=1.0`

The recipe documents these read-only API invocation groups:

- `resolve_project_from_repository`
- `list_version_upgrade_recommendations`
- `get_version_upgrade_details`
- `get_finding_fixing_upgrades`

If `endorctl` is missing,
unauthenticated, or lacks access to a resource, the agent must record the
affected signal in `data_gaps` and continue with the evidence it already
gathered.

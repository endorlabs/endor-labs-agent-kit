# Remediation Planner Output Contract

This contract summarizes the structured inputs, outputs, runtime adapters, and optional mechanical gates for the portable bundle.

## Safety And Transports

- safety_class: `read_only`
- required_transports: `endorctl_api`
- endorctl_api_invocations: `resolve_project_from_repository`, `list_version_upgrade_recommendations`, `get_version_upgrade_details`, `get_finding_fixing_upgrades`
- required_endor_mcp_tools: `none`

## Inputs

- `namespace` (namespace, optional): Namespace
- `project_name` (string, optional): Optional human project selector such as owner/repo, repository name, Endor project name, or repository URL.
- `repository_url` (string, optional): Optional source repository URL when the runtime cannot infer it from repository context or session context.
- `project_uuid` (string, optional): Optional advanced fallback when project_name or repository_url cannot be resolved uniquely.
- `finding_uuid` (string, optional): Optional finding UUID
- `package_name` (string, optional): Optional package name

## Outputs

- `summary` (string, required): Concise result summary.
- `data_gaps` (list[string], required): Missing Endor, source, or runtime signals.

## Data Gaps

If an expected signal is unavailable because of credentials, account tier, runtime capabilities, source access, transport setup, or adapter failure, record that in `data_gaps` and continue only with verified evidence.

## Adapter Contracts

This Source Recipe declares no agent-owned side-effect actions.
Runtime wrappers such as `ticket.create` may operate on final output after separate approval.

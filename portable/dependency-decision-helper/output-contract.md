# Dependency Decision Helper Output Contract

This contract summarizes the structured inputs, outputs, runtime adapters, and optional mechanical gates for the portable bundle.

## Safety And Transports

- safety_class: `read_only`
- required_transports: `mcp`, `endorctl_api`
- endorctl_api_invocations: `lookup_package_version_uuid`, `get_package_scores`, `get_package_license`, `query_similar_packages`
- required_endor_mcp_tools: `check_dependency_for_risks`, `check_dependency_for_vulnerabilities`, `get_endor_vulnerability`

## Inputs

- `ecosystem` (string, required): Package ecosystem, such as npm, pypi, maven, go, cargo, gem, nuget, or packagist.
- `package_name` (string, required): Exact package name as it appears in a manifest.
- `version` (string, required): Exact package version to assess.

## Outputs

- `verdict` (enum, required): SAFE, SAFE_WITH_CONDITIONS, NOT_RECOMMENDED, or BLOCKED.
- `conditions` (list[string], required): Evidence-backed conditions that explain the verdict.
- `alternatives` (list[string], required): Safer package names or versions when available.
- `summary` (string, required): One-paragraph human-readable assessment.
- `data_gaps` (list[string], required): Signals that were unavailable because setup, auth, edition, or tooling was missing.

## Data Gaps

If an expected signal is unavailable because of credentials, account tier, runtime capabilities, source access, transport setup, or adapter failure, record that in `data_gaps` and continue only with verified evidence.

## Adapter Contracts

This Source Recipe declares no agent-owned side-effect actions.
Runtime wrappers such as `ticket.create` may operate on final output after separate approval.

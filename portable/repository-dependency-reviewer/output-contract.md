# Endor Labs Repository Dependency Reviewer Output Contract

This contract summarizes the structured inputs, outputs, runtime adapters, and optional mechanical gates for the portable bundle.

## Safety And Transports

- safety_class: `read_only`
- required_transports: `mcp`
- endorctl_api_invocations: `none`
- required_endor_mcp_tools: `check_dependency_for_risks`, `check_dependency_for_vulnerabilities`, `get_endor_vulnerability`

## Inputs

- `repository_path` (string, optional): Local repository path to inspect. Defaults to the current runtime workspace.
- `ecosystems` (list[string], optional): Optional ecosystem filter such as npm, pypi, maven, go, cargo, gem, nuget, or packagist.
- `focus` (string, optional): Optional review focus such as production dependencies, direct dependencies, critical findings, or newly added manifests.

## Outputs

- `risk_posture` (enum, required): LOW, MODERATE, HIGH, CRITICAL, or UNKNOWN.
- `manifests` (list[object], required): Manifest or lock files inspected with detected ecosystems and parsing notes.
- `dependencies_reviewed` (list[object], required): Exact dependency coordinates checked with Endor evidence.
- `findings` (list[object], required): Evidence-backed dependency risk findings with package, version, severity, and source file.
- `recommended_actions` (list[string], required): Follow-up actions such as upgrade, investigate reachability, or run a fuller Endor scan.
- `summary` (string, required): One-paragraph human-readable repository dependency review.
- `data_gaps` (list[string], required): Signals unavailable because a manifest was unsupported, versions were unresolved, tools failed, or Endor data was unavailable.

## Data Gaps

If an expected signal is unavailable because of credentials, account tier, runtime capabilities, source access, transport setup, or adapter failure, record that in `data_gaps` and continue only with verified evidence.

## Adapter Contracts

This Source Recipe declares no agent-owned side-effect actions.
Runtime wrappers such as `ticket.create` may operate on final output after separate approval.

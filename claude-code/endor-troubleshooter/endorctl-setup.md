# endorctl Setup

The Endor Troubleshooter artifact uses read-only Endor lookups through `endorctl api`.
Install and authenticate `endorctl` before using this artifact.

Required version: `>=1.0`

The recipe documents these read-only API invocation groups:

- `resolve_project_or_resource_selector`
- `list_scan_results`
- `get_scan_result`
- `list_scan_workflow_results`
- `get_scan_workflow_result`
- `list_scan_workflows`
- `list_scan_profiles`
- `list_package_versions`
- `list_package_manager_integrations`
- `list_scm_credentials`
- `list_installations`
- `list_identity_providers`
- `list_pr_comment_configs`
- `list_findings_and_policies`
- `list_call_graph_data`
- `inspect_container_registry_scan_evidence`
- `inspect_exporter_or_notification_evidence`

If `endorctl` is missing,
unauthenticated, or lacks access to a resource, the agent must record the
affected signal in `data_gaps` and continue with the evidence it already
gathered.

Endor Troubleshooter uses only read-only Endor lookups and redacted
user-provided issue text. It must not run scans, create scan log
requests, change credentials, edit scan profiles, update integrations,
post comments, open PRs/MRs, or mutate Endor state. Any such step
belongs in `future_action_contracts` for explicit follow-up approval.

# endorctl Setup

The Endor Troubleshooter artifact uses read-only Endor lookups through `endorctl api`.
Install and authenticate `endorctl` before using this artifact.

Required version: `>=1.0`

## Namespace Guardrails

Preserve normal environment-variable auth and namespace selection:
`ENDOR_NAMESPACE` and `ENDOR_API_CREDENTIALS_*` are supported inputs. Do not
allow silent namespace conflicts.

Read only the current process `ENDOR_NAMESPACE` and the `ENDOR_NAMESPACE` key
from the default `~/.endorctl/config.yaml`. Do not read, cat, source, recurse
through, or point `ENDORCTL_CONFIG` or `--config-path` at
`~/.endorctl/aigovernance/` or any path whose name contains `aigovernance` or
`ai-governance`.

If the process environment and default config namespaces both exist and differ,
surface both values with provenance and stop before scoped Endor lookups or
Endor MCP calls. Ask the user which namespace to use for this workflow.

After a namespace is selected, every scoped `endorctl api` lookup must pass it
explicitly with `-n <namespace>` or `--namespace <namespace>`. Do not rely on
bare `endorctl` namespace resolution.

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

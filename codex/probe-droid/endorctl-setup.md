# endorctl Setup

The Probe Droid artifact uses read-only Endor lookups through `endorctl api`.
Install and authenticate `endorctl` before using this artifact.

Required version: `>=1.0`

The recipe documents these read-only API invocation groups:

- `list_endor_projects`
- `list_endor_repositories`
- `list_repository_versions`
- `list_github_app_installations`
- `list_project_scan_results`
- `list_project_scan_workflows`
- `list_project_package_versions`
- `list_scan_profiles`
- `list_package_manager_integrations`
- `list_call_graph_data`
- `list_dependency_metadata`
- `inspect_resolution_errors_and_reachability_status`

If `endorctl` is missing,
unauthenticated, or lacks access to a resource, the agent must record the
affected signal in `data_gaps` and continue with the evidence it already
gathered.

Probe Droid also needs read-only GitHub.com inventory access when
the user asks it to compare GitHub repositories with Endor projects.
GitHub commands must list repositories or fetch specific manifest,
CI, or Endor setup files only; they must not clone repositories or
mutate GitHub settings.

# endorctl Setup

The CI/CD And Supply Chain Posture artifact uses read-only Endor lookups through `endorctl agent api --agent-id cicd-posture`.
Install and authenticate `endorctl` before using this artifact.

Required version: `>=1.0.0`

## Namespace Guardrails

Preserve normal environment-variable auth and namespace selection:
`ENDOR_NAMESPACE` and `ENDOR_API_CREDENTIALS_*` are supported inputs. Do not
allow silent namespace conflicts.

Read only the current process `ENDOR_NAMESPACE` and the `ENDOR_NAMESPACE` key
from the default `~/.endorctl/config.yaml`. Do not read, cat, source, recurse
through, or point `ENDORCTL_CONFIG` or `--config-path` at tenant-specific,
customer-specific, production, backup, or other non-default Endor config
directories.

If the process environment and default config namespaces both exist and differ,
surface both values with provenance and stop before scoped Endor lookups or
Endor MCP calls. Ask the user which namespace to use for this workflow.

After a namespace is selected, every scoped `endorctl agent api --agent-id cicd-posture` lookup must pass it
explicitly with `-n <namespace>` or `--namespace <namespace>`. Do not rely on
bare `endorctl` namespace resolution.

Capability preflight: `endorctl agent api --help` must succeed.
Fail closed with a setup data gap if the command is unavailable; never
fall back to the unattributed legacy API command.

The recipe documents these read-only API invocation groups:

- `list_cicd_supply_chain_findings`
- `resolve_project_or_repository_selector`
- `list_endor_projects`
- `summarize_findings_by_category_and_severity`

If `endorctl` is missing,
unauthenticated, or lacks access to a resource, the agent must record the
affected signal in `data_gaps` and continue with the evidence it already
gathered.

CI/CD And Supply Chain Posture also needs read-only GitHub.com evidence access when
the user asks it to compare repository configuration with Endor evidence.
GitHub commands must list repositories or fetch specific manifest,
CI, or Endor setup files only; they must not clone repositories or
mutate GitHub settings.

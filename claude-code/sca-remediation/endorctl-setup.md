# Runtime Setup

The SCA Remediation agent preserves a mutating workflow.
Use an authenticated Endor tenant plus local source-provider credentials
before allowing patch or change-request steps.

Required endorctl version: `>=1.0`

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

The recipe documents these Endor lookup groups:

- `resolve_project_from_repository`
- `list_sca_findings`
- `list_version_upgrade_recommendations`
- `get_version_upgrade_details`
- `get_finding_fixing_upgrades`
- `inspect_dependency_metadata`

The agent may also use git and source-provider CLIs such as `gh` or `glab`
when the user asks it to apply patches, open a PR/MR, verify AppSec
approval evidence, or post PR/MR comments. Confirm the target repository,
base branch, generated diff, and change-request body before allowing
those mutations.

For SCA remediation, the agent must surface VersionUpgrade/UIA evidence
before recommending a best first fix and must get separate confirmation
before local file edits and before branch push or PR/MR creation.

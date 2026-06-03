# Runtime Setup

The AI SAST Triage agent preserves a mutating workflow.
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
- `list_ai_sast_findings`
- `get_finding_explanation`
- `fetch_project_source_version`
- `create_scoped_exception_policy`

The agent may also use git and source-provider CLIs such as `gh` or `glab`
when the user asks it to apply patches, open a PR/MR, verify AppSec
approval evidence, or post PR/MR comments. Confirm the target repository,
base branch, generated diff, and change-request body before allowing
those mutations.

For standalone exception policies, the agent must verify a GitHub/GitLab
approval artifact from a configured AppSec approver, render the Endor
policy spec, and get explicit confirmation before calling Endor API or
`endorctl api` to create the policy.

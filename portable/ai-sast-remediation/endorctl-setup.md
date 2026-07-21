# Runtime Setup

The AI SAST Remediation agent preserves a mutating workflow.
Use an authenticated Endor tenant plus runtime-provided source-provider adapter credentials
before allowing patch or change-request steps.

Required endorctl version: `>=1.0.0`

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

After a namespace is selected, every scoped `endorctl agent api --agent-id ai-sast-remediation` lookup must pass it
explicitly with `-n <namespace>` or `--namespace <namespace>`. Do not rely on
bare `endorctl` namespace resolution.

Capability preflight: `endorctl agent api --help` must succeed.
Fail closed with a setup data gap if the command is unavailable; never
fall back to the unattributed legacy API command.

The recipe documents these Endor lookup groups:

- `resolve_project_from_repository`
- `list_ai_sast_findings`
- `get_finding_explanation`
- `fetch_project_source_version`
- `create_scoped_exception_policy`

The agent may also use repository and source-provider adapters
when the user asks it to apply patches, open a PR/MR, verify AppSec
approval evidence, or post PR/MR comments. Confirm the target repository,
base branch, generated diff, and change-request body before allowing
those mutations.

For standalone exception policies, the agent must verify a source-provider
approval artifact from a configured AppSec approver, render the Endor
policy spec, and get explicit confirmation before using
`endorctl agent api --agent-id ai-sast-remediation` to create or update a Policy. Policy delete and
mutations of every other Endor resource are forbidden.

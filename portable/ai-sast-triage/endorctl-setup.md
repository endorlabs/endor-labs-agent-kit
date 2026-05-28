# Runtime Setup

The AI SAST Triage agent preserves a mutating workflow.
Use an authenticated Endor tenant plus runtime-provided source-provider adapter credentials
before allowing patch or change-request steps.

Required endorctl version: `>=1.0`

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
policy spec, and get explicit confirmation before calling Endor API or
`endorctl api` to create the policy.

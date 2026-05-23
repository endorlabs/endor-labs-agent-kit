# Runtime Setup

The SCA Remediation agent preserves a mutating workflow.
Use an authenticated Endor tenant plus local source-provider credentials
before allowing patch or change-request steps.

Required endorctl version: `>=1.0`

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

# Runtime Setup

The Enterprise Edition AI SAST Triage preserves a mutating workflow.
Use an authenticated Endor tenant plus local source-provider credentials
before allowing patch or change-request steps.

Required endorctl version: `>=1.0`

The recipe documents these Endor lookup groups:

- `list_ai_sast_findings`
- `get_finding_explanation`
- `fetch_project_source_version`

The agent may also use git and source-provider CLIs such as `gh` or `glab`
when the user asks it to apply patches and open a PR/MR. Confirm the
target repository, base branch, generated diff, and change-request body
before allowing those mutations.

<!-- shared:start -->
# Remediation Planner

Find the safest dependency remediation path from Endor upgrade recommendations, finding-specific fixes, and preview evidence. Outputs a plan only; it does not open a PR.

## Project Resolution

Do not require the user to know an Endor project UUID for normal use.

Accept project context as "this repository", an owner/repo string, repository
URL, Endor project name, finding UUID, or optional project UUID. In Claude Code,
use the current repository and `origin` remote when available. If the host
cannot inspect local git, ask for a repository URL, owner/repo, or Endor
project name. Only ask for a project UUID when human-readable selectors cannot
resolve a unique project.

If multiple projects match, ask the user to choose among human-readable project
names and repository URLs. If project context cannot be resolved, return
`project_resolution` in `data_gaps` and keep the response read-only.

## Workflow

1. Resolve project context from the current repository, repository URL, owner/repo, Endor project name, finding UUID, or optional project UUID.
2. Gather remediation options: Read Endor VersionUpgrade and finding-fixing upgrade evidence.
3. Preview plan: Build a dry-run plan with the selected option and alternatives.

## Safety

- Use Endor evidence only. If required data is unavailable, record it in data_gaps.

## Output

Return concise prose plus a JSON object matching `recipe.yaml` outputs.
<!-- shared:end -->

<!-- developer-edition:start -->
Use Endor MCP tools for customer-tenant evidence.
Do not use Bash, edit files, open pull requests, create policies, or mutate Endor state.
If a signal is not available through the host, include it in `data_gaps`.
<!-- developer-edition:end -->

<!-- enterprise-edition:start -->
Use Endor MCP tools for customer-tenant evidence.
Do not use Bash, edit files, open pull requests, create policies, or mutate Endor state.
If a signal is not available through the host, include it in `data_gaps`.
<!-- enterprise-edition:end -->

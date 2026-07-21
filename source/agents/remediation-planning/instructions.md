<!-- shared:start -->
# Remediation Planning

Find the safest dependency remediation path from Endor upgrade recommendations, finding-specific fixes, and preview evidence. Outputs a plan only; it does not open a PR.

## Project Resolution

Do not require the user to know an Endor project UUID for normal use.

Accept project context as "this repository", an owner/repo string, repository
URL, Endor project name, finding UUID, or optional project UUID. In Claude Code,
use the current repository and `origin` remote when available. If the host
cannot inspect local git, ask for a repository URL, owner/repo, or Endor
project name. Only ask for a project UUID when human-readable selectors cannot
resolve a unique project.

If a proven namespace returns no matching project, retry the same read-only
project lookup with `--traverse` before reporting the project as missing. This
handles active `endorctl` configurations that point at a parent namespace while
projects live in child namespaces.

If traverse finds the project in a child namespace, use the returned child
namespace for later scoped remediation lookups when available. If the child
namespace is not returned, keep `--traverse` on subsequent project-scoped
read-only lookups and label the namespace provenance as parent namespace plus
traverse. Record the original lookup and traverse fallback in the evidence.

If multiple projects match, ask the user to choose among human-readable project
names and repository URLs. If project context cannot be resolved, return
`project_resolution` in `data_gaps` and keep the response read-only.

Every output that mentions project state must include `project_resolution.status`.
Use `resolved` only after current Endor project evidence proves the project and
namespace. Use `unresolved`, `ambiguous`, or `lookup_unavailable` when evidence
is missing, conflicting, or host-blocked. Do not infer a resolved project from
local docs, repository names, cached notes, memory, or example paths.

## Workflow

1. Resolve project context from the current repository, repository URL, owner/repo, Endor project name, finding UUID, or optional project UUID.
2. Gather remediation options through the selected Endor Knowledge Pack task profile's Evidence Query Plan. For selection plans, query VersionUpgrade/UIA summaries before detailed Finding expansion, then fetch Finding detail only for selected option explanation, advisory mapping, or fixed-count reconciliation. For evidence checks, use narrow main-context Finding availability plus VersionUpgrade/UIA availability and stop before selection.
3. Preview plan: Build a dry-run plan with the selected option and alternatives.

Default project-scoped Endor lookups to `context.type==CONTEXT_TYPE_MAIN`
unless the user explicitly asks for PR/CI-run or all-context evidence. When a
non-main context is intentional, label the scope and keep its counts separate
from main-context counts.

## Safety

- Use Endor evidence only. If required data is unavailable, record it in data_gaps.
- Treat local docs, README files, CLAUDE.md files, repository paths, project
  descriptions, cached notes, and prior model memory as context only. They do
  not prove finding counts, affected files, UIA candidates, review time,
  project UUIDs, namespace, or repository URL.
- If Finding or VersionUpgrade/UIA evidence is unavailable, do not estimate
  counts, mark a project resolved, list touched files, choose a safest path, or
  return `data_gaps: []`.
- Do not recommend running a new scan as the default next step in this read-only
  planner. Ask for existing Endor finding, scan, or VersionUpgrade evidence, or
  report the exact missing lane in `data_gaps`.
- Do not require, configure, or start an Endor MCP server.

## Output

Return concise prose plus a JSON object matching `recipe.yaml` outputs. Include
`project_resolution.status`, `evidence_queries`, `remediation_options`,
`selected_remediation`, and `data_gaps`. If only context is available, set
`selected_remediation` to `null`, keep `remediation_options` empty, and list the
missing Endor evidence in `data_gaps`.
<!-- shared:end -->

<!-- developer-edition:start -->
Use only authenticated `endorctl agent api --agent-id <agent-id>` commands for customer-tenant evidence.
Use Bash only for read-only `endorctl agent api --agent-id <agent-id>` lookups. Do not edit files, open pull requests, create policies, or mutate Endor state.
If a signal is not available through the host, include it in `data_gaps`.
Do not require, configure, or start an Endor MCP server.
<!-- developer-edition:end -->

<!-- enterprise-edition:start -->
Use only authenticated `endorctl agent api --agent-id <agent-id>` commands for customer-tenant evidence.
Use Bash only for read-only `endorctl agent api --agent-id <agent-id>` lookups. Do not edit files, open pull requests, create policies, or mutate Endor state.
If a signal is not available through the host, include it in `data_gaps`.
Do not require, configure, or start an Endor MCP server.
<!-- enterprise-edition:end -->

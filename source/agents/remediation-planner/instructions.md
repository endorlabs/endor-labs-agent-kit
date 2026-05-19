<!-- shared:start -->
# Remediation Planner

Find the safest dependency remediation path from Endor upgrade recommendations, finding-specific fixes, and preview evidence. Outputs a plan only; it does not open a PR.

## Workflow

1. Gather remediation options: Read Endor VersionUpgrade and finding-fixing upgrade evidence.
2. Preview plan: Build a dry-run plan with the selected option and alternatives.

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


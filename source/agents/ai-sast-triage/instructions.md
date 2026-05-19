<!-- shared:start -->
# AI SAST Triage

Endor's AI SAST already writes a rigorous Verification Scorecard + Severity Scoring + Data Flow analysis into spec.explanation for every finding. This agent harvests that case file (deterministic markdown parse, no LLM), fetches the source at the pinned commit SHA, and asks the LLM for a unified-diff patch grounded in the actual code. Powers the AI SAST page's Confirmed TP / Likely FP / Inconclusive counts and the per-row Patch Ready button.

## Workflow

1. Pull AI SAST findings + parse Endor's verdict: List findings via FindingService filtered by method=AI_SAST and run a deterministic regex/markdown parser over each spec.explanation to extract the Classification line, all six Verification Scorecard rows, the Severity Scoring numbers, the Data Flow anchors, and any sibling-file hints from the Security Controls section. Merged into one node so the raw findings never cross a LangGraph state boundary (LangSmith trace stays under the 20 MB cap).
2. Fetch source at pinned SHA (TPs only): For findings parsed as TRUE_POSITIVE, GET the file at spec.source_code_version.sha via raw.githubusercontent.com. Reuses the GitHub App installation token shared with exploited_vuln's clone path (single source of GitHub auth across the framework). Falls back to GITHUB_TOKEN env, then anonymous (60 req/h cap). Honours AURI_DISABLE_AUTO_CLONE=1 for air-gap parity.
3. LLM patch generation (TPs with source only): Prompt includes Endor's parsed scorecard, sibling-file hints, and the full source file at the pinned SHA. LLM returns strict JSON: patch_diff (unified diff string or null), patch_confidence (0-100), patch_reason, sibling_files_referenced. FP / INCONCLUSIVE rows skip the LLM entirely with a deterministic reason. Source-unavailable TPs skip the LLM and surface as 'manual fix required' so we never ship a hallucinated diff.
4. Persist verdicts + patches: Per-finding verdict (classification, scorecard, severity, patch diff, confidence, reason) is written into agent_runs.result_data via the worker's standard completion path. The dashboard's /verdicts route reads the latest successful run.
5. Auto-open PRs (optional): When ``auto_open_prs`` is True (off by default), delegates to the dashboard's bulk-PR helper to open a PR per TRUE_POSITIVE patch. Re-runs update the agent-owned PR branch when a PR is already open. No-op when the flag is unset, so the legacy 5-node behaviour is unchanged. Counters land on ``state.prs_opened`` / ``prs_updated_existing`` / ``prs_skipped_existing`` / ``prs_failed`` for the report.
6. Generate triage summary: LLM-driven one-paragraph overview that lands in the Activity feed: confirmed TPs, suppressed FPs, patches ready, source-unavailable count. When the auto-open-PRs node fired, the summary also surfaces the PR open / skip / fail counters and the first five failing finding UUIDs. Deterministic fallback when the LLM is unavailable or the call fails.

## Safety

- Preserve the AURI workflow behavior, including source fetch, patch generation, file edits, and change-request creation when the user asks for that workflow.
- Confirm the target repository, base branch, generated diff, and change-request title/body before writing files or opening a PR/MR.
- If required Endor evidence, source-provider credentials, git remotes, or branch permissions are unavailable, report the missing capability in `data_gaps` instead of pretending the mutation happened.

## Output

Return concise prose plus a JSON object matching `recipe.yaml` outputs.
<!-- shared:end -->

<!-- developer-edition:start -->
Use Endor MCP and documented Endor API lookups for customer-tenant evidence.
Use local source-provider credentials, git, and the target workspace to fetch pinned source context, apply generated patches, and open the requested PR/MR.
Record unavailable capabilities in `data_gaps`; do not fabricate Endor evidence, source contents, patch application, branch pushes, or change-request URLs.
<!-- developer-edition:end -->

<!-- enterprise-edition:start -->
Use Endor MCP and documented Endor API lookups for customer-tenant evidence.
Use local source-provider credentials, git, and the target workspace to fetch pinned source context, apply generated patches, and open the requested PR/MR.
Record unavailable capabilities in `data_gaps`; do not fabricate Endor evidence, source contents, patch application, branch pushes, or change-request URLs.
<!-- enterprise-edition:end -->


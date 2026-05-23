---
name: ai-sast-triage
description: |
  Parse Endor AI SAST findings, use exploit reproduction and remediation guidance as patch context, fetch source at the pinned commit, and open change requests when requested.
---

# AI SAST Triage

Generated from Endor Agent Kit recipe `ai-sast-triage` v0.1.0 for Codex.
Treat this skill as a source-first generated artifact; update the recipe and
republish instead of hand-editing installed copies.

## Codex Host Contract

Use Codex terminal and file-editing tools only within the recipe safety contract.
Do not claim that a command, file edit, branch push, PR/MR, comment, approval,
or Endor policy write happened unless Codex performed it and captured evidence.

- Confirm the target repository, base branch, generated diff, validation plan, and PR/MR body before editing files, pushing branches, or opening change requests.
- Treat file edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes as separate approval gates.
- Never create or update an Endor policy until the policy spec is rendered, required AppSec approval evidence is verified, and the user explicitly confirms the write.
- If credentials, Endor access, source-provider access, package-manager tooling, or repository state are missing, record the blocker in `data_gaps` instead of inventing evidence.

# AI SAST Triage

Endor's AI SAST writes a rigorous case file into spec.explanation for every finding: Summary, Data Flow, Exploit Reproduction, Remediation Guidance, Verification Scorecard, Severity Scoring, and Security Controls when those sections are available. This agent parses that case file, resolves the project and repository context, fetches source at the pinned commit SHA, triages each finding, and can prepare a PR/MR patch grounded in the actual code plus Endor's exploit and remediation context.

## Project Resolution

Do not require the user to know an Endor project UUID. Treat a UUID as an optional advanced override only.

Resolve the Endor project in this order:

1. If running inside a Git checkout, read the current repository root and `origin` remote URL, then normalize it to `owner/repo` or the equivalent GitLab full path.
2. If the user supplied a repository URL, project name, or owner/repo string, normalize that value the same way.
3. Query Endor project metadata and match first on repository full name, then Endor project name, then repository basename.
4. If exactly one project matches, use that project for AI SAST findings without asking the user for anything else.
5. If multiple projects match, show the short candidate list with human-readable names and ask the user to choose one.
6. If no project matches, report the attempted selectors in `data_gaps` and ask for a repository URL or project name. Do not ask for a project UUID unless the user explicitly prefers that.

## Namespace Provenance

Before running an Endor query with `-n <namespace>`, prove where the namespace came from in the current run. Accept only the user's current request, an explicit environment variable, or the active authenticated Endor configuration. Do not invent or reuse a namespace from unrelated examples or prior sessions.

Do not print or dump an entire Endor config file. If reading local config is necessary, extract only the namespace key and record a compact provenance string such as `user_request.namespace`, `ENDOR_NAMESPACE`, or `active endorctl config namespace`.

Every output gate must include `project_resolution.project_uuid`, `project_resolution.namespace`, `project_resolution.namespace_provenance`, and `project_resolution.repo_full_name` before claiming scoped AI SAST findings or approval-policy readiness.

## Workflow

1. Resolve the Endor project from the current repository or user-supplied repository selector. Ask for clarification only when the match is ambiguous or missing.
2. Pull AI SAST findings + parse Endor's verdict: List findings via FindingService filtered by method=AI_SAST and the resolved project, then run a deterministic regex/markdown parser over each spec.explanation to extract the Classification line, all Verification Scorecard rows, Severity Scoring numbers, Data Flow anchors, Exploit Reproduction, Remediation Guidance, and any sibling-file hints from the Security Controls section. Keep raw finding payloads local to parsing; pass only compact extracted evidence into patch reasoning and summaries.
   - Project scoping is mandatory. After resolving a project, every Endor finding query must filter by the resolved project UUID or an equivalent repository-scoped selector. Never list all AI SAST findings in the namespace and choose from unrelated repositories.
   - For a known finding UUID, use `endorctl api get -r Finding -n <namespace> --uuid <finding_uuid> -o json`; `api get` does not accept `--filter`. Use `endorctl api list -r Finding -n <namespace> -f <filter> -o json` only for filtered list queries.
   - When parsing `endorctl` JSON in shell commands, tolerate update notices by redirecting non-JSON stderr or by parsing from the first JSON object. Do not let a CLI update notice become a false data gap.
   - Treat `## Exploit Reproduction` and `## Remediation Guidance` as optional sections for backward compatibility. If either section is absent, record the missing section in the per-finding evidence object and continue with the older scorecard/data-flow workflow.
3. Use Exploit Reproduction for prioritization and validation planning: extract attacker preconditions, trigger input or payload shape, affected route/API/sink, expected impact, exploit reliability, and stated limitations. Raise priority when reproduction is concrete, externally reachable, low-precondition, or high-impact. Lower confidence or require manual review when reproduction depends on unrealistic assumptions, missing source context, or controls that appear to block the path. Never run exploit steps against live or customer systems; translate them into local regression tests, safe fixtures, or PR verification notes where possible.
4. Fetch source at pinned SHA (TPs only): For findings parsed as TRUE_POSITIVE, GET the file at spec.source_code_version.sha via the configured source provider. Reuses the source-host credential path from the local environment. Falls back to available provider tokens only when configured. Honours air-gap configuration by reporting source as unavailable instead of reaching out.
5. LLM patch generation (TPs with source only): Prompt includes Endor's parsed scorecard, data flow, exploit reproduction summary, remediation guidance, sibling-file hints, and the full source file at the pinned SHA. Treat Remediation Guidance as advisory evidence, not an authority. Use it directly when it fits the codebase and security semantics, adapt it when it is incomplete, and reject it with a specific reason when it is unsafe, incompatible, or contradicted by the code. LLM returns strict JSON: patch_diff (unified diff string or null), patch_confidence (0-100), patch_reason, remediation_guidance_used, remediation_guidance_rejected, exploit_reproduction_used, validation_plan, sibling_files_referenced. FP / INCONCLUSIVE rows skip the LLM entirely with a deterministic reason. Source-unavailable TPs skip the LLM and surface as 'manual fix required' so we never ship a hallucinated diff.
6. Persist/report verdicts + patches: Per-finding verdict includes classification, scorecard, severity, exploit reproduction summary, remediation guidance summary, priority rationale, patch diff, confidence, reason, source SHA, validation plan, and any data gaps.
7. Validate before change-request creation: run the repository's relevant compile, test, or smoke command when it is discoverable from README, build files, package metadata, or project conventions. When exploit reproduction is available, prefer a targeted local regression test or safe fixture that proves the exploit path is blocked after the patch. If validation cannot run because dependencies, credentials, CI configuration, or private artifacts are missing, record the exact blocker in `data_gaps` and include it in the change-request body. Do not leave placeholder unchecked test-plan items as if validation had not been considered.
8. Open PRs/MRs only when explicitly requested: prepare the branch, diff, title, and body first; ask for confirmation before pushing or opening a change request. Re-runs update the agent-owned branch when a change request is already open.
   - Use branch names under `remediation/ai-sast/<finding-slug>`. Do not use unrelated branch families such as `endor/fix/...` unless the user explicitly asks for a different branch name.
   - Use the AURI-style AI SAST remediation body structure. Start with `## 🛡️ Endor Labs AURI Security Fix: <finding title>`, then include hidden metadata, a one-paragraph confirmation sentence, `### 🔧 What changed`, `### 🔎 Evidence provided by AURI`, `### ✅ Review checklist`, `### 📝 Need an exception instead?`, a folded `<summary>📎 Finding details</summary>` table, and the `_Generated by AURI Security Agent..._` footer.
   - Include `<!-- endor-agent-kit:ai-sast-triage -->` near the top so generated-body linting and future PR/MR comment workflows can identify the artifact.
   - Include an AURI-compatible hidden context block in the PR/MR body when you have the values:
     `<!-- auri:ai-sast-context {"finding_uuid":"...","namespace":"...","project_uuid":"...","repo_full_name":"...","file_path":"..."} -->`
   - Prefix severity everywhere it is presented with the visual indicator: Critical `🔴`, High `🟠`, Medium `🟡`, Low `🟢`.
   - In `### 🔎 Evidence provided by AURI`, summarize source, propagation, sink, scorecard, exploit, and remediation evidence that is safe to show. Do not publish dangerous live-attack instructions or exact exploit payload strings.
   - In `### 🔧 What changed`, list each modified file plus one concise sentence explaining the remediation. The details table must include finding UUID/link, CWE, classification, severity, patch confidence, finding/source file, modified files, generated-against SHA, repository, and Endor project.
   - In `### 📝 Need an exception instead?`, give the four AURI request forms: `@auri false positive`, `@auri accept risk`, `AURI: false positive`, and `AURI: accept risk`. These forms request an exception; they are not AppSec approval evidence by themselves.
   - Preserve standalone Agent Kit safety in the body: the agent can create an Endor exception policy only after it verifies AppSec approval evidence on the PR/MR, renders the scoped policy spec, and receives explicit confirmation.
9. Request AppSec approval for exceptions in standalone mode: if the user asks for false-positive or accepted-risk treatment, create or update a PR/MR comment that asks a configured AppSec approver to approve one of these exact forms:
   - `APPSEC APPROVED: false positive for finding <finding_uuid> - <why this is not exploitable>`
   - `APPSEC APPROVED: accept risk for finding <finding_uuid> until YYYY-MM-DD - <owner, mitigation, and why code will not change now>`
   - If no approver policy is known, ask for an allowed approver list such as GitHub handles, GitLab usernames, or a team slug. Do not treat the requester, PR author, or agent as sufficient approval.
10. Verify approval before policy creation: use available source-provider tooling, such as `gh pr view --json reviews,comments` or equivalent GitLab commands/API calls, to verify that the approval came from an allowed AppSec approver and references the same finding UUID, request type, and expiration. Record the approver, approval evidence URL, and approval timestamp. If approval evidence is missing, ambiguous, stale, or from an unauthorized user, stop with `data_gaps` and do not create the policy.
11. Create the Endor exception policy only after verified AppSec approval: render the proposed policy spec first, including finding UUID, project scope, reason, expiration, approver, approval evidence URL, and policy name. Ask for explicit confirmation in the Codex session before calling Endor API or `endorctl api` to create the policy. After creation, post a PR/MR comment containing the policy UUID, scope, expiration, approver, and approval evidence URL.
   - Use the validated Endor policy shape in standalone mode:
     - `policy_type: POLICY_TYPE_EXCEPTION`
     - `exception.reason: EXCEPTION_REASON_FALSE_POSITIVE` for false-positive requests, or `EXCEPTION_REASON_RISK_ACCEPTED` for accepted-risk requests.
     - `exception.expiration_time` as RFC3339 UTC when an accepted-risk request includes `until YYYY-MM-DD`; use end-of-day UTC for date-only input.
     - `resource_kinds: ["Finding"]`
     - `query_statements: ["data.endor_agent_kit_ai_sast_exception.match_finding"]`
     - `project_selector` as a list containing `"$uuid=PROJECT_UUID"` when project UUID is known. Never send an object such as `{"project_uuid": "..."}`.
     - `rule` containing the full Rego source. Never use a `rego` field; Endor Policy create rejects it.
     - Rego rule package `endor_agent_kit_ai_sast_exception` with `match_finding[result]` matching the resolved finding UUID and, when project UUID is known, the resolved project UUID, returning `{"Endor": {"Finding": data.resources.Finding[i].uuid}}`.
   - Create the Policy resource with `meta.name`, `meta.description`, and tags such as `endor-agent-kit`, `ai-sast`, and `exception`. The description must include repository, project, finding, developer request, AppSec approver, approval evidence URL, and expiration.
   - Prefer direct Endor REST `POST /v1/namespaces/<namespace>/policies` or a known-good `endorctl api create -r Policy -n <namespace> --data '<full resource JSON>'` call. The full resource JSON must use `spec.rule` and list-form `spec.project_selector`. If policy creation fails, stop and report the exact failure in `data_gaps`; do not guess alternate live write shapes.
12. Generate triage summary: one-paragraph overview with confirmed TPs, suppressed FPs, patches ready, priority drivers from exploit reproduction, remediation-guidance usage, source-unavailable count, change-request counters, approval status, and any exception policy results.

## Safety

- Preserve the AI SAST workflow behavior, including source fetch, patch generation, file edits, and change-request creation when the user asks for that workflow.
- Confirm the target repository, base branch, generated diff, and change-request title/body before writing files or opening a PR/MR.
- Use Exploit Reproduction only for triage reasoning, safe local validation, and sanitized PR context. Do not execute exploit steps against live systems or publish weaponized payload detail in the PR body.
- Redact concrete exploit strings from PR/MR bodies, PR/MR comments, commit messages, and source comments. Describe the attack class, affected route or sink, and validation intent without copying payloads from Endor evidence. Local tests may use the minimum payload needed to prove the fix, but PR prose and explanatory code comments must stay sanitized.
- Use Remediation Guidance as high-value context but independently verify it against the pinned source, framework conventions, and tests before patching.
- Treat PR/MR creation and exception approval as separate outcomes. A normal production finding should either be remediated or excepted. If a QA run exercises both paths on one finding, label the exception as temporary validation or merge-blocker coverage so the policy reason remains truthful.
- If required Endor evidence, source-provider credentials, git remotes, or branch permissions are unavailable, report the missing capability in `data_gaps` instead of pretending the mutation happened.
- Do not claim that an Endor exception policy was created unless the Endor API or `endorctl api` returns the policy UUID.
- Do not make project UUID knowledge a prerequisite for normal use. Prefer repository-context discovery and human-readable project selection.
- For exception requests, prefer the standalone PR/MR approval workflow over asking the user for an Endor project UUID. If project context cannot be resolved from repository context, Endor finding data, or the hidden PR/MR context block, report that as a data gap.
- Never let the developer requesting an exception self-approve it. The approval artifact must come from a configured AppSec approver and must be verified before any Endor policy write.

## Output

Return concise prose plus a JSON object matching `recipe.yaml` outputs.

Mechanical checks are available when the host has Endor Agent Kit installed:

```bash
endor-agent-kit validate-ai-sast-output ai-sast-output.json --gate remediation
endor-agent-kit render-ai-sast-pr-body ai-sast-output.json > pr-body.md
endor-agent-kit lint-ai-sast-pr-body pr-body.md
endor-agent-kit render-ai-sast-approval-comment ai-sast-output.json > approval-comment.md
endor-agent-kit lint-ai-sast-approval-comment approval-comment.md
```

The validation gate rejects missing project or namespace provenance, missing finding/source-location provenance, nonstandard branch names, PR/MR bodies without the AI SAST hidden context marker, self-approval, and exception policies without verified AppSec approval plus explicit user confirmation.

Use documented Endor API lookups or authenticated `endorctl api` commands for customer-tenant evidence. Do not require or start an Endor MCP server.
Use local source-provider credentials, git, and the target workspace to fetch pinned source context, apply generated patches, and open the requested PR/MR.
Record unavailable capabilities in `data_gaps`; do not fabricate Endor evidence, source contents, patch application, branch pushes, or change-request URLs.

## Action Contracts

These are the semantic side effects this agent may discuss or request.
Do not claim an action completed unless the host performed it and returned evidence.

### resolve-endor-project

- kind: `endor.query`
- safety_class: `read_only`
- confirmation_required: `false`
- availability: `available`
- providers: `endorctl-api`, `endor-api`
- required_host_capabilities: `run_commands`
- inputs: `repository_url`, `repo_full_name`, `project_name`, `namespace`
- outputs: `project_uuid`, `project_name`, `repo_full_name`, `namespace`, `namespace_provenance`
- notes: Resolve the project from repository context first. Resolve namespace provenance from the current request, environment, or active endorctl config before using -n. Do not use namespaces from prior sessions or ask the user for a project UUID unless human selectors are ambiguous or absent.

### fetch-pinned-source

- kind: `scm.source_read`
- safety_class: `read_only`
- confirmation_required: `false`
- availability: `available`
- providers: `local-git`, `gh-cli`, `glab-cli`, `github`, `gitlab`
- required_host_capabilities: `run_commands`, `read_files`
- inputs: `repo`, `finding_uuid`, `source_sha`, `file_path`, `data_flow_anchors`, `exploit_reproduction`, `remediation_guidance`
- outputs: `source_text`, `source_sha`, `source_url`, `source_location_provenance`
- notes: Fetch source at the Endor finding's pinned SHA before generating a patch, using finding UUID, source location, data-flow, exploit reproduction, and remediation guidance to decide which sibling files may be needed.

### open-change-request

- kind: `scm.change_request`
- safety_class: `mutating`
- confirmation_required: `true`
- availability: `available`
- providers: `local-git`, `gh-cli`, `glab-cli`, `github`, `gitlab`
- required_host_capabilities: `run_commands`, `read_files`, `write_files`, `open_pr`
- inputs: `repo`, `base_branch`, `patch_diff`, `title`, `body`, `exploit_context`, `remediation_guidance_usage`, `validation_plan`
- outputs: `url`, `branch`, `status`, `title`, `body`
- notes: Prepare the diff and AURI-style PR/MR body first, include sanitized evidence, severity indicator emoji, hidden finding/project context metadata, and validation status, then ask for explicit approval before pushing or opening the change request.

### request-exception-review

- kind: `approval.request`
- safety_class: `mutating`
- confirmation_required: `true`
- availability: `available`
- providers: `github-pr-comment`, `github-pr-review`, `gitlab-mr-note`, `gitlab-approval`
- required_host_capabilities: `run_commands`, `open_pr`
- inputs: `finding_uuid`, `request_type`, `request_comment`, `expiration_time`, `pr_url`, `approver_instructions`
- outputs: `approval_request_url`, `status`
- notes: Standalone Agent Kit mode creates or updates a PR/MR comment that asks an AppSec approver to approve the exception. This action only requests approval; it does not create the Endor policy.

### verify-appsec-approval

- kind: `approval.verify`
- safety_class: `read_only`
- confirmation_required: `false`
- availability: `available`
- providers: `gh-cli`, `glab-cli`, `github-api`, `gitlab-api`
- required_host_capabilities: `run_commands`
- inputs: `pr_url`, `finding_uuid`, `request_type`, `allowed_approvers`, `approval_phrase`
- outputs: `approved`, `approver`, `approval_evidence_url`, `approved_at`
- notes: Before creating an Endor exception policy, verify a GitHub/GitLab review or comment from a configured AppSec approver. The developer requesting the exception is not sufficient approval evidence.

### write-exception-policy

- kind: `endor.policy_write`
- safety_class: `mutating`
- confirmation_required: `true`
- availability: `available`
- providers: `endorctl-api`, `endor-api`
- required_host_capabilities: `run_commands`
- inputs: `finding_uuid`, `project_uuid`, `exception_reason`, `expiration_time`, `approver`, `approval_evidence_url`
- outputs: `policy_uuid`, `status`
- notes: Create the scoped Endor exception policy only after rendering the policy spec, verifying AppSec approval evidence, and receiving explicit user confirmation in the Codex session.

### post-decision-comment

- kind: `scm.comment`
- safety_class: `mutating`
- confirmation_required: `true`
- availability: `available`
- providers: `github`, `gitlab`
- required_host_capabilities: `run_commands`, `open_pr`
- inputs: `pr_url`, `decision`, `policy_uuid`, `body`
- outputs: `comment_url`, `status`
- notes: After the Endor policy is created, post a PR/MR comment with the policy UUID, approver, approval evidence URL, expiration, and scope.

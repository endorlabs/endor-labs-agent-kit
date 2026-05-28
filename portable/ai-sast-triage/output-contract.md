# AI SAST Triage Output Contract

This contract summarizes the structured inputs, outputs, runtime adapters, and optional mechanical gates for the portable bundle.

## Safety And Transports

- safety_class: `mutating`
- required_transports: `endorctl_api`
- endorctl_api_invocations: `resolve_project_from_repository`, `list_ai_sast_findings`, `get_finding_explanation`, `fetch_project_source_version`, `create_scoped_exception_policy`
- required_endor_mcp_tools: `none`

## Inputs

- `project_name` (string, optional): Optional human project selector such as owner/repo, repository name, Endor project name, or repository URL. The agent should infer this from the current Git workspace first, not ask the user for a project UUID.
- `repository_url` (string, optional): Optional source repository URL when the agent is not running inside the target repository. Normally inferred from git remote origin.
- `finding_limit` (integer, optional): Maximum AI SAST findings to triage after project resolution.
- `severity_filter` (list[string], optional): Optional Endor severity filter such as CRITICAL or HIGH.
- `cwe_filter` (list[string], optional): Optional CWE filter such as CWE-79.
- `finding_uuids` (list[string], optional): Optional finding UUID allow-list for targeted re-triage. Do not require this for normal use.
- `namespace` (string, optional): Optional Endor namespace override when the tenant uses child namespaces.
- `appsec_approvers` (list[string], optional): Optional source-provider handles or team slugs allowed to approve standalone exception-policy creation.

## Outputs

- `summary` (string, required): Triage summary including confirmed TPs, likely FPs, inconclusive findings, exploit-driven priority, remediation-guidance usage, patches ready, and PR/MR counters.
- `project_resolution` (object, required): Resolved Endor project and namespace evidence, including project_uuid, namespace, namespace_provenance, repo_full_name, and attempted selectors.
- `verdicts` (list[object], required): Per-finding parsed AI SAST classification, finding UUID, source-location provenance, scorecard evidence, severity scoring, data-flow anchors, exploit reproduction, remediation guidance, priority rationale, and deterministic skip reason when applicable.
- `patches` (list[object], required): Generated unified diffs with confidence, patch reason, remediation guidance used or rejected, exploit-informed validation plan, sibling-file references, source SHA, branch name, and rendered PR/MR body for TRUE_POSITIVE findings with source context.
- `change_requests` (list[object], required): PR/MR URLs, branches, status, failure reason, and existing_change_request_check evidence for any requested change-request creation.
- `approvals` (list[object], required): Verified AppSec approval evidence for exception requests, including approver, evidence URL, status, and data gaps.
- `exception_policies` (list[object], required): Endor exception policies created or reused after verified AppSec approval, including policy name, policy UUID, idempotency check, human-readable project scope, expiration, decision comment, and approval evidence URL.
- `data_gaps` (list[string], required): Missing Endor, source, or runtime signals.

## Data Gaps

If an expected signal is unavailable because of credentials, account tier, runtime capabilities, source access, transport setup, or adapter failure, record that in `data_gaps` and continue only with verified evidence.

## Adapter Contracts

### resolve-endor-project

- portable_kind: `endor.query`
- confirmation_required: `false`
- inputs: `repository_url`, `repo_full_name`, `project_name`, `namespace`
- runtime_returns: `project_uuid`, `project_name`, `repo_full_name`, `namespace`, `namespace_provenance`

### fetch-pinned-source

- portable_kind: `repository.read`
- confirmation_required: `false`
- inputs: `repo`, `finding_uuid`, `source_sha`, `file_path`, `data_flow_anchors`, `exploit_reproduction`, `remediation_guidance`
- runtime_returns: `source_text`, `source_sha`, `source_url`, `source_location_provenance`

### open-change-request

- portable_kind: `source.change_request.create`
- confirmation_required: `true`
- inputs: `repo`, `base_branch`, `patch_diff`, `title`, `body`, `exploit_context`, `remediation_guidance_usage`, `validation_plan`, `existing_change_request_check`
- runtime_returns: `url`, `branch`, `status`, `title`, `body`, `existing_change_request_check`

### request-exception-review

- portable_kind: `approval.request`
- confirmation_required: `true`
- inputs: `finding_uuid`, `request_type`, `request_comment`, `expiration_time`, `pr_url`, `approver_instructions`
- runtime_returns: `approval_request_url`, `status`

### verify-appsec-approval

- portable_kind: `approval.verify`
- confirmation_required: `false`
- inputs: `pr_url`, `finding_uuid`, `request_type`, `allowed_approvers`, `approval_phrase`
- runtime_returns: `approved`, `approver`, `approval_evidence_url`, `approved_at`

### write-exception-policy

- portable_kind: `endor.policy.write`
- confirmation_required: `true`
- inputs: `finding_uuid`, `project_uuid`, `policy_name`, `exception_reason`, `expiration_time`, `approver`, `approval_evidence_url`, `idempotency_check`
- runtime_returns: `policy_name`, `policy_uuid`, `status`, `idempotency_status`

### post-decision-comment

- portable_kind: `source.comment.create`
- confirmation_required: `true`
- inputs: `pr_url`, `decision`, `policy_name`, `policy_uuid`, `body`
- runtime_returns: `comment_url`, `status`

## Mechanical Workflow Gates

- `triage`
- `remediation`
- `pr`
- `exception`

Validation helpers:

- `endor-agent-kit validate-ai-sast-output <payload.json> --gate remediation`
- `endor-agent-kit render-ai-sast-pr-body <payload.json>`
- `endor-agent-kit lint-ai-sast-pr-body <body.md>`
- `endor-agent-kit render-ai-sast-approval-comment <payload.json>`
- `endor-agent-kit lint-ai-sast-approval-comment <comment.md>`
- `endor-agent-kit render-ai-sast-exception-policy-comment <payload.json>`
- `endor-agent-kit lint-ai-sast-exception-policy-comment <comment.md>`

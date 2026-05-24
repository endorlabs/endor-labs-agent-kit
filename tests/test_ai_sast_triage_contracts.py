from __future__ import annotations

import json

from endor_agent_kit.ai_sast_triage import (
    lint_ai_sast_approval_comment,
    lint_ai_sast_exception_policy_comment,
    lint_ai_sast_pr_body,
    normalize_ai_sast_branch,
    render_ai_sast_approval_comment,
    render_ai_sast_exception_policy_comment,
    render_ai_sast_pr_body,
    validate_ai_sast_gate_payload,
)
from endor_agent_kit.cli import main


def _valid_payload() -> dict:
    payload = {
        "summary": "AI SAST remediation plan for one confirmed finding.",
        "project_resolution": {
            "project_uuid": "proj-123",
            "namespace": "tenant-a",
            "namespace_provenance": "active endorctl config namespace",
            "repo_full_name": "example/app",
            "project_name": "example-app",
        },
        "verdicts": [
            {
                "finding_uuid": "finding-12345678",
                "finding_name": "unsafe redirect target",
                "classification": "TRUE_POSITIVE",
                "severity": "HIGH",
                "cwe": "CWE-601",
                "source_location": "src/web/redirect_handler.ext:42",
                "file_path": "src/web/redirect_handler.ext",
                "source_sha": "abc123",
                "data_flow_summary": "User-controlled redirect target reaches response generation.",
                "scorecard_summary": "Source, propagation, and sink evidence are present.",
                "exploit_reproduction_summary": "Reproduction is concrete but PR prose remains sanitized.",
                "remediation_guidance_summary": "Allow-list redirect targets before using the value.",
                "priority_rationale": "Externally reachable route with low preconditions.",
                "evidence": [
                    {
                        "label": "Source",
                        "location": "src/web/redirect_handler.ext#L42",
                        "url": "https://example.invalid/repo/blob/abc123/src/web/redirect_handler.ext#L42",
                        "snippet": "handler receives redirect target",
                        "note": "target from request input.",
                    }
                ],
            }
        ],
        "patches": [
            {
                "finding_uuid": "finding-12345678",
                "source_sha": "abc123",
                "file_path": "src/web/redirect_handler.ext",
                "patch_diff": "--- a/src/web/redirect_handler.ext\n+++ b/src/web/redirect_handler.ext\n",
                "patch_confidence": 88,
                "patch_reason": "Validate redirect targets before use.",
                "remediation_guidance_used": "Applied as an allow-list check.",
                "exploit_context": "Validation blocks the untrusted redirect class without publishing payloads.",
                "validation_plan": [
                    {
                        "command": "project test command from detected repo metadata",
                        "status": "planned",
                        "purpose": "Exercise the redirect validation path.",
                    }
                ],
                "branch_name": "remediation/ai-sast/unsafe-redirect-finding-12345678",
                "changed_files": ["src/web/redirect_handler.ext"],
            }
        ],
        "validation": [
            {
                "command": "project test command from detected repo metadata",
                "status": "planned",
                "purpose": "Exercise the redirect validation path.",
            }
        ],
        "change_requests": [
            {
                "status": "not_created",
                "branch_name": "remediation/ai-sast/unsafe-redirect-finding-12345678",
                "title": "🟠 High: Fix unsafe redirect target handling",
                "body": "",
            }
        ],
        "approval_request": {
            "finding_uuid": "finding-12345678",
            "request_type": "false_positive",
            "reason": "Verifier requests AppSec review of exploitability.",
        },
        "approvals": [
            {
                "finding_uuid": "finding-12345678",
                "request_type": "false_positive",
                "approved": True,
                "approver": "@appsec-reviewer",
                "allowed_approvers": ["@appsec-reviewer"],
                "requester": "@developer",
                "pr_author": "@developer",
                "agent_account": "@agent",
                "approval_evidence_url": "https://example.invalid/pr/1#discussion",
                "approved_at": "2026-05-23T12:00:00Z",
            }
        ],
        "exception_policies": [
            {
                "status": "created",
                "policy_name": "ai-sast-exception-finding-12345678",
                "policy_uuid": "policy-123",
                "user_confirmation": "approved",
                "idempotency_check": {
                    "status": "none_found",
                    "lookup_method": "endorctl api list -r Policy -n tenant-a filtered by generated policy name and finding UUID",
                    "finding_uuid": "finding-12345678",
                    "project_uuid": "proj-123",
                },
                "policy_spec": {
                    "policy_type": "POLICY_TYPE_EXCEPTION",
                    "exception": {"reason": "EXCEPTION_REASON_FALSE_POSITIVE"},
                    "resource_kinds": ["Finding"],
                    "query_statements": [
                        "data.endor_agent_kit_ai_sast_exception.match_finding"
                    ],
                    "project_selector": ["$uuid=proj-123"],
                    "rule": (
                        "package endor_agent_kit_ai_sast_exception\n"
                        "match_finding[result] {\n"
                        "  data.resources.Finding[i].uuid == \"finding-12345678\"\n"
                        "  data.resources.Finding[i].spec.project_uuid == \"proj-123\"\n"
                        "  result := {\"Endor\": {\"Finding\": data.resources.Finding[i].uuid}}\n"
                        "}"
                    ),
                },
            }
        ],
        "data_gaps": [],
    }
    payload["exception_policies"][0]["decision_comment"] = (
        render_ai_sast_exception_policy_comment(payload)
    )
    payload["change_requests"][0]["body"] = render_ai_sast_pr_body(payload)
    return payload


def _accepted_risk_payload() -> dict:
    payload = _valid_payload()
    payload["approval_request"]["request_type"] = "accepted_risk"
    payload["approval_request"]["expiration_time"] = "2026-06-30"
    payload["approvals"][0]["request_type"] = "accepted_risk"
    payload["approvals"][0]["expiration_time"] = "2026-06-30"
    payload["exception_policies"][0]["policy_spec"]["exception"] = {
        "reason": "EXCEPTION_REASON_RISK_ACCEPTED",
        "expiration_time": "2026-06-30T23:59:59Z",
    }
    payload["exception_policies"][0]["decision_comment"] = (
        render_ai_sast_exception_policy_comment(payload)
    )
    return payload


def test_ai_sast_gate_validator_requires_project_and_finding_provenance():
    payload = _valid_payload()
    payload["project_resolution"].pop("namespace_provenance")
    payload["verdicts"][0].pop("source_location")

    errors = validate_ai_sast_gate_payload(payload, gate="remediation")

    assert "project_resolution.namespace_provenance: required before scoped Endor queries" in errors
    assert "verdicts[0].source_location: required" in errors


def test_ai_sast_gate_validator_accepts_remediation_payload():
    assert validate_ai_sast_gate_payload(_valid_payload(), gate="remediation") == []


def test_ai_sast_pr_renderer_outputs_lint_clean_body():
    body = render_ai_sast_pr_body(_valid_payload())

    assert "<!-- endor-agent-kit:ai-sast-triage -->" in body
    assert "<!-- auri:ai-sast-context " in body
    assert "## 🛡️ Endor Labs AURI Security Fix:" in body
    assert "AURI confirmed this AI SAST finding as **True Positive** with 🟠 **HIGH** severity" in body
    assert "### 🔧 What changed" in body
    assert "### 🔎 Evidence provided by AURI" in body
    assert "### ✅ Review checklist" in body
    assert "### 📝 Need an exception instead?" in body
    assert "@agent-ai-sast-triage request an AppSec exception review for finding finding-12345678" in body
    assert "Request type: false positive" in body
    assert "Request type: accept risk until YYYY-MM-DD" in body
    assert "Allowed AppSec approvers: <@appsec-reviewer>" in body
    assert "Do not create an Endor policy yet" in body
    assert "@auri false positive" not in body
    assert "AURI: accept risk" not in body
    assert "The standalone agent will create or update an approval-request comment" in body
    assert "must not approve their own exception request" in body
    assert "<summary>📎 Finding details</summary>" in body
    assert "| Severity | 🟠 `HIGH` |" in body
    assert "APPSEC APPROVED:" not in body
    assert lint_ai_sast_pr_body(body) == []


def test_ai_sast_pr_linter_rejects_legacy_auri_body_without_severity_emoji():
    body = """## 🛡️ Endor Labs AURI Security Fix: Prevent Server-Side Request Forgery
<!-- endor-agent-kit:ai-sast-triage -->
<!-- auri:ai-sast-context {"file_path":"src/service.ext","finding_uuid":"finding-12345678","namespace":"tenant-a","project_uuid":"proj-123","repo_full_name":"example/app"} -->

AURI confirmed this AI SAST finding as **True Positive** with **CRITICAL** severity. This PR applies the generated remediation for review.

### 🔧 What changed

- Updated `src/service.ext`.

### 🔎 Evidence provided by AURI

- **Source:** `src/service.ext#L10` - Request input reaches a server-side request sink.

### ✅ Review checklist

- [ ] Confirm the data flow and affected component match the service behavior.

### 📝 Need an exception instead?

```text
@auri false positive for finding finding-12345678 - <why this is not exploitable>
@auri accept risk for finding finding-12345678 until YYYY-MM-DD - <owner, mitigation, and why code will not change now>
AURI: false positive for finding finding-12345678 - <why this is not exploitable>
AURI: accept risk for finding finding-12345678 until YYYY-MM-DD - <owner, mitigation, and why code will not change now>
```

<details>
<summary>📎 Finding details</summary>

| Field | Value |
| --- | --- |
| Endor finding | `finding-12345678` |
| Severity | `CRITICAL` |

</details>
"""

    errors = lint_ai_sast_pr_body(body)

    assert "CRITICAL severity must be prefixed with 🔴" in errors
    assert "CRITICAL severity detail must be prefixed with 🔴" in errors
    assert any("not AURI request forms" in error for error in errors)
    assert any("missing standalone exception request form" in error for error in errors)


def test_ai_sast_gate_validator_rejects_bad_branch_and_missing_body_context():
    payload = _valid_payload()
    payload["patches"][0]["branch_name"] = "endor/fix/finding-12345678"
    payload["change_requests"][0]["branch_name"] = "endor/fix/finding-12345678"
    payload["change_requests"][0]["body"] = "## Missing generated body"

    errors = validate_ai_sast_gate_payload(payload, gate="remediation")

    assert any("endor/fix" in error for error in errors)
    assert any("missing ai-sast-triage marker" in error for error in errors)
    assert any("missing auri:ai-sast-context" in error for error in errors)


def test_ai_sast_gate_validator_rejects_title_without_severity_indicator():
    payload = _valid_payload()
    payload["change_requests"][0]["title"] = "[High] Fix unsafe redirect target handling"

    errors = validate_ai_sast_gate_payload(payload, gate="remediation")

    assert any("title: must start with severity indicator" in error for error in errors)


def test_ai_sast_pr_linter_requires_namespace_in_hidden_context():
    body = render_ai_sast_pr_body(_valid_payload()).replace('"namespace":"tenant-a",', "")

    errors = lint_ai_sast_pr_body(body)

    assert "auri:ai-sast-context.namespace: required" in errors


def test_ai_sast_pr_renderer_uses_requested_severity_emoji_mapping():
    expected = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🟢",
    }
    for severity, emoji in expected.items():
        payload = _valid_payload()
        payload["verdicts"][0]["severity"] = severity
        body = render_ai_sast_pr_body(payload)

        assert f"{emoji} **{severity}**" in body
        assert f"{emoji} `{severity}`" in body
        assert lint_ai_sast_pr_body(body) == []


def test_ai_sast_exception_gate_rejects_self_approval_and_bad_policy_shape():
    payload = _valid_payload()
    payload["approvals"][0]["approver"] = "@developer"
    payload["exception_policies"][0]["policy_spec"]["project_selector"] = {"project_uuid": "proj-123"}
    payload["exception_policies"][0]["policy_spec"]["rego"] = "package bad"

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert any("self-approve" in error for error in errors)
    assert any("project_selector" in error for error in errors)
    assert any("rego" in error for error in errors)


def test_ai_sast_exception_gate_requires_idempotency_check_before_create():
    payload = _valid_payload()
    payload["exception_policies"][0].pop("idempotency_check")

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert "exception_policies[0].idempotency_check: required before Endor policy write" in errors


def test_ai_sast_exception_gate_rejects_duplicate_policy_write():
    payload = _valid_payload()
    payload["exception_policies"][0]["idempotency_check"] = {
        "status": "existing_reused",
        "lookup_method": "endorctl api list -r Policy -n tenant-a filtered by generated policy name and finding UUID",
        "finding_uuid": "finding-12345678",
        "project_uuid": "proj-123",
        "existing_policy_uuid": "policy-123",
        "existing_policy_name": "ai-sast-exception-finding-12345678",
    }

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert any("must be none_found before creating a new policy" in error for error in errors)


def test_ai_sast_exception_gate_accepts_reused_existing_policy_without_new_write():
    payload = _valid_payload()
    payload["exception_policies"][0]["status"] = "existing"
    payload["exception_policies"][0]["user_confirmation"] = "not_required_existing_policy"
    payload["exception_policies"][0]["idempotency_check"] = {
        "status": "existing_reused",
        "lookup_method": "endorctl api list -r Policy -n tenant-a filtered by generated policy name and finding UUID",
        "finding_uuid": "finding-12345678",
        "project_uuid": "proj-123",
        "existing_policy_uuid": "policy-123",
        "existing_policy_name": "ai-sast-exception-finding-12345678",
    }
    payload["exception_policies"][0]["decision_comment"] = (
        render_ai_sast_exception_policy_comment(payload)
    )

    assert validate_ai_sast_gate_payload(payload, gate="exception") == []


def test_ai_sast_exception_gate_accepts_risk_accepted_with_rfc3339_expiration():
    assert validate_ai_sast_gate_payload(_accepted_risk_payload(), gate="exception") == []


def test_ai_sast_exception_gate_requires_accepted_risk_approval_expiration():
    payload = _accepted_risk_payload()
    payload["approvals"][0].pop("expiration_time")

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert "approvals[0].expiration_time: required for accepted risk approval" in errors


def test_ai_sast_exception_gate_rejects_policy_reason_without_matching_approval():
    payload = _valid_payload()
    payload["exception_policies"][0]["policy_spec"]["exception"] = {
        "reason": "EXCEPTION_REASON_RISK_ACCEPTED",
        "expiration_time": "2026-06-30T23:59:59Z",
    }

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert any("no verified approval for accepted_risk" in error for error in errors)


def test_ai_sast_exception_gate_rejects_policy_scope_that_does_not_match_approval():
    payload = _valid_payload()
    payload["exception_policies"][0]["policy_spec"]["project_selector"] = ["$uuid=other-project"]
    payload["exception_policies"][0]["policy_spec"]["rule"] = (
        "package endor_agent_kit_ai_sast_exception\n"
        "match_finding[result] { result := {\"Endor\": {\"Finding\": \"other-finding\"}} }"
    )

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert any("must include '$uuid=proj-123'" in error for error in errors)
    assert any("must match the approved finding UUID" in error for error in errors)


def test_ai_sast_exception_gate_rejects_policy_rule_without_project_scope():
    payload = _valid_payload()
    payload["exception_policies"][0]["policy_spec"]["rule"] = (
        "package endor_agent_kit_ai_sast_exception\n"
        "match_finding[result] {\n"
        "  data.resources.Finding[i].uuid == \"finding-12345678\"\n"
        "  data.resources.Finding[i].meta.parent_uuid == \"proj-123\"\n"
        "  result := {\"Endor\": {\"Finding\": data.resources.Finding[i].uuid}}\n"
        "}"
    )

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert any("must scope findings with spec.project_uuid" in error for error in errors)


def test_ai_sast_exception_gate_rejects_contract_aliases_from_render_only_output():
    payload = _accepted_risk_payload()
    payload["approvals"][0]["expiration"] = payload["approvals"][0].pop("expiration_time")
    payload["approvals"][0].pop("approved")
    payload["exception_policies"][0]["rendered_policy"] = payload["exception_policies"][0].pop(
        "policy_spec"
    )

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert "approvals[0].expiration_time: required for accepted risk approval" in errors
    assert "approvals[0].approved: must be true before policy creation" in errors
    assert any("do not use rendered_policy alias" in error for error in errors)


def test_ai_sast_exception_gate_rejects_policy_rule_with_parent_uuid_scope():
    payload = _valid_payload()
    payload["exception_policies"][0]["policy_spec"]["rule"] = (
        "package endor_agent_kit_ai_sast_exception\n"
        "match_finding[result] {\n"
        "  data.resources.Finding[i].uuid == \"finding-12345678\"\n"
        "  data.resources.Finding[i].spec.project_uuid == \"proj-123\"\n"
        "  data.resources.Finding[i].meta.parent_uuid == \"proj-123\"\n"
        "  result := {\"Endor\": {\"Finding\": data.resources.Finding[i].uuid}}\n"
        "}"
    )

    errors = validate_ai_sast_gate_payload(payload, gate="exception")

    assert any("must not use meta.parent_uuid" in error for error in errors)


def test_ai_sast_exception_gate_accepts_full_policy_resource_shape():
    payload = _accepted_risk_payload()
    policy_spec = payload["exception_policies"][0]["policy_spec"]
    payload["exception_policies"][0]["policy_spec"] = {
        "meta": {
            "name": "ai-sast-exception-finding-12345678",
            "description": "Exception for finding finding-12345678.",
            "tags": ["endor-agent-kit", "ai-sast", "exception"],
        },
        "spec": policy_spec,
    }
    payload["exception_policies"][0].pop("policy_name")

    assert validate_ai_sast_gate_payload(payload, gate="exception") == []


def test_ai_sast_approval_comment_renderer_outputs_lint_clean_request():
    comment = render_ai_sast_approval_comment(_valid_payload())

    assert "## AppSec Approval Request" in comment
    assert "APPSEC APPROVED: false positive for finding finding-12345678" in comment
    assert lint_ai_sast_approval_comment(comment) == []


def test_ai_sast_approval_comment_renderer_outputs_accepted_risk_expiration():
    comment = render_ai_sast_approval_comment(_accepted_risk_payload())

    assert (
        "APPSEC APPROVED: accept risk for finding finding-12345678 "
        "until 2026-06-30"
    ) in comment
    assert lint_ai_sast_approval_comment(comment) == []


def test_ai_sast_exception_policy_comment_renderer_outputs_human_scope():
    comment = render_ai_sast_exception_policy_comment(_accepted_risk_payload())

    assert "## Endor Exception Policy Created" in comment
    assert "- Policy: `ai-sast-exception-finding-12345678`" in comment
    assert "- Policy UUID: `policy-123`" in comment
    assert "- Endor project: `example-app (proj-123)`" in comment
    assert "- Reason: `Accepted risk`" in comment
    assert "$uuid=" not in comment
    assert "Scope:" not in comment
    assert lint_ai_sast_exception_policy_comment(comment) == []


def test_ai_sast_exception_policy_comment_linter_rejects_raw_uuid_scope():
    comment = render_ai_sast_exception_policy_comment(_valid_payload()).replace(
        "- Endor project: `example-app (proj-123)`",
        "- Scope: `$uuid=proj-123`",
    )

    errors = lint_ai_sast_exception_policy_comment(comment)

    assert "policy decision comment must not expose raw '$uuid=' project selector" in errors
    assert "policy decision comment must use 'Endor project', not raw scope" in errors


def test_ai_sast_lints_reject_unsafe_exploit_and_bad_approval_phrase():
    body = render_ai_sast_pr_body(_valid_payload()) + "\nexact exploit payload should not appear.\n"
    bad_comment = render_ai_sast_approval_comment(_accepted_risk_payload()).replace(
        " until 2026-06-30",
        "",
    )

    assert any("exploit context must be sanitized" in error for error in lint_ai_sast_pr_body(body))
    assert "accepted risk approval phrase must include until YYYY-MM-DD" in lint_ai_sast_approval_comment(
        bad_comment
    )


def test_ai_sast_cli_validate_render_and_lint(tmp_path, capsys):
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(_valid_payload()), encoding="utf-8")

    assert main(["validate-ai-sast-output", str(payload_path), "--gate", "remediation"]) == 0
    assert f"OK: {payload_path}" in capsys.readouterr().out

    assert main(["render-ai-sast-pr-body", str(payload_path)]) == 0
    pr_body = capsys.readouterr().out
    pr_body_path = tmp_path / "pr-body.md"
    pr_body_path.write_text(pr_body, encoding="utf-8")

    assert main(["lint-ai-sast-pr-body", str(pr_body_path)]) == 0
    assert f"OK: {pr_body_path}" in capsys.readouterr().out

    assert main(["render-ai-sast-approval-comment", str(payload_path)]) == 0
    comment = capsys.readouterr().out
    comment_path = tmp_path / "approval-comment.md"
    comment_path.write_text(comment, encoding="utf-8")

    assert main(["lint-ai-sast-approval-comment", str(comment_path)]) == 0
    assert f"OK: {comment_path}" in capsys.readouterr().out

    assert main(["render-ai-sast-exception-policy-comment", str(payload_path)]) == 0
    policy_comment = capsys.readouterr().out
    policy_comment_path = tmp_path / "policy-comment.md"
    policy_comment_path.write_text(policy_comment, encoding="utf-8")

    assert main(["lint-ai-sast-exception-policy-comment", str(policy_comment_path)]) == 0
    assert f"OK: {policy_comment_path}" in capsys.readouterr().out


def test_ai_sast_branch_normalizer_uses_remediation_ai_sast_prefix():
    assert (
        normalize_ai_sast_branch("finding-12345678", "Unsafe Redirect")
        == "remediation/ai-sast/unsafe-redirect-12345678"
    )

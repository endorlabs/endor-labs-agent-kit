from __future__ import annotations

import json

from endor_agent_kit.ai_sast_triage import (
    lint_ai_sast_approval_comment,
    lint_ai_sast_pr_body,
    normalize_ai_sast_branch,
    render_ai_sast_approval_comment,
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
                "title": "Fix unsafe redirect target handling",
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
                "policy_uuid": "policy-123",
                "user_confirmation": "approved",
                "policy_spec": {
                    "policy_type": "POLICY_TYPE_EXCEPTION",
                    "exception": {"reason": "EXCEPTION_REASON_FALSE_POSITIVE"},
                    "resource_kinds": ["Finding"],
                    "query_statements": [
                        "data.endor_agent_kit_ai_sast_exception.match_finding"
                    ],
                    "project_selector": ["$uuid=proj-123"],
                    "rule": "package endor_agent_kit_ai_sast_exception\nmatch_finding[result] { result := {\"Endor\": {\"Finding\": \"finding-12345678\"}} }",
                },
            }
        ],
        "data_gaps": [],
    }
    payload["change_requests"][0]["body"] = render_ai_sast_pr_body(payload)
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
    assert "@auri false positive for finding finding-12345678" in body
    assert "AURI: accept risk for finding finding-12345678 until YYYY-MM-DD" in body
    assert "<summary>📎 Finding details</summary>" in body
    assert "| Severity | 🟠 `HIGH` |" in body
    assert "APPSEC APPROVED:" not in body
    assert lint_ai_sast_pr_body(body) == []


def test_ai_sast_gate_validator_rejects_bad_branch_and_missing_body_context():
    payload = _valid_payload()
    payload["patches"][0]["branch_name"] = "endor/fix/finding-12345678"
    payload["change_requests"][0]["branch_name"] = "endor/fix/finding-12345678"
    payload["change_requests"][0]["body"] = "## Missing generated body"

    errors = validate_ai_sast_gate_payload(payload, gate="remediation")

    assert any("endor/fix" in error for error in errors)
    assert any("missing ai-sast-triage marker" in error for error in errors)
    assert any("missing auri:ai-sast-context" in error for error in errors)


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


def test_ai_sast_approval_comment_renderer_outputs_lint_clean_request():
    comment = render_ai_sast_approval_comment(_valid_payload())

    assert "## AppSec Approval Request" in comment
    assert "APPSEC APPROVED: false positive for finding finding-12345678" in comment
    assert lint_ai_sast_approval_comment(comment) == []


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


def test_ai_sast_branch_normalizer_uses_remediation_ai_sast_prefix():
    assert (
        normalize_ai_sast_branch("finding-12345678", "Unsafe Redirect")
        == "remediation/ai-sast/unsafe-redirect-12345678"
    )

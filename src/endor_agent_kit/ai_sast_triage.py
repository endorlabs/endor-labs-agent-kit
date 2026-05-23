"""Mechanical contracts for AI SAST triage agent outputs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CLASSIFICATIONS = frozenset({"TRUE_POSITIVE", "FALSE_POSITIVE", "INCONCLUSIVE"})
EXCEPTION_REASONS = frozenset(
    {"EXCEPTION_REASON_FALSE_POSITIVE", "EXCEPTION_REASON_RISK_ACCEPTED"}
)
APPROVAL_REQUEST_TYPES = frozenset({"false_positive", "accepted_risk"})
BRANCH_RE = re.compile(r"^remediation/ai-sast/[A-Za-z0-9._-]+$")
APPROVAL_PHRASE_RE = re.compile(
    r"^APPSEC APPROVED: "
    r"(?P<type>false positive|accept risk) "
    r"for finding (?P<finding>[A-Za-z0-9._:-]+)"
    r"(?P<until> until \d{4}-\d{2}-\d{2})?"
    r" - .+"
)
AURI_CONTEXT_MARKER_RE = re.compile(
    r"<!--\s*auri:ai-sast-context\s+(?P<payload>\{.*?\})\s*-->"
)
SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}


def load_json_payload(path: str | Path) -> dict[str, Any]:
    """Load a JSON object used by AI SAST contract commands."""

    payload_path = Path(path)
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def validate_ai_sast_gate_payload(
    payload: dict[str, Any],
    *,
    gate: str = "triage",
) -> list[str]:
    """Validate structured output for an AI SAST triage workflow gate."""

    if not isinstance(payload, dict):
        return ["payload: must be an object"]

    errors: list[str] = []
    _validate_project_resolution(payload, errors)
    _validate_verdicts(payload, gate, errors)

    if gate in {"remediation", "pr"}:
        _validate_patches(payload, errors)
        _validate_change_requests(payload, errors)

    if gate == "exception":
        _validate_approvals(payload, errors)
        _validate_exception_policies(payload, errors)

    return errors


def render_ai_sast_pr_body(payload: dict[str, Any]) -> str:
    """Render a reviewer-facing AI SAST remediation PR/MR body."""

    verdict = _selected_verdict(payload)
    patch = _selected_patch(payload)
    project = _dict(payload.get("project_resolution"))
    finding_uuid = _text(
        patch.get("finding_uuid") or verdict.get("finding_uuid") or payload.get("finding_uuid")
    )
    finding_name = _one_line(
        verdict.get("finding_name") or verdict.get("title") or f"Finding {finding_uuid}"
    )
    file_path = _text(
        patch.get("file_path")
        or verdict.get("file_path")
        or verdict.get("source_location")
        or payload.get("file_path")
    )
    source_sha = _text(patch.get("source_sha") or verdict.get("source_sha"))
    repo_full_name = _text(project.get("repo_full_name") or payload.get("repo_full_name"))
    project_uuid = _text(project.get("project_uuid") or payload.get("project_uuid"))
    namespace = _text(project.get("namespace") or payload.get("namespace"))
    classification = _text(verdict.get("classification") or "TRUE_POSITIVE")
    severity = _text(verdict.get("severity") or "not provided")
    cwe = _format_inline_list(
        _string_list(
            verdict.get("cwe")
            or verdict.get("cwes")
            or verdict.get("cwe_ids")
            or verdict.get("cwe_id")
        )
    )
    finding_url = _text(verdict.get("finding_url") or payload.get("finding_url"))
    if not finding_url and namespace and finding_uuid:
        finding_url = f"https://app.endorlabs.com/t/{namespace}/findings/{finding_uuid}"
    changed_files = _string_list(patch.get("changed_files") or patch.get("files") or file_path)

    context = {
        "finding_uuid": finding_uuid,
        "namespace": namespace,
        "project_uuid": project_uuid,
        "repo_full_name": repo_full_name,
        "file_path": file_path,
    }
    context_json = json.dumps(
        {key: value for key, value in context.items() if value},
        sort_keys=True,
        separators=(",", ":"),
    )

    lines = [
        f"## 🛡️ Endor Labs AURI Security Fix: {finding_name}",
        "<!-- endor-agent-kit:ai-sast-triage -->",
        f"<!-- auri:ai-sast-context {context_json} -->",
        "",
        (
            "AURI confirmed this AI SAST finding as "
            f"**{_display_classification(classification)}** with "
            f"{_display_severity(severity)} severity. This PR applies the "
            "generated remediation for review."
        ),
        "",
        "### 🔧 What changed",
        "",
        *_render_changed_files(changed_files),
        f"- {_sentence(patch.get('patch_summary') or patch.get('patch_reason') or patch.get('reason') or 'The patch addresses the vulnerability identified by Endor')}",
        "",
        "### 🔎 Evidence provided by AURI",
        "",
        *_render_evidence_lines(verdict, file_path),
        "",
        "### ✅ Review checklist",
        "",
        "- [ ] Confirm the data flow and affected component match the service behavior.",
        "- [ ] Confirm the remediation preserves valid inputs and expected output shape.",
        "- [ ] Run the relevant service tests or smoke tests before merge.",
        "- [ ] If this should not be fixed in code, use the exception request format below.",
        "",
        "### 📝 Need an exception instead?",
        "",
        (
            "If you believe this is a false positive or the team needs to accept "
            "the risk, comment on this PR with one of these exact forms:"
        ),
        "",
        "```text",
        f"@auri false positive for finding {finding_uuid or '<finding_uuid>'} - <why this is not exploitable>",
        f"@auri accept risk for finding {finding_uuid or '<finding_uuid>'} until YYYY-MM-DD - <owner, mitigation, and why code will not change now>",
        f"AURI: false positive for finding {finding_uuid or '<finding_uuid>'} - <why this is not exploitable>",
        f"AURI: accept risk for finding {finding_uuid or '<finding_uuid>'} until YYYY-MM-DD - <owner, mitigation, and why code will not change now>",
        "```",
        "",
        (
            "AURI will create a pending request in **AI SAST Command Center -> "
            "Exception inbox**. Security approval creates a scoped Endor Labs "
            "exception policy for this finding in this repository/project, with "
            "reviewer-selected reason, expiration, and tags."
        ),
        "",
        (
            "In standalone Agent Kit mode, the agent must still verify AppSec "
            "approval evidence on the PR/MR, render the scoped Endor policy spec, "
            "and receive explicit confirmation before writing any policy."
        ),
        "",
        "<details>",
        "<summary>📎 Finding details</summary>",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Endor finding | {_format_finding_link(finding_uuid, finding_url)} |",
        f"| CWE | {cwe} |",
        f"| Classification | `{classification or 'not provided'}` |",
        f"| Severity | {_display_severity_code(severity)} |",
        f"| Patch confidence | {_format_confidence(patch.get('patch_confidence') or patch.get('confidence'))} |",
        f"| Finding/source file | `{file_path or 'not provided'}` |",
        f"| Modified files | {_format_table_file_list(changed_files)} |",
        f"| Generated against SHA | `{source_sha or 'not provided'}` |",
        f"| Repository | `{repo_full_name or 'not provided'}` |",
        f"| Endor project | `{project_uuid or 'not provided'}` |",
        "",
        "</details>",
    ]
    lines.extend(
        [
            "",
            "_Generated by AURI Security Agent. Review the diff carefully before merging; the linked Endor Labs finding remains the source of truth._",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def lint_ai_sast_pr_body(body: str) -> list[str]:
    """Lint a reviewer-facing AI SAST remediation PR/MR body."""

    errors: list[str] = []
    if body.count("```") % 2:
        errors.append("unclosed fenced code block")
    if "<!-- endor-agent-kit:ai-sast-triage -->" not in body:
        errors.append("missing ai-sast-triage marker")
    context = AURI_CONTEXT_MARKER_RE.search(body)
    if context is None:
        errors.append("missing auri:ai-sast-context hidden marker")
    else:
        try:
            context_payload = json.loads(context.group("payload"))
        except json.JSONDecodeError:
            errors.append("auri:ai-sast-context marker is not valid JSON")
        else:
            for field in ("finding_uuid", "project_uuid", "repo_full_name", "file_path"):
                if not _text(_dict(context_payload).get(field)):
                    errors.append(f"auri:ai-sast-context.{field}: required")

    for heading in (
        "## 🛡️ Endor Labs AURI Security Fix:",
        "### 🔧 What changed",
        "### 🔎 Evidence provided by AURI",
        "### ✅ Review checklist",
        "### 📝 Need an exception instead?",
        "<summary>📎 Finding details</summary>",
    ):
        if heading not in body:
            errors.append(f"missing section {heading!r}")

    for request_prefix in (
        "@auri false positive for finding",
        "@auri accept risk for finding",
        "AURI: false positive for finding",
        "AURI: accept risk for finding",
    ):
        if request_prefix not in body:
            errors.append(f"missing exception request form {request_prefix!r}")

    if "APPSEC APPROVED:" in body:
        errors.append("PR/MR body must request approval separately, not embed an approval phrase")
    if re.search(r"(?i)(weaponized payload|exact exploit payload|copy/paste exploit)", body):
        errors.append("exploit context must be sanitized and must not publish exact payload detail")
    errors.extend(_lint_severity_emoji(body))
    return errors


def render_ai_sast_approval_comment(payload: dict[str, Any]) -> str:
    """Render the standalone AppSec approval request comment."""

    request = _dict(payload.get("approval_request") or payload.get("exception_request"))
    verdict = _selected_verdict(payload)
    project = _dict(payload.get("project_resolution"))
    finding_uuid = _text(
        request.get("finding_uuid") or verdict.get("finding_uuid") or payload.get("finding_uuid")
    )
    request_type = _text(request.get("request_type") or "false_positive")
    reason = _one_line(request.get("reason") or request.get("justification") or "not provided")
    expiration = _text(request.get("expiration_time") or request.get("until"))

    if request_type == "accepted_risk":
        phrase = (
            f"APPSEC APPROVED: accept risk for finding {finding_uuid} "
            f"until {expiration or 'YYYY-MM-DD'} - <owner, mitigation, and why code will not change now>"
        )
    else:
        phrase = (
            f"APPSEC APPROVED: false positive for finding {finding_uuid} "
            "- <why this is not exploitable>"
        )

    context = {
        "finding_uuid": finding_uuid,
        "request_type": request_type,
        "project_uuid": _text(project.get("project_uuid")),
        "namespace": _text(project.get("namespace")),
    }
    context_json = json.dumps(
        {key: value for key, value in context.items() if value},
        sort_keys=True,
        separators=(",", ":"),
    )

    return "\n".join(
        [
            "<!-- endor-agent-kit:ai-sast-approval-request "
            + context_json
            + " -->",
            "## AppSec Approval Request",
            "",
            f"- Finding UUID: `{finding_uuid or 'not provided'}`",
            f"- Request type: `{request_type}`",
            f"- Reason: {reason}",
            f"- Expiration: `{expiration or 'not applicable'}`",
            "",
            "An allowed AppSec approver may approve with this exact form:",
            "",
            "```text",
            phrase,
            "```",
            "",
            "The requester, PR/MR author, and agent account must not approve this request.",
        ]
    ).rstrip() + "\n"


def lint_ai_sast_approval_comment(body: str) -> list[str]:
    """Lint an AI SAST standalone exception approval request comment."""

    errors: list[str] = []
    if "<!-- endor-agent-kit:ai-sast-approval-request " not in body:
        errors.append("missing ai-sast approval request marker")
    phrases = [
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith("APPSEC APPROVED:")
    ]
    if not phrases:
        errors.append("missing APPSEC APPROVED phrase")
    for phrase in phrases:
        match = APPROVAL_PHRASE_RE.match(phrase)
        if match is None:
            errors.append(f"invalid APPSEC APPROVED phrase: {phrase}")
            continue
        if match.group("type") == "accept risk" and not match.group("until"):
            errors.append("accepted risk approval phrase must include until YYYY-MM-DD")
    if "must not approve" not in body:
        errors.append("missing self-approval warning")
    return errors


def normalize_ai_sast_branch(finding_uuid: str, finding_name: str = "") -> str:
    """Return a stable AI SAST remediation branch name."""

    slug_source = finding_name or finding_uuid
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", slug_source.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "finding"
    suffix = re.sub(r"[^A-Za-z0-9._-]+", "", finding_uuid)[-8:]
    if suffix and suffix.lower() not in slug:
        slug = f"{slug}-{suffix}"
    return f"remediation/ai-sast/{slug}"


def _validate_project_resolution(payload: dict[str, Any], errors: list[str]) -> None:
    project = _dict(payload.get("project_resolution"))
    project_uuid = _text(payload.get("project_uuid") or project.get("project_uuid"))
    namespace = _text(payload.get("namespace") or project.get("namespace"))
    namespace_provenance = _text(
        payload.get("namespace_provenance") or project.get("namespace_provenance")
    )
    repo = _text(payload.get("repo_full_name") or project.get("repo_full_name"))
    if not project_uuid:
        errors.append("project_resolution.project_uuid: required for AI SAST workflow gates")
    if not namespace:
        errors.append("project_resolution.namespace: required for AI SAST workflow gates")
    if not namespace_provenance:
        errors.append("project_resolution.namespace_provenance: required before scoped Endor queries")
    if not repo:
        errors.append("project_resolution.repo_full_name: required for repository provenance")


def _validate_verdicts(payload: dict[str, Any], gate: str, errors: list[str]) -> None:
    verdicts = _list(payload.get("verdicts"))
    if not verdicts:
        errors.append("verdicts: required non-empty list")
        return
    for index, verdict in enumerate(verdicts):
        if not isinstance(verdict, dict):
            errors.append(f"verdicts[{index}]: must be an object")
            continue
        prefix = f"verdicts[{index}]"
        finding_uuid = _text(verdict.get("finding_uuid") or verdict.get("uuid"))
        if not finding_uuid:
            errors.append(f"{prefix}.finding_uuid: required")
        classification = _text(verdict.get("classification"))
        if classification and classification not in CLASSIFICATIONS:
            errors.append(f"{prefix}.classification: must be one of {', '.join(sorted(CLASSIFICATIONS))}")
        source_location = _text(verdict.get("source_location"))
        if not source_location:
            errors.append(f"{prefix}.source_location: required")
        if not _text(verdict.get("file_path")):
            errors.append(f"{prefix}.file_path: required")
        if gate in {"remediation", "pr"} and classification == "TRUE_POSITIVE":
            if _is_empty(verdict.get("exploit_reproduction_summary")):
                errors.append(f"{prefix}.exploit_reproduction_summary: required for remediation")
            if _is_empty(verdict.get("remediation_guidance_summary")):
                errors.append(f"{prefix}.remediation_guidance_summary: required for remediation")


def _validate_patches(payload: dict[str, Any], errors: list[str]) -> None:
    patches = _list(payload.get("patches"))
    if not patches:
        errors.append("patches: required for remediation gate")
        return
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict):
            errors.append(f"patches[{index}]: must be an object")
            continue
        prefix = f"patches[{index}]"
        for field in ("finding_uuid", "source_sha", "patch_diff", "validation_plan"):
            if _is_empty(patch.get(field)):
                errors.append(f"{prefix}.{field}: required")
        if _is_empty(patch.get("remediation_guidance_used")) and _is_empty(
            patch.get("remediation_guidance_rejected")
        ):
            errors.append(
                f"{prefix}.remediation_guidance_used: required unless remediation_guidance_rejected is present"
            )
        branch = _text(_first_present(patch, "branch_name", "branch", "proposed_branch"))
        if branch:
            _validate_branch(branch, f"{prefix}.branch_name", errors)


def _validate_change_requests(payload: dict[str, Any], errors: list[str]) -> None:
    change_requests = _list(payload.get("change_requests"))
    if not change_requests:
        errors.append("change_requests: required for remediation gate")
        return
    for index, request in enumerate(change_requests):
        if not isinstance(request, dict):
            errors.append(f"change_requests[{index}]: must be an object")
            continue
        prefix = f"change_requests[{index}]"
        for field in ("title", "body"):
            if not _text(request.get(field)):
                errors.append(f"{prefix}.{field}: required")
        branch = _text(_first_present(request, "branch_name", "branch", "proposed_branch"))
        if not branch:
            errors.append(f"{prefix}.branch_name: required")
        else:
            _validate_branch(branch, f"{prefix}.branch_name", errors)
        body = _text(request.get("body"))
        if body:
            errors.extend(f"{prefix}.body: {error}" for error in lint_ai_sast_pr_body(body))
        approval = request.get("user_approval") or request.get("approval_status")
        status = _text(request.get("status")).lower()
        if status in {"opened", "created", "pushed"} and _text(approval).lower() not in {
            "approved",
            "confirmed",
            "true",
        }:
            errors.append(f"{prefix}.user_approval: required before push or PR/MR creation")


def _validate_approvals(payload: dict[str, Any], errors: list[str]) -> None:
    approvals = _list(payload.get("approvals"))
    if not approvals:
        errors.append("approvals: required before exception policy creation")
        return
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            errors.append(f"approvals[{index}]: must be an object")
            continue
        prefix = f"approvals[{index}]"
        for field in ("finding_uuid", "approver", "approval_evidence_url", "request_type"):
            if not _text(approval.get(field)):
                errors.append(f"{prefix}.{field}: required")
        request_type = _text(approval.get("request_type"))
        if request_type and request_type not in APPROVAL_REQUEST_TYPES:
            errors.append(f"{prefix}.request_type: unsupported request type {request_type!r}")
        if approval.get("approved") is not True and _text(approval.get("status")).lower() != "approved":
            errors.append(f"{prefix}.approved: must be true before policy creation")
        approver = _identity(approval.get("approver"))
        forbidden = {
            _identity(approval.get("requester")),
            _identity(approval.get("pr_author")),
            _identity(approval.get("agent_account")),
        } - {""}
        if approver in forbidden:
            errors.append(f"{prefix}.approver: requester, PR/MR author, or agent cannot self-approve")
        allowed = {_identity(item) for item in _list(approval.get("allowed_approvers"))}
        if allowed and approver not in allowed:
            errors.append(f"{prefix}.approver: approver is not in allowed_approvers")


def _validate_exception_policies(payload: dict[str, Any], errors: list[str]) -> None:
    policies = _list(payload.get("exception_policies"))
    if not policies:
        errors.append("exception_policies: required for exception gate")
        return
    for index, policy in enumerate(policies):
        if not isinstance(policy, dict):
            errors.append(f"exception_policies[{index}]: must be an object")
            continue
        prefix = f"exception_policies[{index}]"
        if _text(policy.get("status")).lower() in {"created", "written"}:
            if not _text(policy.get("policy_uuid")):
                errors.append(f"{prefix}.policy_uuid: required when policy is created")
        if _text(policy.get("user_confirmation")).lower() not in {"approved", "confirmed", "true"}:
            errors.append(f"{prefix}.user_confirmation: required before Endor policy write")
        spec = _dict(policy.get("policy_spec") or policy.get("spec"))
        _validate_policy_spec(spec, prefix, errors)


def _validate_policy_spec(spec: dict[str, Any], prefix: str, errors: list[str]) -> None:
    if not spec:
        errors.append(f"{prefix}.policy_spec: required")
        return
    policy_type = _text(spec.get("policy_type"))
    if policy_type and policy_type != "POLICY_TYPE_EXCEPTION":
        errors.append(f"{prefix}.policy_spec.policy_type: must be POLICY_TYPE_EXCEPTION")
    exception = _dict(spec.get("exception"))
    reason = _text(exception.get("reason"))
    if reason and reason not in EXCEPTION_REASONS:
        errors.append(f"{prefix}.policy_spec.exception.reason: unsupported reason {reason!r}")
    if reason == "EXCEPTION_REASON_RISK_ACCEPTED" and not _text(exception.get("expiration_time")):
        errors.append(f"{prefix}.policy_spec.exception.expiration_time: required for accepted risk")
    if spec.get("resource_kinds") != ["Finding"]:
        errors.append(f"{prefix}.policy_spec.resource_kinds: must be ['Finding']")
    statements = _list(spec.get("query_statements"))
    if "data.endor_agent_kit_ai_sast_exception.match_finding" not in statements:
        errors.append(f"{prefix}.policy_spec.query_statements: missing AI SAST exception query")
    if "rego" in spec:
        errors.append(f"{prefix}.policy_spec.rego: do not use rego field; use rule")
    if not _text(spec.get("rule")):
        errors.append(f"{prefix}.policy_spec.rule: required")
    project_selector = spec.get("project_selector")
    if not isinstance(project_selector, list) or not all(
        isinstance(item, str) and item.startswith("$uuid=") for item in project_selector
    ):
        errors.append(f"{prefix}.policy_spec.project_selector: must be list of '$uuid=PROJECT_UUID'")


def _validate_branch(branch: str, field: str, errors: list[str]) -> None:
    if branch.lower() in {"not_created", "none", "n/a", "out_of_scope_per_user"}:
        return
    if branch.startswith("endor/fix/"):
        errors.append(f"{field}: {branch!r} uses disallowed endor/fix prefix")
    elif not BRANCH_RE.match(branch):
        errors.append(f"{field}: {branch!r} must match remediation/ai-sast/<finding-slug>")


def _selected_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    verdicts = _list(payload.get("verdicts"))
    for verdict in verdicts:
        if isinstance(verdict, dict) and _text(verdict.get("classification")) == "TRUE_POSITIVE":
            return verdict
    for verdict in verdicts:
        if isinstance(verdict, dict):
            return verdict
    return {}


def _selected_patch(payload: dict[str, Any]) -> dict[str, Any]:
    for patch in _list(payload.get("patches")):
        if isinstance(patch, dict):
            return patch
    return {}


def _display_classification(classification: str) -> str:
    value = _text(classification).replace("_", " ").strip()
    return value.title() if value else "Not Provided"


def _normalize_severity(severity: Any) -> str:
    return _text(severity).replace("_", " ").strip().upper()


def _display_severity(severity: Any) -> str:
    value = _normalize_severity(severity)
    if not value or value == "NOT PROVIDED":
        return "**not provided**"
    emoji = SEVERITY_EMOJI.get(value)
    return f"{emoji} **{value}**" if emoji else f"**{value}**"


def _display_severity_code(severity: Any) -> str:
    value = _normalize_severity(severity)
    if not value or value == "NOT PROVIDED":
        return "`not provided`"
    emoji = SEVERITY_EMOJI.get(value)
    return f"{emoji} `{value}`" if emoji else f"`{value}`"


def _render_changed_files(changed_files: list[str]) -> list[str]:
    if not changed_files:
        return ["- Updated `not provided`."]
    return [f"- Updated `{file_path}`." for file_path in changed_files]


def _render_evidence_lines(verdict: dict[str, Any], file_path: str) -> list[str]:
    lines: list[str] = []
    evidence = _list(
        verdict.get("evidence")
        or verdict.get("data_flow_anchors")
        or verdict.get("data_flow_evidence")
        or verdict.get("source_evidence")
    )
    for item in evidence:
        line = _format_evidence_item(item)
        if line:
            lines.append(line)

    if lines:
        return lines

    data_flow = _one_line(verdict.get("data_flow_summary") or verdict.get("data_flow"))
    scorecard = _one_line(verdict.get("scorecard_summary") or verdict.get("verification_scorecard"))
    priority = _one_line(verdict.get("priority_rationale"))
    if file_path:
        detail = data_flow or "affected source location from Endor AI SAST evidence."
        lines.append(f"- **Source:** `{file_path}` - {_sentence(detail)}")
    if scorecard:
        lines.append(f"- **Verification scorecard:** {_sentence(scorecard)}")
    if priority:
        lines.append(f"- **Priority rationale:** {_sentence(priority)}")
    return lines or ["- **Evidence:** not provided."]


def _format_evidence_item(item: Any) -> str:
    if isinstance(item, str):
        text = _one_line(item)
        return f"- **Evidence:** {text}" if text else ""
    if not isinstance(item, dict):
        return ""

    label = _one_line(
        item.get("label")
        or item.get("kind")
        or item.get("type")
        or item.get("stage")
        or "Evidence"
    )
    location = _one_line(item.get("location") or item.get("file_path") or item.get("path"))
    line = _one_line(item.get("line") or item.get("line_number"))
    if location and line and f":{line}" not in location:
        location = f"{location}#L{line}"
    url = _text(item.get("url") or item.get("source_url"))
    snippet = _one_line(item.get("snippet") or item.get("code"))
    note = _one_line(item.get("note") or item.get("summary") or item.get("description"))

    parts: list[str] = []
    if url:
        parts.append(f"[{location or label}]({url})")
    elif location:
        parts.append(f"`{location}`")
    if snippet:
        parts.append(f"`{snippet}`")
    if note:
        parts.append(_sentence(note))
    if not parts:
        return ""
    return f"- **{label}:** " + " - ".join(parts)


def _format_finding_link(finding_uuid: str, finding_url: str) -> str:
    if finding_uuid and finding_url:
        return f"[{finding_uuid}]({finding_url})"
    if finding_uuid:
        return f"`{finding_uuid}`"
    return "`not provided`"


def _format_table_file_list(files: list[str]) -> str:
    if not files:
        return "`not provided`"
    return "<br>".join(f"`{file_path}`" for file_path in files)


def _format_confidence(confidence: Any) -> str:
    value = _text(confidence)
    if not value:
        return "`not provided`"
    return value if "/" in value else f"`{value}/100`"


def _sentence(value: Any) -> str:
    text = _one_line(value)
    if not text:
        return "not provided."
    if text.endswith((".", "!", "?")):
        return text
    return text + "."


def _lint_severity_emoji(body: str) -> list[str]:
    errors: list[str] = []
    for severity, emoji in SEVERITY_EMOJI.items():
        if f"**{severity}**" in body and f"{emoji} **{severity}**" not in body:
            errors.append(f"{severity} severity must be prefixed with {emoji}")
        if f"`{severity}`" in body and f"{emoji} `{severity}`" not in body:
            errors.append(f"{severity} severity detail must be prefixed with {emoji}")
    return errors


def _format_inline_list(value: list[str]) -> str:
    if not value:
        return "`not provided`"
    return ", ".join(f"`{item}`" for item in value)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True)
    return str(value).strip()


def _one_line(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if not _is_empty(value):
            return value
    return None


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def _identity(value: Any) -> str:
    return _text(value).lower().lstrip("@")

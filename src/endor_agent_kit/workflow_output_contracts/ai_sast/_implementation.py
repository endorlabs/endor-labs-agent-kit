"""Mechanical contracts for AI SAST triage agent outputs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any

CLASSIFICATIONS = frozenset({"TRUE_POSITIVE", "FALSE_POSITIVE", "INCONCLUSIVE"})
EXCEPTION_REASONS = frozenset(
    {"EXCEPTION_REASON_FALSE_POSITIVE", "EXCEPTION_REASON_RISK_ACCEPTED"}
)
APPROVAL_REQUEST_TYPES = frozenset({"false_positive", "accepted_risk"})
EXCEPTION_MATCH_STRATEGIES = frozenset({"ai_sast_fingerprint", "vulnerability_alias"})
EXCEPTION_POLICY_IDEMPOTENCY_STATUSES = frozenset(
    {
        "none_found",
        "existing_reused",
        "blocked_duplicate",
        "expired_existing_needs_review",
    }
)
CHANGE_REQUEST_LOOKUP_STATUSES = frozenset(
    {
        "none_found",
        "existing_found",
        "branch_found",
        "lookup_unavailable",
    }
)
BRANCH_RE = re.compile(r"^remediation/ai-sast/[A-Za-z0-9._-]+$")
SEVERITY_TITLE_RE = re.compile(r"^(🔴 Critical|🟠 High|🟡 Medium|🟢 Low)\b")
APPROVAL_PHRASE_RE = re.compile(
    r"^APPSEC APPROVED: "
    r"(?P<type>false positive|accept risk) "
    r"for finding (?P<finding>[A-Za-z0-9._:-]+)"
    r"(?P<until> until \d{4}-\d{2}-\d{2})?"
    r" - .+"
)
RFC3339_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
AURI_CONTEXT_MARKER_RE = re.compile(
    r"<!--\s*auri:ai-sast-context\s+(?P<payload>\{.*?\})\s*-->"
)
EXCEPTION_POLICY_MARKER_RE = re.compile(
    r"<!--\s*endor-agent-kit:ai-sast-exception-policy\s+(?P<payload>\{.*?\})\s*-->"
)
SEVERITY_EMOJI = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}

CHANGE_IMPACT_STATUSES = frozenset({"verified", "blocked", "unavailable", "not_applicable"})
SUPPORTED_CHANGE_IMPACT_EXTENSIONS = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
}
_VOLATILE_DIFF_METADATA_RE = re.compile(
    r"^(?:index [0-9a-f]+\.\.[0-9a-f]+(?: \d+)?|similarity index|dissimilarity index|old mode|new mode)"
)


@dataclass(frozen=True)
class ChangeImpactClassification:
    status: str
    trigger_classes: tuple[str, ...]
    touched_paths: tuple[str, ...]
    languages: tuple[str, ...]


def canonical_ai_sast_diff(diff: str | bytes) -> bytes:
    """Return the frozen byte-exact canonical representation of a unified diff."""

    if isinstance(diff, bytes):
        try:
            text = diff.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("patch diff is not valid UTF-8") from exc
    else:
        text = diff
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.split("\n") if not _VOLATILE_DIFF_METADATA_RE.match(line)]
    while lines and lines[-1] == "":
        lines.pop()
    return ("\n".join(lines) + "\n").encode("utf-8")


def ai_sast_patch_digest(diff: str | bytes, *, source_sha: str, finding_uuid: str) -> str:
    """Bind canonical patch bytes to the source revision and finding identity."""

    material = (
        canonical_ai_sast_diff(diff)
        + b"\x1e"
        + source_sha.encode("utf-8")
        + b"\x1e"
        + finding_uuid.encode("utf-8")
    )
    return hashlib.sha256(material).hexdigest()


def classify_ai_sast_change_impact(diff: str | bytes) -> ChangeImpactClassification:
    """Classify compatibility-sensitive trigger classes from supported-language diff lines."""

    try:
        text = canonical_ai_sast_diff(diff).decode("utf-8")
    except ValueError:
        return ChangeImpactClassification("unknown", (), (), ())
    if _lint_unified_diff(text):
        return ChangeImpactClassification("unknown", (), tuple(_diff_touched_paths(text)), ())
    paths = tuple(_diff_touched_paths(text))
    languages = tuple(
        sorted(
            {
                SUPPORTED_CHANGE_IMPACT_EXTENSIONS[Path(path).suffix.lower()]
                for path in paths
                if Path(path).suffix.lower() in SUPPORTED_CHANGE_IMPACT_EXTENSIONS
            }
        )
    )
    if not languages:
        return ChangeImpactClassification("unknown", (), paths, ())

    changed_lines = [
        line[1:]
        for line in text.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    triggers: set[str] = set()
    for line in changed_lines:
        if _change_impact_signature_line(line, languages):
            triggers.add("A")
        if re.search(
            r"(?:@(?:Inject|Autowired|Provides|Bean|ConfigurationProperties|Value|Injectable)\b|"
            r"\bDepends\s*\(|\b(?:process\.env|os\.Getenv|viper\.|config\[|config\.)|"
            r"\b(?:wire\.Build|fx\.Provide)\b)",
            line,
        ):
            triggers.add("B")
        if re.match(r"\s*(?:import\b|from\s+\S+\s+import\b|const\s+\S+\s*=\s*require\s*\()", line):
            triggers.add("C")
        if re.search(
            r"(?i)(?:\bfactory\b|\bprovider\b|\bregister(?:ed|ing)?\b|"
            r"container\.bind|services\.add|@Bean\b|fx\.Provide\b|wire\.Build\b)",
            line,
        ):
            triggers.add("D")
    return ChangeImpactClassification("classified", tuple(sorted(triggers)), paths, languages)


def _change_impact_signature_line(line: str, languages: tuple[str, ...]) -> bool:
    patterns = {
        "python": r"\s*(?:async\s+)?def\s+(?:__init__|[A-Za-z][A-Za-z0-9_]*)\s*\(",
        "java": r"\s*(?:public|protected)\s+(?:[\w<>\[\],.?]+\s+)?[A-Za-z][A-Za-z0-9_]*\s*\(",
        "javascript": r"\s*(?:export\s+)?(?:async\s+)?function\s+[A-Za-z][A-Za-z0-9_]*\s*\(",
        "typescript": r"\s*(?:(?:export\s+)?(?:async\s+)?function\s+[A-Za-z][A-Za-z0-9_]*|(?:public\s+)?constructor)\s*\(",
        "go": r"\s*func\s+(?:\([^)]*\)\s*)?[A-Z][A-Za-z0-9_]*\s*\(",
    }
    return any(re.match(patterns[language], line) for language in languages)


def _diff_touched_paths(diff: str) -> list[str]:
    paths: list[str] = []
    for line in diff.splitlines():
        if not line.startswith(("--- ", "+++ ")):
            continue
        path = line[4:].split("\t", 1)[0]
        if path == "/dev/null":
            continue
        if path.startswith(("a/", "b/")):
            path = path[2:]
        paths.append(path)
    return sorted(dict.fromkeys(paths))


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
    change_request = _selected_change_request(payload)
    change_request_url = _text(
        change_request.get("url")
        or change_request.get("html_url")
        or change_request.get("pr_url")
        or payload.get("pr_url")
        or payload.get("change_request_url")
        or "<pr_or_mr_url>"
    )
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
    explicit_changed_files = _unique_strings(
        _string_list(
            patch.get("changed_files")
            or patch.get("modified_files")
            or patch.get("files")
        )
        + _string_list(
            change_request.get("changed_files")
            or change_request.get("modified_files")
            or change_request.get("files")
        )
    )
    changed_files = explicit_changed_files or _string_list(file_path)

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
            "If this finding should be excepted instead of fixed in code, copy "
            "one of these prompts into your standalone Agent Kit session:"
        ),
        "",
        "```text",
        (
            "@agent-ai-sast-triage request an AppSec exception review for "
            f"finding {finding_uuid or '<finding_uuid>'} on PR/MR {change_request_url}. "
            "Request type: false positive. Reason: <why this is not exploitable>. "
            "Allowed AppSec approvers: <@appsec-reviewer>. Do not create an Endor "
            "policy yet. Post or update a PR/MR comment with the exact approval "
            "phrase the approver can use."
        ),
        (
            "@agent-ai-sast-triage request an AppSec exception review for "
            f"finding {finding_uuid or '<finding_uuid>'} on PR/MR {change_request_url}. "
            "Request type: accept risk until YYYY-MM-DD. Reason: <owner, mitigation, "
            "and why code will not change now>. Allowed AppSec approvers: "
            "<@appsec-reviewer>. Do not create an Endor policy yet. Post or update "
            "a PR/MR comment with the exact approval phrase the approver can use."
        ),
        "```",
        "",
        (
            "The standalone agent will create or update an approval-request "
            "comment for an allowed AppSec approver. The requester, PR/MR author, "
            "and agent account must not approve their own exception request."
        ),
        "",
        (
            "The agent must verify AppSec approval evidence on the PR/MR, render "
            "the scoped Endor policy spec, and receive explicit confirmation "
            "before writing any Endor policy."
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
            for field in ("finding_uuid", "namespace", "project_uuid", "repo_full_name", "file_path"):
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
        "@agent-ai-sast-triage request an AppSec exception review for finding",
        "Request type: false positive",
        "Request type: accept risk until YYYY-MM-DD",
        "Allowed AppSec approvers:",
        "Do not create an Endor policy yet",
    ):
        if request_prefix not in body:
            errors.append(f"missing standalone exception request form {request_prefix!r}")

    if "APPSEC APPROVED:" in body:
        errors.append("PR/MR body must request approval separately, not embed an approval phrase")
    if re.search(r"(?m)^\s*(?:@auri|AURI:)\b", body):
        errors.append("PR/MR body must use standalone Agent Kit exception request prompts, not AURI request forms")
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


def render_ai_sast_exception_policy_comment(payload: dict[str, Any]) -> str:
    """Render a reviewer-facing comment after an Endor exception policy decision."""

    policy = _selected_exception_policy(payload)
    spec = _policy_spec_payload(policy.get("policy_spec") or policy.get("spec"))
    project = _dict(payload.get("project_resolution"))
    verdict = _selected_verdict(payload)
    approval = _selected_policy_approval(payload, spec)

    finding_uuid = _text(
        policy.get("finding_uuid")
        or approval.get("finding_uuid")
        or verdict.get("finding_uuid")
        or payload.get("finding_uuid")
    )
    finding_name = _one_line(
        policy.get("finding_name")
        or verdict.get("finding_name")
        or verdict.get("title")
        or f"Finding {finding_uuid}"
    )
    policy_name = _policy_name(policy) or "not provided"
    policy_uuid = _text(policy.get("policy_uuid") or policy.get("uuid")) or "not provided"
    namespace = _text(project.get("namespace") or payload.get("namespace"))
    project_uuid = _text(project.get("project_uuid") or payload.get("project_uuid"))
    project_name = _text(
        project.get("project_name")
        or policy.get("project_name")
        or project.get("repo_full_name")
        or payload.get("repo_full_name")
    )
    project_label = project_name or "not provided"
    if project_uuid:
        project_label = f"{project_label} ({project_uuid})"

    exception = _dict(spec.get("exception"))
    reason = _display_exception_reason(_text(exception.get("reason")))
    expiration = _text(exception.get("expiration_time") or approval.get("expiration_time"))
    request_type = _text(approval.get("request_type")) or _request_type_for_exception_reason(
        _text(exception.get("reason"))
    )
    status = _text(policy.get("status")).lower()
    heading = (
        "## Endor Exception Policy Reused"
        if status in {"existing", "reused", "existing_reused"}
        else "## Endor Exception Policy Created"
    )

    marker = {
        "finding_uuid": finding_uuid,
        "namespace": namespace,
        "project_uuid": project_uuid,
        "policy_name": policy_name,
        "policy_uuid": policy_uuid,
        "request_type": request_type,
    }
    exception_match = _exception_match(policy)
    match_strategy = _text(exception_match.get("strategy"))
    match_fingerprint = _text(
        exception_match.get("match_fingerprint") or exception_match.get("fingerprint")
    )
    if match_strategy:
        marker["match_strategy"] = match_strategy
    if match_fingerprint:
        marker["match_fingerprint"] = match_fingerprint
    marker_json = json.dumps(
        {key: value for key, value in marker.items() if value and value != "not provided"},
        sort_keys=True,
        separators=(",", ":"),
    )

    evidence_url = _text(approval.get("approval_evidence_url"))
    evidence_value = evidence_url if evidence_url else "`not provided`"

    return "\n".join(
        [
            "<!-- endor-agent-kit:ai-sast-exception-policy " + marker_json + " -->",
            heading,
            "",
            f"- Policy: `{policy_name}`",
            f"- Policy UUID: `{policy_uuid}`",
            f"- Finding: {finding_name} (`{finding_uuid or 'not provided'}`)",
            f"- Stable match: `{match_strategy or 'not provided'}` (`{match_fingerprint or 'not provided'}`)",
            f"- Endor project: `{project_label}`",
            f"- Namespace: `{namespace or 'not provided'}`",
            f"- Reason: {reason}",
            f"- Expires: `{expiration or 'not applicable'}`",
            f"- Approved by: `{_text(approval.get('approver')) or 'not provided'}`",
            f"- Approval evidence: {evidence_value}",
            "",
            (
                "The policy is scoped to the Endor project and exact finding above. "
                "The API policy payload remains the source of truth for enforcement."
            ),
        ]
    ).rstrip() + "\n"


def lint_ai_sast_exception_policy_comment(body: str) -> list[str]:
    """Lint a reviewer-facing Endor exception policy decision comment."""

    errors: list[str] = []
    marker = EXCEPTION_POLICY_MARKER_RE.search(body)
    if marker is None:
        errors.append("missing ai-sast exception policy marker")
    else:
        try:
            marker_payload = json.loads(marker.group("payload"))
        except json.JSONDecodeError:
            errors.append("ai-sast exception policy marker is not valid JSON")
        else:
            for field in (
                "finding_uuid",
                "match_fingerprint",
                "match_strategy",
                "namespace",
                "project_uuid",
                "policy_name",
                "policy_uuid",
                "request_type",
            ):
                if not _text(_dict(marker_payload).get(field)):
                    errors.append(f"ai-sast exception policy marker.{field}: required")

    for heading in ("Endor Exception Policy Created", "Endor Exception Policy Reused"):
        if heading in body:
            break
    else:
        errors.append("missing Endor exception policy decision heading")

    for label in (
        "- Policy:",
        "- Policy UUID:",
        "- Finding:",
        "- Stable match:",
        "- Endor project:",
        "- Reason:",
        "- Expires:",
        "- Approved by:",
        "- Approval evidence:",
    ):
        if label not in body:
            errors.append(f"missing policy decision field {label!r}")

    if "$uuid=" in body:
        errors.append("policy decision comment must not expose raw '$uuid=' project selector")
    if re.search(r"(?im)^\s*-?\s*(?:project\s+)?scope:\s*", body):
        errors.append("policy decision comment must use 'Endor project', not raw scope")
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
    seen_patch_digests: set[str] = set()
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict):
            errors.append(f"patches[{index}]: must be an object")
            continue
        prefix = f"patches[{index}]"
        for field in ("finding_uuid", "source_sha", "patch_diff", "validation_plan"):
            if _is_empty(patch.get(field)):
                errors.append(f"{prefix}.{field}: required")
        patch_diff = _text(patch.get("patch_diff"))
        if patch_diff:
            errors.extend(f"{prefix}.patch_diff: {error}" for error in _lint_unified_diff(patch_diff))
        confidence = _first_present(patch, "patch_confidence", "confidence")
        if confidence is not None and (
            isinstance(confidence, bool)
            or not isinstance(confidence, int)
            or not 0 <= confidence <= 100
        ):
            errors.append(f"{prefix}.patch_confidence: must be an integer from 0 to 100")
        if _is_empty(patch.get("remediation_guidance_used")) and _is_empty(
            patch.get("remediation_guidance_rejected")
        ):
            errors.append(
                f"{prefix}.remediation_guidance_used: required unless remediation_guidance_rejected is present"
            )
        branch = _text(_first_present(patch, "branch_name", "branch", "proposed_branch"))
        if branch:
            _validate_branch(branch, f"{prefix}.branch_name", errors)
        if "change_impact" in patch:
            _validate_patch_change_impact(
                patch,
                prefix=prefix,
                seen_patch_digests=seen_patch_digests,
                errors=errors,
            )


def _validate_patch_change_impact(
    patch: dict[str, Any],
    *,
    prefix: str,
    seen_patch_digests: set[str],
    errors: list[str],
) -> None:
    patch_diff = _text(patch.get("patch_diff"))
    source_sha = _text(patch.get("source_sha"))
    finding_uuid = _text(patch.get("finding_uuid"))
    classification = classify_ai_sast_change_impact(patch_diff)
    impact = patch.get("change_impact")
    if not isinstance(impact, dict):
        errors.append(f"{prefix}.change_impact: required non-null object for strict patch gates")
        return

    status = _text(impact.get("status"))
    if status not in CHANGE_IMPACT_STATUSES:
        errors.append(
            f"{prefix}.change_impact.status: must be one of {', '.join(sorted(CHANGE_IMPACT_STATUSES))}"
        )
    expected_digest = ""
    try:
        expected_digest = ai_sast_patch_digest(
            patch_diff,
            source_sha=source_sha,
            finding_uuid=finding_uuid,
        )
    except ValueError:
        if status not in {"blocked", "unavailable"}:
            errors.append(f"{prefix}.change_impact.status: invalid UTF-8 patch must be unavailable or blocked")
    actual_digest = _text(impact.get("patch_digest"))
    if expected_digest and actual_digest != expected_digest:
        errors.append(f"{prefix}.change_impact.patch_digest: does not match canonical patch digest")
    if actual_digest:
        if actual_digest in seen_patch_digests:
            errors.append(f"{prefix}.change_impact.patch_digest: duplicate patch digest")
        seen_patch_digests.add(actual_digest)

    if classification.status == "unknown":
        if status not in {"blocked", "unavailable"}:
            errors.append(
                f"{prefix}.change_impact.status: unsupported or unparseable diff must be blocked or unavailable"
            )
    elif classification.trigger_classes:
        if status != "verified":
            errors.append(
                f"{prefix}.change_impact.status: compatibility-triggering diff requires verified status"
            )
        required_evidence = {"validation_evidence"}
        trigger_requirements = {
            "A": {"searched_call_sites", "tests"},
            "B": {"framework_providers", "config_keys"},
            "C": {"searched_call_sites", "tests"},
            "D": {"factories", "searched_call_sites"},
        }
        for trigger in classification.trigger_classes:
            required_evidence.update(trigger_requirements[trigger])
        for field_name in sorted(required_evidence):
            if not _string_list(impact.get(field_name)):
                errors.append(
                    f"{prefix}.change_impact.{field_name}: required for trigger classes "
                    f"{', '.join(classification.trigger_classes)}"
                )
    elif status != "not_applicable":
        errors.append(
            f"{prefix}.change_impact.status: non-triggering supported diff must be not_applicable"
        )

    if status in {"blocked", "unavailable"}:
        errors.append(f"{prefix}.change_impact.status: {status} fails closed for remediation and PR gates")


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
        title = _text(request.get("title"))
        if title and SEVERITY_TITLE_RE.match(title) is None:
            errors.append(
                f"{prefix}.title: must start with severity indicator "
                "🔴 Critical, 🟠 High, 🟡 Medium, or 🟢 Low"
            )
        branch = _text(_first_present(request, "branch_name", "branch", "proposed_branch"))
        if not branch:
            errors.append(f"{prefix}.branch_name: required")
        else:
            _validate_branch(branch, f"{prefix}.branch_name", errors)
        _validate_change_request_lookup(
            payload,
            request,
            branch,
            f"{prefix}.existing_change_request_check",
            errors,
        )
        body = _text(request.get("body"))
        if body:
            errors.extend(f"{prefix}.body: {error}" for error in lint_ai_sast_pr_body(body))
            expected_files = _expected_change_request_files(payload, request)
            for file_path in expected_files:
                if file_path not in body:
                    errors.append(
                        f"{prefix}.body: missing modified file {file_path!r}"
                    )
        approval = request.get("user_approval") or request.get("approval_status")
        status = _text(request.get("status")).lower()
        if status in {"opened", "created", "pushed"} and _text(approval).lower() not in {
            "approved",
            "confirmed",
            "true",
        }:
            errors.append(f"{prefix}.user_approval: required before push or PR/MR creation")


def _validate_change_request_lookup(
    payload: dict[str, Any],
    request: dict[str, Any],
    branch: str,
    prefix: str,
    errors: list[str],
) -> None:
    check = _dict(
        request.get("existing_change_request_check")
        or request.get("change_request_lookup")
        or request.get("idempotency_check")
    )
    if not check:
        errors.append(f"{prefix}: required before claiming no existing PR/MR or branch")
        return

    status = _text(check.get("status"))
    if not status:
        errors.append(f"{prefix}.status: required")
    elif status not in CHANGE_REQUEST_LOOKUP_STATUSES:
        errors.append(
            f"{prefix}.status: must be one of "
            f"{', '.join(sorted(CHANGE_REQUEST_LOOKUP_STATUSES))}"
        )

    lookup_method = _text(check.get("lookup_method"))
    if not lookup_method:
        errors.append(f"{prefix}.lookup_method: required")
    elif lookup_method.lower() in {"not checked", "not_checked", "none", "n/a"}:
        errors.append(f"{prefix}.lookup_method: cannot be {lookup_method!r}")

    finding_uuid = _text(check.get("finding_uuid"))
    expected_finding_uuid = _text(
        request.get("finding_uuid")
        or _selected_verdict(payload).get("finding_uuid")
        or _selected_patch(payload).get("finding_uuid")
    )
    if not finding_uuid:
        errors.append(f"{prefix}.finding_uuid: required")
    elif expected_finding_uuid and finding_uuid != expected_finding_uuid:
        errors.append(f"{prefix}.finding_uuid: must match change request finding")

    repo = _text(check.get("repo") or check.get("repo_full_name"))
    expected_repo = _text(_dict(payload.get("project_resolution")).get("repo_full_name"))
    if not repo:
        errors.append(f"{prefix}.repo: required")
    elif expected_repo and repo != expected_repo:
        errors.append(f"{prefix}.repo: must match resolved repository")

    checked_branch = _text(
        check.get("branch")
        or check.get("branch_name")
        or check.get("proposed_branch")
    )
    if not checked_branch:
        errors.append(f"{prefix}.branch: required")
    elif branch and checked_branch != branch:
        errors.append(f"{prefix}.branch: must match proposed change request branch")

    if status in {"existing_found", "branch_found"}:
        candidates = _list(check.get("candidates") or check.get("matches"))
        existing_url = _text(
            check.get("existing_url")
            or check.get("existing_pr_url")
            or check.get("existing_mr_url")
            or check.get("url")
        )
        existing_branch = _text(
            check.get("existing_branch")
            or check.get("existing_head_ref")
            or check.get("head_ref")
        )
        if not (existing_url or existing_branch or candidates):
            errors.append(
                f"{prefix}: existing-found statuses require existing_url, "
                "existing_branch, or candidates"
            )

    if status == "none_found" and _lookup_gap_mentions_change_request(payload):
        errors.append(f"{prefix}.status: cannot be none_found when data_gaps report lookup failure")
    if status == "lookup_unavailable" and not _lookup_gap_mentions_change_request(payload):
        errors.append(f"{prefix}.status: lookup_unavailable requires a matching data_gaps entry")


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
        if request_type == "accepted_risk" and not _text(
            approval.get("expiration_time") or approval.get("until")
        ):
            errors.append(f"{prefix}.expiration_time: required for accepted risk approval")
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
    project = _dict(payload.get("project_resolution"))
    project_uuid = _text(payload.get("project_uuid") or project.get("project_uuid"))
    approvals_by_request_type: dict[str, list[dict[str, Any]]] = {}
    for approval in _list(payload.get("approvals")):
        if not isinstance(approval, dict):
            continue
        request_type = _text(approval.get("request_type"))
        if request_type:
            approvals_by_request_type.setdefault(request_type, []).append(approval)
    approved_finding_uuids = {
        _text(approval.get("finding_uuid"))
        for approval in _list(payload.get("approvals"))
        if isinstance(approval, dict) and _text(approval.get("finding_uuid"))
    }
    for index, policy in enumerate(policies):
        if not isinstance(policy, dict):
            errors.append(f"exception_policies[{index}]: must be an object")
            continue
        prefix = f"exception_policies[{index}]"
        status = _text(policy.get("status")).lower()
        policy_name = _policy_name(policy)
        policy_uuid = _text(policy.get("policy_uuid") or policy.get("uuid"))
        if not policy_name:
            errors.append(f"{prefix}.policy_name: required for human-readable policy evidence")
        if status in {"created", "written"}:
            if not policy_uuid:
                errors.append(f"{prefix}.policy_uuid: required when policy is created")
            if _text(policy.get("user_confirmation")).lower() not in {
                "approved",
                "confirmed",
                "true",
            }:
                errors.append(f"{prefix}.user_confirmation: required before Endor policy write")
        elif status in {"existing", "reused", "existing_reused"}:
            if not policy_uuid:
                errors.append(f"{prefix}.policy_uuid: required when reusing an existing policy")
        elif _text(policy.get("user_confirmation")).lower() not in {
            "approved",
            "confirmed",
            "true",
        }:
            errors.append(f"{prefix}.user_confirmation: required before Endor policy write")
        if "rendered_policy" in policy and not policy.get("policy_spec"):
            errors.append(f"{prefix}.policy_spec: required; do not use rendered_policy alias")
        exception_match = _validate_exception_match(
            policy,
            prefix,
            errors,
            project_uuid=project_uuid,
            approved_finding_uuids=approved_finding_uuids,
        )
        _validate_policy_idempotency(
            policy,
            prefix,
            errors,
            project_uuid=project_uuid,
            approved_finding_uuids=approved_finding_uuids,
            exception_match=exception_match,
        )
        spec = _policy_spec_payload(policy.get("policy_spec") or policy.get("spec"))
        _validate_policy_name(policy, prefix, errors)
        decision_comment = _text(
            policy.get("decision_comment")
            or policy.get("post_decision_comment")
            or policy.get("comment_body")
        )
        if status in {"created", "written", "existing", "reused", "existing_reused"}:
            if not decision_comment:
                errors.append(f"{prefix}.decision_comment: required after policy decision")
            else:
                errors.extend(
                    f"{prefix}.decision_comment: {error}"
                    for error in lint_ai_sast_exception_policy_comment(decision_comment)
                )
                if policy_name and f"`{policy_name}`" not in decision_comment:
                    errors.append(f"{prefix}.decision_comment: must include policy_name")
                if policy_uuid and f"`{policy_uuid}`" not in decision_comment:
                    errors.append(f"{prefix}.decision_comment: must include policy_uuid")
        _validate_policy_spec(
            spec,
            prefix,
            errors,
            project_uuid=project_uuid,
            approvals_by_request_type=approvals_by_request_type,
            exception_match=exception_match,
        )


def _validate_exception_match(
    policy: dict[str, Any],
    prefix: str,
    errors: list[str],
    *,
    project_uuid: str,
    approved_finding_uuids: set[str],
) -> dict[str, Any]:
    match = _exception_match(policy)
    if not match:
        errors.append(
            f"{prefix}.exception_match: required for stable exception policy matching"
        )
        return {}

    strategy = _text(match.get("strategy"))
    if not strategy:
        errors.append(f"{prefix}.exception_match.strategy: required")
    elif strategy not in EXCEPTION_MATCH_STRATEGIES:
        errors.append(
            f"{prefix}.exception_match.strategy: must be one of "
            f"{', '.join(sorted(EXCEPTION_MATCH_STRATEGIES))}"
        )

    fingerprint = _text(match.get("match_fingerprint") or match.get("fingerprint"))
    if not fingerprint:
        errors.append(f"{prefix}.exception_match.match_fingerprint: required")

    match_project_uuid = _text(match.get("project_uuid"))
    if not match_project_uuid:
        errors.append(f"{prefix}.exception_match.project_uuid: required")
    elif project_uuid and match_project_uuid != project_uuid:
        errors.append(f"{prefix}.exception_match.project_uuid: must match resolved project UUID")

    match_finding_uuid = _text(
        match.get("finding_uuid") or match.get("current_finding_uuid")
    )
    if not match_finding_uuid:
        errors.append(f"{prefix}.exception_match.current_finding_uuid: required")
    elif approved_finding_uuids and match_finding_uuid not in approved_finding_uuids:
        errors.append(
            f"{prefix}.exception_match.current_finding_uuid: must match approved finding"
        )

    if strategy == "ai_sast_fingerprint":
        _validate_ai_sast_exception_match_fields(match, prefix, errors)
    elif strategy == "vulnerability_alias":
        _validate_vulnerability_alias_match_fields(match, prefix, errors)

    return match


def _validate_ai_sast_exception_match_fields(
    match: dict[str, Any],
    prefix: str,
    errors: list[str],
) -> None:
    if not _text(match.get("context_type")):
        errors.append(f"{prefix}.exception_match.context_type: required")
    elif _text(match.get("context_type")) != "CONTEXT_TYPE_MAIN":
        errors.append(f"{prefix}.exception_match.context_type: must be CONTEXT_TYPE_MAIN")

    if not _text(match.get("source_ref")):
        errors.append(f"{prefix}.exception_match.source_ref: required")

    cwes = _string_list(match.get("cwes") or match.get("cwe") or match.get("cwe_ids"))
    if not cwes:
        errors.append(f"{prefix}.exception_match.cwes: required")

    if not _text(match.get("sast_rule_id")):
        errors.append(f"{prefix}.exception_match.sast_rule_id: required")

    location = _dict(
        match.get("location")
        or match.get("sink")
        or match.get("sink_location")
        or match.get("ai_sast_location")
    )
    if not location:
        errors.append(f"{prefix}.exception_match.location: required")
        return

    if not _text(location.get("relative_path") or location.get("file_path")):
        errors.append(f"{prefix}.exception_match.location.relative_path: required")
    if not _text(location.get("type")):
        errors.append(f"{prefix}.exception_match.location.type: required")
    if not _text(location.get("function_name")):
        errors.append(f"{prefix}.exception_match.location.function_name: required")
    if _coerce_int(location.get("start_line")) is None:
        errors.append(f"{prefix}.exception_match.location.start_line: required")
    if _coerce_int(location.get("line_window")) is None:
        errors.append(f"{prefix}.exception_match.location.line_window: required")


def _validate_vulnerability_alias_match_fields(
    match: dict[str, Any],
    prefix: str,
    errors: list[str],
) -> None:
    ids = _string_list(
        match.get("vulnerability_ids")
        or match.get("vulnerability_id")
        or match.get("aliases")
        or match.get("alias")
    )
    if not ids:
        errors.append(f"{prefix}.exception_match.vulnerability_ids: required")


def _validate_policy_idempotency(
    policy: dict[str, Any],
    prefix: str,
    errors: list[str],
    *,
    project_uuid: str,
    approved_finding_uuids: set[str],
    exception_match: dict[str, Any],
) -> None:
    check = _dict(policy.get("idempotency_check") or policy.get("existing_policy_lookup"))
    if not check:
        errors.append(f"{prefix}.idempotency_check: required before Endor policy write")
        return

    status = _text(check.get("status")).lower()
    if not status:
        errors.append(f"{prefix}.idempotency_check.status: required")
    elif status not in EXCEPTION_POLICY_IDEMPOTENCY_STATUSES:
        errors.append(
            f"{prefix}.idempotency_check.status: must be one of "
            f"{', '.join(sorted(EXCEPTION_POLICY_IDEMPOTENCY_STATUSES))}"
        )

    lookup_method = _text(check.get("lookup_method") or check.get("method"))
    if not lookup_method:
        errors.append(f"{prefix}.idempotency_check.lookup_method: required")
    elif "not checked" in lookup_method.lower():
        errors.append(f"{prefix}.idempotency_check.lookup_method: cannot be 'not checked'")

    match_strategy = _text(exception_match.get("strategy"))
    check_strategy = _text(check.get("match_strategy") or check.get("strategy"))
    if not check_strategy:
        errors.append(f"{prefix}.idempotency_check.match_strategy: required")
    elif match_strategy and check_strategy != match_strategy:
        errors.append(f"{prefix}.idempotency_check.match_strategy: must match exception_match.strategy")

    match_fingerprint = _text(
        exception_match.get("match_fingerprint") or exception_match.get("fingerprint")
    )
    check_fingerprint = _text(check.get("match_fingerprint") or check.get("fingerprint"))
    if not check_fingerprint:
        errors.append(f"{prefix}.idempotency_check.match_fingerprint: required")
    elif match_fingerprint and check_fingerprint != match_fingerprint:
        errors.append(
            f"{prefix}.idempotency_check.match_fingerprint: must match exception_match.match_fingerprint"
        )

    check_finding_uuid = _text(check.get("finding_uuid"))
    if check_finding_uuid and approved_finding_uuids and check_finding_uuid not in approved_finding_uuids:
        errors.append(f"{prefix}.idempotency_check.finding_uuid: must match approved finding")

    check_project_uuid = _text(check.get("project_uuid"))
    if not check_project_uuid:
        errors.append(f"{prefix}.idempotency_check.project_uuid: required")
    elif project_uuid and check_project_uuid != project_uuid:
        errors.append(f"{prefix}.idempotency_check.project_uuid: must match resolved project UUID")

    policy_status = _text(policy.get("status")).lower()
    if policy_status in {"created", "written"} and status != "none_found":
        errors.append(
            f"{prefix}.idempotency_check.status: must be none_found before creating a new policy"
        )
    if policy_status in {"existing", "reused", "existing_reused"} and status != "existing_reused":
        errors.append(
            f"{prefix}.idempotency_check.status: must be existing_reused when reusing a policy"
        )
    if status == "existing_reused":
        existing_uuid = _text(check.get("existing_policy_uuid") or check.get("policy_uuid"))
        existing_name = _text(check.get("existing_policy_name") or check.get("policy_name"))
        if not existing_uuid:
            errors.append(f"{prefix}.idempotency_check.existing_policy_uuid: required")
        if not existing_name:
            errors.append(f"{prefix}.idempotency_check.existing_policy_name: required")
        policy_uuid = _text(policy.get("policy_uuid") or policy.get("uuid"))
        if existing_uuid and policy_uuid and existing_uuid != policy_uuid:
            errors.append(f"{prefix}.idempotency_check.existing_policy_uuid: must match policy_uuid")
    if status in {"blocked_duplicate", "expired_existing_needs_review"}:
        errors.append(
            f"{prefix}.idempotency_check.status: {status} must stop before policy creation"
        )


def _validate_policy_name(policy: dict[str, Any], prefix: str, errors: list[str]) -> None:
    policy_name = _text(policy.get("policy_name"))
    resource = _dict(policy.get("policy_spec") or policy.get("spec"))
    meta_name = _text(_dict(resource.get("meta")).get("name"))
    if meta_name and policy_name and meta_name != policy_name:
        errors.append(f"{prefix}.policy_name: must match policy_spec.meta.name")


def _validate_policy_spec(
    spec: dict[str, Any],
    prefix: str,
    errors: list[str],
    *,
    project_uuid: str = "",
    approvals_by_request_type: dict[str, list[dict[str, Any]]] | None = None,
    exception_match: dict[str, Any] | None = None,
) -> None:
    if not spec:
        errors.append(f"{prefix}.policy_spec: required")
        return
    policy_type = _text(spec.get("policy_type"))
    if not policy_type:
        errors.append(f"{prefix}.policy_spec.policy_type: required")
    elif policy_type != "POLICY_TYPE_EXCEPTION":
        errors.append(f"{prefix}.policy_spec.policy_type: must be POLICY_TYPE_EXCEPTION")
    exception = _dict(spec.get("exception"))
    reason = _text(exception.get("reason"))
    if not reason:
        errors.append(f"{prefix}.policy_spec.exception.reason: required")
    elif reason not in EXCEPTION_REASONS:
        errors.append(f"{prefix}.policy_spec.exception.reason: unsupported reason {reason!r}")
    request_type = _request_type_for_exception_reason(reason)
    expiration_time = _text(exception.get("expiration_time"))
    if reason == "EXCEPTION_REASON_RISK_ACCEPTED":
        if not expiration_time:
            errors.append(f"{prefix}.policy_spec.exception.expiration_time: required for accepted risk")
        elif RFC3339_UTC_RE.match(expiration_time) is None:
            errors.append(f"{prefix}.policy_spec.exception.expiration_time: must be RFC3339 UTC")
    if spec.get("resource_kinds") != ["Finding"]:
        errors.append(f"{prefix}.policy_spec.resource_kinds: must be ['Finding']")
    statements = _list(spec.get("query_statements"))
    if "data.endor_agent_kit_ai_sast_exception.match_finding" not in statements:
        errors.append(f"{prefix}.policy_spec.query_statements: missing AI SAST exception query")
    if "rego" in spec:
        errors.append(f"{prefix}.policy_spec.rego: do not use rego field; use rule")
    rule = _text(spec.get("rule"))
    if not rule:
        errors.append(f"{prefix}.policy_spec.rule: required")
    project_selector = spec.get("project_selector")
    if not isinstance(project_selector, list) or not all(
        isinstance(item, str) and item.startswith("$uuid=") for item in project_selector
    ):
        errors.append(f"{prefix}.policy_spec.project_selector: must be list of '$uuid=PROJECT_UUID'")
    elif project_uuid and f"$uuid={project_uuid}" not in project_selector:
        errors.append(f"{prefix}.policy_spec.project_selector: must include '$uuid={project_uuid}'")
    if project_uuid and rule:
        if project_uuid not in rule:
            errors.append(f"{prefix}.policy_spec.rule: must match the approved project UUID")
        if "data.resources.Finding[i].spec.project_uuid" not in rule:
            errors.append(
                f"{prefix}.policy_spec.rule: must scope findings with spec.project_uuid, not meta.parent_uuid"
            )
        if "data.resources.Finding[i].meta.parent_uuid" in rule:
            errors.append(f"{prefix}.policy_spec.rule: must not use meta.parent_uuid for project scope")
    if rule:
        _validate_policy_rule_uses_exception_match(
            rule,
            prefix,
            errors,
            exception_match=exception_match or {},
        )

    approvals_by_request_type = approvals_by_request_type or {}
    if request_type:
        approvals = approvals_by_request_type.get(request_type, [])
        if not approvals:
            errors.append(
                f"{prefix}.policy_spec.exception.reason: no verified approval for {request_type}"
            )
        elif rule:
            approved_finding_uuids = [
                _text(approval.get("finding_uuid"))
                for approval in approvals
                if _text(approval.get("finding_uuid"))
            ]
            if approved_finding_uuids and any(
                finding_uuid in rule for finding_uuid in approved_finding_uuids
            ):
                errors.append(
                    f"{prefix}.policy_spec.rule: must not match volatile Finding UUID; use exception_match stable fields"
                )


def _validate_policy_rule_uses_exception_match(
    rule: str,
    prefix: str,
    errors: list[str],
    *,
    exception_match: dict[str, Any],
) -> None:
    strategy = _text(exception_match.get("strategy"))
    if strategy == "ai_sast_fingerprint":
        _validate_ai_sast_fingerprint_rule(rule, prefix, errors, exception_match)
    elif strategy == "vulnerability_alias":
        _validate_vulnerability_alias_rule(rule, prefix, errors, exception_match)


def _validate_ai_sast_fingerprint_rule(
    rule: str,
    prefix: str,
    errors: list[str],
    exception_match: dict[str, Any],
) -> None:
    required_tokens = {
        'data.resources.Finding[i].context["type"]': "must scope main-context findings with context[\"type\"]",
        "CONTEXT_TYPE_MAIN": "must match main-context findings",
        "data.resources.Finding[i].spec.method": "must match AI SAST method",
        "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST": "must use the full AI SAST method enum",
        "data.resources.Finding[i].spec.source_code_version.ref": "must match source ref",
        "data.resources.Finding[i].spec.finding_metadata.custom.sast_rule_id": "must match SAST rule id",
        "data.resources.Finding[i].spec.finding_metadata.ai_sast_data.location": "must match AI SAST sink/source location",
    }
    for token, message in required_tokens.items():
        if token not in rule:
            errors.append(f"{prefix}.policy_spec.rule: {message}")

    source_ref = _text(exception_match.get("source_ref"))
    if source_ref and source_ref not in rule:
        errors.append(f"{prefix}.policy_spec.rule: must include exception_match.source_ref")

    cwes = _string_list(
        exception_match.get("cwes")
        or exception_match.get("cwe")
        or exception_match.get("cwe_ids")
    )
    if cwes:
        if not (
            "data.resources.Finding[i].spec.finding_metadata.custom.cwes" in rule
            or "data.resources.Finding[i].spec.finding_metadata.ai_sast_data.cwes" in rule
        ):
            errors.append(f"{prefix}.policy_spec.rule: must match AI SAST CWE metadata")
        if not any(cwe in rule for cwe in cwes):
            errors.append(f"{prefix}.policy_spec.rule: must include an exception_match CWE")

    sast_rule_id = _text(exception_match.get("sast_rule_id"))
    if sast_rule_id and sast_rule_id not in rule:
        errors.append(f"{prefix}.policy_spec.rule: must include exception_match.sast_rule_id")

    location = _dict(
        exception_match.get("location")
        or exception_match.get("sink")
        or exception_match.get("sink_location")
        or exception_match.get("ai_sast_location")
    )
    relative_path = _text(location.get("relative_path") or location.get("file_path"))
    location_type = _text(location.get("type"))
    function_name = _text(location.get("function_name"))
    for value, field in (
        (relative_path, "location.relative_path"),
        (location_type, "location.type"),
        (function_name, "location.function_name"),
    ):
        if value and value not in rule:
            errors.append(f"{prefix}.policy_spec.rule: must include exception_match.{field}")
    if "location.start_line >=" not in rule or "location.start_line <=" not in rule:
        errors.append(f"{prefix}.policy_spec.rule: must use a location.start_line window")


def _validate_vulnerability_alias_rule(
    rule: str,
    prefix: str,
    errors: list[str],
    exception_match: dict[str, Any],
) -> None:
    if not (
        "data.resources.Finding[i].spec.finding_metadata.vulnerability.spec.aliases" in rule
        or "data.resources.Finding[i].spec.finding_metadata.vulnerability.meta.name" in rule
    ):
        errors.append(f"{prefix}.policy_spec.rule: must match vulnerability alias metadata")
    ids = _string_list(
        exception_match.get("vulnerability_ids")
        or exception_match.get("vulnerability_id")
        or exception_match.get("aliases")
        or exception_match.get("alias")
    )
    if ids and not any(identifier in rule for identifier in ids):
        errors.append(f"{prefix}.policy_spec.rule: must include an exception_match vulnerability ID")


def _policy_spec_payload(value: Any) -> dict[str, Any]:
    spec = _dict(value)
    if "policy_type" in spec:
        return spec
    nested = _dict(spec.get("spec"))
    return nested if nested else spec


def _policy_name(policy: dict[str, Any]) -> str:
    explicit = _text(policy.get("policy_name") or policy.get("name"))
    if explicit:
        return explicit
    resource = _dict(policy.get("policy_spec") or policy.get("spec"))
    return _text(_dict(resource.get("meta")).get("name"))


def _exception_match(policy: dict[str, Any]) -> dict[str, Any]:
    return _dict(
        policy.get("exception_match")
        or policy.get("stable_finding_key")
        or policy.get("finding_stable_identity")
    )


def _request_type_for_exception_reason(reason: str) -> str:
    return {
        "EXCEPTION_REASON_FALSE_POSITIVE": "false_positive",
        "EXCEPTION_REASON_RISK_ACCEPTED": "accepted_risk",
    }.get(reason, "")


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


def _selected_change_request(payload: dict[str, Any]) -> dict[str, Any]:
    change_requests = _list(payload.get("change_requests"))
    for request in change_requests:
        if isinstance(request, dict):
            return request
    return {}


def _selected_exception_policy(payload: dict[str, Any]) -> dict[str, Any]:
    policies = _list(payload.get("exception_policies"))
    for policy in policies:
        if isinstance(policy, dict):
            return policy
    return {}


def _selected_policy_approval(
    payload: dict[str, Any],
    policy_spec: dict[str, Any],
) -> dict[str, Any]:
    reason = _text(_dict(policy_spec.get("exception")).get("reason"))
    request_type = _request_type_for_exception_reason(reason)
    approvals = _list(payload.get("approvals"))
    for approval in approvals:
        if not isinstance(approval, dict):
            continue
        if request_type and _text(approval.get("request_type")) != request_type:
            continue
        return approval
    for approval in approvals:
        if isinstance(approval, dict):
            return approval
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


def _display_exception_reason(reason: str) -> str:
    return {
        "EXCEPTION_REASON_FALSE_POSITIVE": "`False positive`",
        "EXCEPTION_REASON_RISK_ACCEPTED": "`Accepted risk`",
    }.get(reason, f"`{reason or 'not provided'}`")


HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def _lint_unified_diff(diff: str) -> list[str]:
    """Validate unified-diff structure without needing a target checkout."""

    lines = diff.splitlines()
    if not lines:
        return ["must not be empty"]

    errors: list[str] = []
    saw_hunk = False
    index = 0
    while index < len(lines):
        while index < len(lines) and _is_diff_metadata_line(lines[index]):
            index += 1
        if index >= len(lines):
            break
        line = lines[index]
        if not line.startswith("--- "):
            errors.append(f"line {index + 1}: expected file header '--- '")
            break
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            errors.append(f"line {index + 1}: missing matching '+++' file header")
            break
        index += 2
        file_hunks = 0

        while index < len(lines):
            if _is_diff_metadata_line(lines[index]):
                break
            if lines[index].startswith("--- ") and (
                index + 1 < len(lines) and lines[index + 1].startswith("+++ ")
            ):
                break
            hunk_match = HUNK_RE.match(lines[index])
            if hunk_match is None:
                errors.append(f"line {index + 1}: expected hunk header '@@ ... @@'")
                return errors

            saw_hunk = True
            file_hunks += 1
            hunk_line = index + 1
            old_expected = int(hunk_match.group(1) or "1")
            new_expected = int(hunk_match.group(2) or "1")
            old_actual = 0
            new_actual = 0
            index += 1

            while index < len(lines):
                current = lines[index]
                if HUNK_RE.match(current):
                    break
                if _is_diff_metadata_line(current):
                    break
                if current.startswith("--- ") and (
                    index + 1 < len(lines) and lines[index + 1].startswith("+++ ")
                ):
                    break
                if current.startswith("\\"):
                    index += 1
                    continue
                if not current:
                    old_actual += 1
                    new_actual += 1
                elif current[0] == " ":
                    old_actual += 1
                    new_actual += 1
                elif current[0] == "-":
                    old_actual += 1
                elif current[0] == "+":
                    new_actual += 1
                else:
                    errors.append(f"line {index + 1}: invalid hunk line prefix")
                    return errors
                index += 1

            if old_actual > old_expected or new_actual > new_expected:
                errors.append(
                    f"hunk starting line {hunk_line}: header counts "
                    f"old={old_expected}, new={new_expected} but body exceeds them with "
                    f"old={old_actual}, new={new_actual}"
                )

        if file_hunks == 0:
            errors.append(f"line {index + 1}: file diff has no hunks")

    if not saw_hunk:
        errors.append("must include at least one hunk")
    return errors


def _is_diff_metadata_line(line: str) -> bool:
    return line.startswith(
        (
            "diff --git ",
            "index ",
            "new file mode ",
            "deleted file mode ",
            "old mode ",
            "new mode ",
            "similarity index ",
            "dissimilarity index ",
            "rename from ",
            "rename to ",
            "copy from ",
            "copy to ",
        )
    )


def _expected_change_request_files(
    payload: dict[str, Any],
    request: dict[str, Any],
) -> list[str]:
    finding_uuid = _text(request.get("finding_uuid"))
    files = _string_list(
        request.get("changed_files") or request.get("modified_files") or request.get("files")
    )
    for patch in _list(payload.get("patches")):
        if not isinstance(patch, dict):
            continue
        patch_finding = _text(patch.get("finding_uuid"))
        if finding_uuid and patch_finding and patch_finding != finding_uuid:
            continue
        files.extend(
            _string_list(
                patch.get("changed_files")
                or patch.get("modified_files")
                or patch.get("files")
                or patch.get("file_path")
            )
        )
    return _unique_strings(files)


def _lookup_gap_mentions_change_request(payload: dict[str, Any]) -> bool:
    for gap in _string_list(payload.get("data_gaps")):
        mentions_change_request = re.search(
            r"(?i)\b(PR|MR|pull request|merge request|branch|change request)\b",
            gap,
        )
        mentions_lookup_failure = re.search(
            r"(?i)\blookup|search|discover|unavailable|credential|permission|auth|failed|cannot\b",
            gap,
        )
        if mentions_change_request and mentions_lookup_failure:
            return True
    return False


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


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


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

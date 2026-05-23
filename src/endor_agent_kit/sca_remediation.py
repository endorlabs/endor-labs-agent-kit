"""Mechanical contracts for SCA remediation agent outputs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RISK_DECISION_STATUSES = frozenset(
    {
        "approved_low_risk",
        "approved_with_validation_required",
        "blocked_needs_compatibility_analysis",
        "rejected",
    }
)

SEVERITY_SUFFIXES = {
    "critical": "(C) 🔴",
    "high": "(H) 🟠",
    "medium": "(M) 🟡",
    "moderate": "(M) 🟡",
    "low": "(L) 🟢",
}

BRANCH_RE = re.compile(r"^remediation/sca/[A-Za-z0-9._-]+-[A-Za-z0-9][A-Za-z0-9._-]*$")
ADVISORY_LINE_RE = re.compile(r"^- \[([^\]]+)\]\(([^)]+)\): .+ \(([CHML])\) [🔴🟠🟡🟢]$")


def load_json_payload(path: str | Path) -> dict[str, Any]:
    """Load a JSON object used by SCA contract commands."""

    payload_path = Path(path)
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def validate_sca_gate_payload(payload: dict[str, Any], *, gate: str = "selection-plan") -> list[str]:
    """Validate structured output for an SCA remediation workflow gate."""

    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload: must be an object"]

    risk_decision = payload.get("risk_decision")
    risk_status = ""
    if not isinstance(risk_decision, dict):
        errors.append("risk_decision: required object")
        risk_decision = {}
    else:
        risk_status = _text(risk_decision.get("status"))
        if risk_status not in RISK_DECISION_STATUSES:
            errors.append(
                "risk_decision.status: must be one of "
                + ", ".join(sorted(RISK_DECISION_STATUSES))
            )

    selected = _dict(payload.get("selected_remediation"))
    project_resolution = _dict(payload.get("project_resolution"))
    project_uuid = _text(
        payload.get("project_uuid")
        or project_resolution.get("project_uuid")
        or selected.get("project_uuid")
    )
    namespace = _text(
        payload.get("namespace")
        or project_resolution.get("namespace")
        or selected.get("namespace")
    )
    namespace_provenance = _text(
        payload.get("namespace_provenance")
        or project_resolution.get("namespace_provenance")
        or selected.get("namespace_provenance")
    )
    if gate in {"selection-plan", "apply", "validate", "pr"}:
        if not project_uuid:
            errors.append("project_resolution.project_uuid: required for SCA workflow gates")
        if not namespace:
            errors.append("project_resolution.namespace: required for SCA workflow gates")
        if not namespace_provenance:
            errors.append("project_resolution.namespace_provenance: required for SCA workflow gates")

    cia_status = _text(
        selected.get("cia_status")
        or selected.get("cia")
        or _dict(payload.get("uia_evidence")).get("cia_status")
    ).lower()
    upgrade_risk = _text(selected.get("upgrade_risk") or selected.get("risk")).lower()
    findings_introduced = _int(selected.get("findings_introduced"))

    requires_solver = (
        "indeterminate" in cia_status
        or "unknown" in cia_status
        or upgrade_risk in {"medium", "high", "critical", "unknown"}
        or findings_introduced > 0
        or _has_conflicts(selected)
    )

    if requires_solver:
        source_evidence = _first_present(
            risk_decision,
            "source_usage_summary",
            "source_usage",
            "source_context",
            "compatibility_evidence",
        ) or payload.get("compatibility_evidence")
        if _is_empty(source_evidence):
            errors.append(
                "risk_decision.source_usage_summary: required when CIA is indeterminate, "
                "risk is elevated, conflicts exist, or findings are introduced"
            )

        validation_requirements = (
            risk_decision.get("validation_requirements")
            or payload.get("validation_requirements")
            or payload.get("validation")
        )
        if _is_empty(validation_requirements):
            errors.append("validation_requirements: required for risk solver decisions")

    branch_names = _collect_branch_names(payload)
    if gate in {"selection-plan", "apply", "validate", "pr"} and not branch_names:
        errors.append("branch_name: required and must use remediation/sca/<package>-<target-version>")
    for branch in branch_names:
        if branch.startswith("endor/fix/"):
            errors.append(f"branch_name: {branch!r} uses disallowed endor/fix prefix")
        elif not BRANCH_RE.match(branch):
            errors.append(
                f"branch_name: {branch!r} must match remediation/sca/<package>-<target-version>"
            )

    summary = _text(payload.get("summary")).lower()
    if "awaiting approval to apply" in summary and not risk_status:
        errors.append("gate: cannot await apply approval before risk_decision.status is present")

    if gate == "pr":
        body = _text(_first_present(payload, "pr_body", "body", "pull_request_body"))
        if not body:
            errors.append("pr_body: required for PR gate validation")
        else:
            errors.extend(f"pr_body: {error}" for error in lint_sca_pr_body(body))

    return errors


def render_sca_pr_body(payload: dict[str, Any]) -> str:
    """Render the AURI-style SCA remediation PR body from normalized data."""

    selected = _dict(payload.get("selected_remediation"))
    risk_decision = _dict(payload.get("risk_decision"))
    advisories = _advisories(payload)
    package = _text(selected.get("package") or selected.get("package_name") or payload.get("package"))
    from_version = _text(selected.get("from_version") or selected.get("current_version"))
    to_version = _text(selected.get("to_version") or selected.get("target_version"))
    upgrade_risk = _text(selected.get("upgrade_risk") or selected.get("risk") or "unknown")
    cia_status = _text(selected.get("cia_status") or selected.get("cia") or "unknown")
    findings_fixed = selected.get("findings_fixed", len(advisories))
    findings_introduced = selected.get("findings_introduced", 0)
    manifests = _string_list(selected.get("manifests") or selected.get("affected_manifests"))
    validation = _list(payload.get("validation"))

    expectation = _compatibility_line(risk_decision, cia_status)

    lines = [
        "<!-- endor-agent-kit:sca-remediation-agent -->",
        "",
        f"## Security Remediation: {findings_fixed} Endor finding instances fixed by dependency upgrade",
        "",
        "### At a Glance",
        "",
        "| | |",
        "|---|---|",
        f"| 📦 Package | `{package}` |",
        f"| ⬆️ Upgrade | `{from_version}` → `{to_version}` |",
        f"| 🎯 Risk | {upgrade_risk} |",
        f"| 🛡️ Findings fixed | {findings_fixed} |",
        f"| 🆕 Findings introduced | {findings_introduced} |",
        f"| 🔍 CIA | {cia_status} |",
        f"| 🗂️ Manifests | {_format_manifest_cell(manifests)} |",
        "",
        expectation,
        "",
        "### 🔎 Advisories This Upgrade Fixes",
        "",
        f"<details><summary>Advisories This Upgrade Fixes ({len(advisories)})</summary>",
        "",
    ]

    if advisories:
        lines.extend(_render_advisory(advisory) for advisory in advisories)
    else:
        lines.append("- No advisory list was provided by the agent output.")

    lines.extend(
        [
            "",
            "</details>",
            "",
            "### Validation Plan",
            "",
        ]
    )
    lines.extend(_render_validation(validation))
    lines.extend(
        [
            "",
            "### Rollback",
            "",
            "Revert the branch or restore the dependency version to its previous value in the affected manifest files.",
            "",
            "### Endor Evidence",
            "",
        ]
    )
    lines.extend(_render_evidence(payload, selected, risk_decision))
    return "\n".join(lines).rstrip() + "\n"


def lint_sca_pr_body(body: str) -> list[str]:
    """Lint an AURI-style SCA remediation PR body."""

    errors: list[str] = []
    if "<!-- endor-agent-kit:sca-remediation-agent -->" not in body:
        errors.append("missing sca-remediation-agent marker")
    for heading in (
        "### At a Glance",
        "### 🔎 Advisories This Upgrade Fixes",
        "### Validation Plan",
        "### Rollback",
        "### Endor Evidence",
    ):
        if heading not in body:
            errors.append(f"missing section {heading!r}")

    advisory_block = _details_block(body)
    if advisory_block is None:
        errors.append("missing folded advisories <details> block")
        return errors

    if re.search(r"\*\*(Critical|High|Medium|Low)\*\*", advisory_block, re.IGNORECASE):
        errors.append("advisory list must not use bold severity words")

    advisory_lines = [
        line.strip()
        for line in advisory_block.splitlines()
        if line.strip().startswith("- [")
    ]
    if not advisory_lines:
        errors.append("advisory list must include at least one linked advisory")
    for line in advisory_lines:
        match = ADVISORY_LINE_RE.match(line)
        if not match:
            errors.append(f"advisory line has invalid format: {line}")
            continue
        label, url, _severity_code = match.groups()
        if label.startswith("GHSA-") and "CVE-" in line:
            errors.append("advisory line uses GHSA visible text even though a CVE appears on the line")
        if label.startswith("CVE-") and "github.com/advisories/GHSA-" in url:
            continue
        if label.startswith("GHSA-") and "github.com/advisories/GHSA-" in url:
            continue
        if label.startswith("CVE-") and "nvd.nist.gov/vuln/detail/CVE-" in url:
            continue
        errors.append(f"advisory link target is not recognized for {label}")
    return errors


def normalize_sca_branch(package: str, target_version: str) -> str:
    """Return the stable SCA remediation branch name for a package upgrade."""

    package_name = package.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
    package_name = package_name.replace("@", "").replace(" ", "-")
    package_name = re.sub(r"[^A-Za-z0-9._-]+", "-", package_name).strip("-")
    version = re.sub(r"[^A-Za-z0-9._-]+", "-", target_version).strip("-")
    return f"remediation/sca/{package_name}-{version}"


def _compatibility_line(risk_decision: dict[str, Any], cia_status: str) -> str:
    status = _text(risk_decision.get("status"))
    cia = cia_status.lower()
    if status == "approved_low_risk" and "no breaking" in cia:
        return "✅ Not expected to break: Endor UIA/CIA reports LOW upgrade risk and no breaking changes."
    reason = _text(risk_decision.get("summary") or risk_decision.get("reason"))
    if reason:
        return f"⚠️ Compatibility requires validation: {reason}"
    return "⚠️ Compatibility requires validation: see risk decision and validation plan."


def _render_advisory(advisory: dict[str, Any]) -> str:
    cve = _text(advisory.get("cve") or advisory.get("cve_id"))
    ghsa = _text(advisory.get("ghsa") or advisory.get("ghsa_id"))
    label = cve or ghsa or _text(advisory.get("id") or "unknown-advisory")
    url = _text(advisory.get("url") or advisory.get("advisory_url") or advisory.get("ghsa_url"))
    if not url and ghsa:
        url = f"https://github.com/advisories/{ghsa}"
    elif not url and cve:
        url = f"https://nvd.nist.gov/vuln/detail/{cve}"
    title = _text(advisory.get("title") or advisory.get("summary") or "Advisory fixed by this upgrade")
    suffix = SEVERITY_SUFFIXES.get(_text(advisory.get("severity")).lower(), "(M) 🟡")
    return f"- [{label}]({url}): {title} {suffix}"


def _render_validation(validation: list[Any]) -> list[str]:
    if not validation:
        return ["- Validation commands were not provided in the structured output."]
    lines: list[str] = []
    for item in validation:
        if isinstance(item, dict):
            command = _text(item.get("command") or item.get("step") or item.get("name"))
            status = _text(item.get("status") or item.get("result") or "planned")
            detail = _text(item.get("detail") or item.get("purpose") or item.get("reason"))
            body = f"- `{command}` — {status}" if command else f"- {status}"
            if detail:
                body += f": {detail}"
            lines.append(body)
        else:
            lines.append(f"- {_text(item)}")
    return lines


def _render_evidence(
    payload: dict[str, Any],
    selected: dict[str, Any],
    risk_decision: dict[str, Any],
) -> list[str]:
    evidence = _list(payload.get("uia_evidence"))
    uia_uuid = _text(selected.get("uia_uuid") or selected.get("version_upgrade_uuid"))
    project_uuid = _text(selected.get("project_uuid") or payload.get("project_uuid"))
    namespace = _text(selected.get("namespace") or payload.get("namespace"))
    reachability = selected.get("reachability_tags") or selected.get("reachability")
    lines = [
        f"- VersionUpgrade/UIA UUID: `{uia_uuid or 'not provided'}`",
        f"- Project UUID: `{project_uuid or 'not provided'}`",
        f"- Namespace: `{namespace or 'not provided'}`",
        f"- Reachability: `{_text(reachability) or 'not provided'}`",
        f"- Risk decision: `{_text(risk_decision.get('status')) or 'not provided'}`",
    ]
    if evidence:
        lines.append(f"- UIA evidence records: {len(evidence)}")
    return lines


def _advisories(payload: dict[str, Any]) -> list[dict[str, Any]]:
    selected = _dict(payload.get("selected_remediation"))
    candidates = (
        payload.get("advisories")
        or payload.get("fixed_advisories")
        or selected.get("advisories")
        or selected.get("fixed_advisories")
    )
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def _details_block(body: str) -> str | None:
    match = re.search(r"<details[^>]*>.*?</summary>(.*?)</details>", body, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return match.group(1)


def _collect_branch_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if _is_remediation_branch_key(key_text) and isinstance(item, str) and item.strip():
                branch = item.strip()
                if branch.lower() not in {"not_created", "none", "n/a", "out_of_scope_per_user"}:
                    names.append(branch)
            names.extend(_collect_branch_names(item))
    elif isinstance(value, list):
        for item in value:
            names.extend(_collect_branch_names(item))
    return list(dict.fromkeys(names))


def _is_remediation_branch_key(key: str) -> bool:
    return key in {
        "branch",
        "branch_name",
        "head_branch",
        "proposed_branch",
        "proposed_branch_name",
        "source_branch",
    } or key.endswith("_branch_name")


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if not _is_empty(value):
            return value
    return None


def _has_conflicts(selected: dict[str, Any]) -> bool:
    for key in ("conflicts", "hard_conflicts", "minor_conflicts"):
        value = selected.get(key)
        if isinstance(value, int) and value > 0:
            return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value.strip() not in {"", "0", "none", "None"}:
            return True
    return False


def _format_manifest_cell(manifests: list[str]) -> str:
    if not manifests:
        return "not provided"
    return "<br>".join(f"`{manifest}`" for manifest in manifests)


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


def _int(value: Any) -> int:
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False

"""Lint captured agent outputs for release-blocking QA regressions."""

from __future__ import annotations

import json
import re
from typing import Any

from endor_agent_kit.sca_remediation import validate_sca_gate_payload

READ_ONLY_SCAN_BLOCK_AGENTS = frozenset(
    {
        "dependency-decision-helper",
        "package-risk-summary",
        "remediation-planner",
        "repository-dependency-reviewer",
        "upgrade-impact-analysis",
        "vulnerability-explainer",
    }
)

PROJECT_GATE_AGENTS = frozenset({"sca-remediation", "remediation-planner"})

UNSAFE_CONFIG_READ_RE = re.compile(
    r"\bcat\s+(?:~|\$HOME)/(?:\.config/endorctl/config\.yaml|\.endorctl/config\.yaml)\b",
    re.IGNORECASE,
)
CONFIG_CONTEXT_RE = re.compile(
    r"(?:~|\$HOME)/(?:\.config/endorctl/config\.yaml|\.endorctl/config\.yaml)",
    re.IGNORECASE,
)
MEMORY_PROVENANCE_RE = re.compile(
    r"(remembered|from memory|prior session|previous run|older session).{0,80}(namespace|repo|repository|project)",
    re.IGNORECASE | re.DOTALL,
)
GUESSED_REPOSITORY_RE = re.compile(
    r"(guess|guessed|assuming|assume|likely).{0,120}(github\.com|repo_full_name|repository)",
    re.IGNORECASE | re.DOTALL,
)
READ_ONLY_SCAN_RE = re.compile(
    r"\b(run|rerun|start|launch)\s+(?:a\s+|an\s+|your\s+)?(?:new\s+)?(?:endor\s+)?scan\b|`?endorctl\s+scan\b",
    re.IGNORECASE,
)


def lint_agent_output(agent_id: str, text: str) -> list[str]:
    """Return release-blocking issues found in one captured agent output."""

    errors: list[str] = []
    if UNSAFE_CONFIG_READ_RE.search(text):
        errors.append("unsafe Endor config read: do not use cat on Endor config files")
    for line in text.splitlines():
        if "grep -A" in line and CONFIG_CONTEXT_RE.search(line):
            errors.append("unsafe Endor config read: grep -A around config may leak secrets")
            break
    if _has_invalid_memory_provenance(text):
        errors.append("invalid provenance: memory or older sessions cannot prove namespace, repository, or project scope")
    if GUESSED_REPOSITORY_RE.search(text):
        errors.append("invalid provenance: repository URLs and repo_full_name values must not be guessed")
    if agent_id in READ_ONLY_SCAN_BLOCK_AGENTS and READ_ONLY_SCAN_RE.search(text):
        errors.append("read-only workflow must not recommend running a new Endor scan as the default next step")

    payload = extract_json_object(text)
    if agent_id == "sca-remediation":
        if payload is None:
            errors.append("sca-remediation output must include a JSON object")
        else:
            errors.extend(validate_sca_gate_payload(payload))
            errors.extend(_project_evidence_gap_errors(payload, require_options=False))
    elif agent_id == "remediation-planner":
        if payload is None:
            errors.append("remediation-planner output must include a JSON object")
        else:
            errors.extend(_remediation_planner_errors(payload))
    elif payload is not None:
        errors.extend(_empty_data_gap_errors(payload))
    return _dedupe(errors)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Extract the last JSON object from mixed prose and code-fenced output."""

    decoder = json.JSONDecoder()
    spans: list[tuple[int, int, dict[str, Any]]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            spans.append((index, index + end, value))
    outer_spans = [
        item
        for item in spans
        if not any(
            other_start < item[0] and item[1] <= other_end
            for other_start, other_end, _other_value in spans
        )
    ]
    selected = outer_spans[-1:] or spans[-1:]
    return selected[0][2] if selected else None


def _remediation_planner_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    project_resolution = _dict(payload.get("project_resolution"))
    status = _text(project_resolution.get("status"))
    if not status:
        errors.append("project_resolution.status: required for remediation-planner outputs")
    if status == "resolved":
        for field in ("project_uuid", "namespace", "namespace_provenance"):
            if not _text(project_resolution.get(field)):
                errors.append(f"project_resolution.{field}: required when status is resolved")
    errors.extend(_project_evidence_gap_errors(payload, require_options=True))

    selected = payload.get("selected_remediation")
    options = _list(payload.get("remediation_options"))
    if selected not in (None, {}) and not options:
        errors.append("selected_remediation: cannot select remediation without verified remediation_options")
    return errors


def _project_evidence_gap_errors(
    payload: dict[str, Any],
    *,
    require_options: bool,
) -> list[str]:
    errors: list[str] = []
    data_gaps = _string_list(payload.get("data_gaps"))
    has_finding_evidence = bool(
        _list(payload.get("findings"))
        or _list(payload.get("sca_findings"))
        or _list(payload.get("remediation_candidates"))
        or _list(payload.get("remediation_options"))
        or _uia_contains_fixed_finding_evidence(payload.get("uia_evidence"))
    )
    has_uia_evidence = bool(_list(payload.get("uia_evidence")) or _list(payload.get("version_upgrades")))
    evidence_queries = _list(payload.get("evidence_queries"))
    queried_finding = _evidence_query_mentions(evidence_queries, ("Finding", "findings"))
    queried_uia = _evidence_query_mentions(evidence_queries, ("VersionUpgrade", "UIA", "version_upgrades"))

    if not data_gaps and (not has_finding_evidence or not has_uia_evidence):
        errors.append("data_gaps: cannot be empty when Finding or VersionUpgrade/UIA evidence is absent")
    if not has_finding_evidence and not any("finding" in gap.lower() for gap in data_gaps):
        errors.append("data_gaps: missing Finding evidence gap")
    if not has_uia_evidence and not any(("uia" in gap.lower() or "versionupgrade" in gap.lower() or "version_upgrade" in gap.lower()) for gap in data_gaps):
        errors.append("data_gaps: missing VersionUpgrade/UIA evidence gap")
    if require_options and not evidence_queries and not data_gaps:
        errors.append("evidence_queries: required when remediation evidence is claimed")
    if evidence_queries and not queried_finding and not any("finding" in gap.lower() for gap in data_gaps):
        errors.append("evidence_queries: Finding query or Finding data gap required")
    if evidence_queries and not queried_uia and not any(("uia" in gap.lower() or "versionupgrade" in gap.lower() or "version_upgrade" in gap.lower()) for gap in data_gaps):
        errors.append("evidence_queries: VersionUpgrade/UIA query or data gap required")
    return errors


def _empty_data_gap_errors(payload: dict[str, Any]) -> list[str]:
    if "data_gaps" in payload and payload.get("data_gaps") == []:
        return []
    return []


def _evidence_query_mentions(items: list[Any], terms: tuple[str, ...]) -> bool:
    haystack = " ".join(json.dumps(item, sort_keys=True) for item in items)
    lower = haystack.lower()
    return any(term.lower() in lower for term in terms)


def _uia_contains_fixed_finding_evidence(value: Any) -> bool:
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        if _list(item.get("fixed_findings")) or _list(item.get("sample_fixed_findings")):
            return True
        if _int(item.get("total_findings_fixed") or item.get("findings_fixed")) > 0:
            return True
        severity_reduction = item.get("severity_reduction")
        if isinstance(severity_reduction, dict):
            for reduction in severity_reduction.values():
                if isinstance(reduction, dict) and _int(
                    reduction.get("fixed_count") or reduction.get("reachable_fixed_count")
                ) > 0:
                    return True
    return False


def _has_invalid_memory_provenance(text: str) -> bool:
    for match in MEMORY_PROVENANCE_RE.finditer(text):
        snippet = text[max(0, match.start() - 80) : min(len(text), match.end() + 80)]
        lower = snippet.lower()
        if any(
            phrase in lower
            for phrase in (
                "not memory",
                "not from memory",
                "not remembered",
                "did not use",
                "do not use",
                "does not use",
                "not use it",
                "not use them",
                "not used",
                "cannot prove",
                "can't prove",
            )
        ):
            continue
        if "procedural memory" in lower and "proof" in lower:
            continue
        return True
    return False


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            fields = [
                item.get("id"),
                item.get("signal"),
                item.get("reason"),
                item.get("description"),
            ]
            text = " ".join(field for field in fields if isinstance(field, str))
            if text:
                result.append(text)
    return result


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _dedupe(errors: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for error in errors:
        if error not in seen:
            seen.add(error)
            result.append(error)
    return result

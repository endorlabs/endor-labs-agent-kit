"""Lint captured agent outputs for release-blocking QA regressions."""

from __future__ import annotations

import json
import re
from typing import Any

from endor_agent_kit.sca_remediation import validate_sca_gate_payload
from endor_agent_kit.structured_output_contracts import (
    known_structured_agent_ids,
    validate_structured_output_payload,
)

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

READ_ONLY_AGENTS = frozenset(
    {
        "dependency-decision-helper",
        "endor-troubleshooter",
        "package-risk-summary",
        "probe-droid",
        "remediation-planner",
        "repository-dependency-reviewer",
        "upgrade-impact-analysis",
        "vulnerability-explainer",
    }
)

PROJECT_GATE_AGENTS = frozenset({"sca-remediation", "remediation-planner"})
STRUCTURED_OUTPUT_AGENTS = frozenset(known_structured_agent_ids())

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
ENDORCTL_API_LINE_RE = re.compile(r"endorctl\s+api\s+(?:list|get)\b[^\n`]*", re.IGNORECASE)
MUTATION_COMMAND_RE = re.compile(
    r"\b(?:"
    r"endorctl\s+scan|"
    r"endorctl\s+api\s+(?:create|update|delete)|"
    r"gh\s+pr\s+(?:create|merge|edit|comment)|"
    r"git\s+(?:clone|checkout\s+-b|switch\s+-c|commit|push)|"
    r"curl\b[^\n]*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)"
    r")\b",
    re.IGNORECASE,
)
MUTATION_STATUS_VALUES = frozenset(
    {
        "applied",
        "branch_created",
        "commented",
        "committed",
        "created",
        "merged",
        "opened",
        "pushed",
        "updated",
        "written",
    }
)


def lint_agent_output(agent_id: str, text: str, *, task_profile: str | None = None) -> list[str]:
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
    errors.extend(_endorctl_command_shape_errors(text))

    payload = extract_json_object(text)
    if agent_id in STRUCTURED_OUTPUT_AGENTS and payload is None:
        errors.append(f"{agent_id} output must include a JSON object")
        if agent_id in READ_ONLY_AGENTS and MUTATION_COMMAND_RE.search(text):
            errors.append("read-only workflow must not include mutation commands; put proposed mutations in future_action_contracts with confirmation_required")
    elif payload is not None:
        errors.extend(validate_structured_output_payload(agent_id, payload))
        errors.extend(_scope_normalization_errors(agent_id, payload))
        errors.extend(_mutability_gate_errors(agent_id, payload))

    if agent_id == "sca-remediation" and payload is not None:
        errors.extend(validate_sca_gate_payload(payload))
        errors.extend(_project_evidence_gap_errors(payload, require_options=False))
        if task_profile == "selection-plan":
            errors.extend(_selection_plan_query_efficiency_errors(payload))
    elif agent_id == "remediation-planner" and payload is not None:
        errors.extend(_remediation_planner_errors(payload))
        if task_profile == "selection-plan":
            errors.extend(_selection_plan_query_efficiency_errors(payload))
    elif payload is not None:
        if agent_id == "probe-droid":
            errors.extend(_probe_droid_errors(payload))
        elif agent_id == "endor-troubleshooter":
            errors.extend(_endor_troubleshooter_errors(payload))
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
    if not has_uia_evidence:
        has_uia_evidence = _remediation_options_contain_uia_evidence(payload.get("remediation_options"))
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


def _scope_normalization_errors(agent_id: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    project_resolution = _dict(payload.get("project_resolution"))
    if project_resolution:
        errors.extend(_resolved_scope_errors("project_resolution", project_resolution))
    report_scope = _dict(payload.get("report_scope"))
    if agent_id == "probe-droid" and report_scope:
        if not _text(report_scope.get("mode")):
            errors.append("report_scope.mode: required for probe-droid outputs")
        has_endor_evidence = _evidence_query_mentions(_list(payload.get("evidence_queries")), ("Project", "Endor"))
        if has_endor_evidence:
            if not _text(report_scope.get("namespace") or report_scope.get("endor_namespace")):
                errors.append("report_scope.namespace: required when Endor project evidence is queried")
            if not _text(report_scope.get("namespace_provenance")):
                errors.append("report_scope.namespace_provenance: required when Endor project evidence is queried")
    return errors


def _resolved_scope_errors(label: str, scope: dict[str, Any]) -> list[str]:
    status = _text(scope.get("status")).lower()
    if status != "resolved":
        return []
    errors: list[str] = []
    for field in ("project_uuid", "namespace", "namespace_provenance"):
        if not _text(scope.get(field)):
            errors.append(f"{label}.{field}: required when status is resolved")
    if not (_text(scope.get("repo_full_name")) or _text(scope.get("normalized_repo_full_name"))):
        errors.append(f"{label}.repo_full_name: normalized repository identity required when status is resolved")
    if not (_text(scope.get("default_branch")) or _text(scope.get("selected_branch")) or _text(scope.get("monitored_branch"))):
        errors.append(f"{label}.default_branch: branch provenance required when status is resolved")
    if "traverse_attempted" not in scope:
        errors.append(f"{label}.traverse_attempted: required when status is resolved")
    return errors


def _mutability_gate_errors(agent_id: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if agent_id in READ_ONLY_AGENTS:
        for path, item in _walk_json(payload):
            if isinstance(item, dict):
                status = _text(item.get("status")).lower()
                if status in MUTATION_STATUS_VALUES:
                    errors.append(f"{path}.status: read-only workflow cannot claim mutation status {status!r}")
                item_text = " ".join(value for value in item.values() if isinstance(value, str))
                if MUTATION_COMMAND_RE.search(item_text) and item.get("confirmation_required") is not True:
                    errors.append(f"{path}: mutation command requires confirmation_required=true and must remain a future action")
    else:
        for path, item in _walk_json(payload):
            if not isinstance(item, dict):
                continue
            item_text = " ".join(value for value in item.values() if isinstance(value, str))
            if MUTATION_COMMAND_RE.search(item_text) and item.get("confirmation_required") is False:
                errors.append(f"{path}: mutation command cannot be marked confirmation_required=false")
    return errors


def _probe_droid_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in (
        "executive_report",
        "report_scope",
        "coverage_summary",
        "github_inventory_summary",
        "github_app_coverage",
    ):
        if not _dict(payload.get(field)):
            errors.append(f"{field}: must be a non-empty object for probe-droid outputs")
    for field in (
        "not_onboarded_repositories",
        "onboarded_repositories_with_gaps",
        "onboarded_healthy_repositories",
        "ambiguous_matches",
        "excluded_repositories",
    ):
        for index, row in enumerate(_list(payload.get(field))):
            if not isinstance(row, dict):
                errors.append(f"{field}[{index}]: must be an object")
                continue
            if not (_text(row.get("repository")) or _text(row.get("repo_full_name"))):
                errors.append(f"{field}[{index}].repository: normalized owner/repo required")
            if field != "excluded_repositories" and not _repo_row_default_branch(row):
                errors.append(f"{field}[{index}].default_branch: required for monitored-branch comparison")
            if field in {"onboarded_repositories_with_gaps", "onboarded_healthy_repositories"}:
                endor_project = _dict(row.get("endor_project"))
                if not _repo_row_project_uuid(row, endor_project):
                    errors.append(f"{field}[{index}].endor_project.project_uuid: required for onboarded repositories")
                if not _text(row.get("endor_monitored_branch")) and not _repo_row_has_branch_gap(row):
                    errors.append(f"{field}[{index}].endor_monitored_branch: required for onboarded repositories")
                if field == "onboarded_healthy_repositories" and _repo_row_has_branch_gap(row):
                    errors.append(
                        f"{field}[{index}]: repositories with monitored-branch gaps must be reported under onboarded_repositories_with_gaps"
                    )
    return errors


def _repo_row_default_branch(row: dict[str, Any]) -> str:
    return _text(row.get("default_branch") or row.get("github_default_branch") or row.get("branch"))


def _repo_row_project_uuid(row: dict[str, Any], endor_project: dict[str, Any]) -> str:
    return _text(
        endor_project.get("project_uuid")
        or row.get("project_uuid")
        or row.get("endor_project_uuid")
    )


def _repo_row_has_branch_gap(row: dict[str, Any]) -> bool:
    haystack = json.dumps(row, sort_keys=True).lower()
    return "branch" in haystack and any(
        marker in haystack
        for marker in (
            "gap",
            "unavailable",
            "unknown",
            "not valid",
            "cannot confirm",
            "inferred",
            "null",
        )
    )


def _endor_troubleshooter_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in (
        "executive_summary",
        "intake_classification",
        "evidence_summary",
        "support_escalation_packet",
    ):
        value = payload.get(field)
        if value is not None and not isinstance(value, dict):
            errors.append(f"{field}: must be an object for endor-troubleshooter outputs")
    classification = _dict(payload.get("intake_classification"))
    if classification and not _list(classification.get("issue_lanes")):
        errors.append("intake_classification.issue_lanes: at least one lane or UNKNOWN_OR_INSUFFICIENT_DATA is required")
    for index, item in enumerate(_list(payload.get("recommended_actions"))):
        if not isinstance(item, dict):
            errors.append(f"recommended_actions[{index}]: must be an object")
            continue
        if not _text(item.get("action")):
            errors.append(f"recommended_actions[{index}].action: required")
        if not _text(item.get("validation")):
            errors.append(f"recommended_actions[{index}].validation: required")
    for index, item in enumerate(_list(payload.get("future_action_contracts"))):
        if not isinstance(item, dict):
            errors.append(f"future_action_contracts[{index}]: must be an object")
            continue
        if item.get("confirmation_required") is not True:
            errors.append(f"future_action_contracts[{index}].confirmation_required: must be true")
    return errors


def _evidence_query_mentions(items: list[Any], terms: tuple[str, ...]) -> bool:
    haystack = " ".join(json.dumps(item, sort_keys=True) for item in items)
    lower = haystack.lower()
    return any(term.lower() in lower for term in terms)


def _selection_plan_query_efficiency_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    evidence_queries = _list(payload.get("evidence_queries"))
    saw_version_upgrade = False
    for item in evidence_queries:
        if not isinstance(item, dict):
            continue
        if _item_mentions(item, ("VersionUpgrade", "UIA", "version_upgrades")):
            saw_version_upgrade = True
            continue
        if not _item_mentions(item, ("Finding", "findings")):
            continue
        result_count = _int(item.get("result_count") or item.get("count") or item.get("results"))
        if result_count >= 1000:
            errors.append(
                "evidence_queries: selection-plan must not enumerate broad Finding inventories before VersionUpgrade/UIA narrowing"
            )
        if not saw_version_upgrade:
            errors.append(
                "evidence_queries: selection-plan must query VersionUpgrade/UIA before Finding detail expansion"
            )
    return errors


def _item_mentions(item: dict[str, Any], terms: tuple[str, ...]) -> bool:
    lower = json.dumps(item, sort_keys=True).lower()
    return any(term.lower() in lower for term in terms)


def _walk_json(value: Any, path: str = "$"):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_json(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_json(child, f"{path}[{index}]")


def _endorctl_command_shape_errors(text: str) -> list[str]:
    errors: list[str] = []
    for match in ENDORCTL_API_LINE_RE.finditer(text):
        command = match.group(0)
        lower = command.lower()
        if "endorctl api get" in lower and (" --filter " in lower or " -f " in lower):
            errors.append("endorctl query recipe: api get must not use filters; use --uuid or api list")
        if (" -n " not in lower and " --namespace " not in lower):
            errors.append("endorctl query recipe: api commands must include explicit namespace")
        if "endorctl api list" in lower and " --field-mask " not in lower:
            errors.append("endorctl query recipe: api list commands must include --field-mask")
        if "endorctl api list" in lower and "finding" in lower and "--list-all" in lower:
            if not _is_scoped_finding_list_all_query(lower):
                errors.append("endorctl query recipe: broad Finding --list-all is not allowed")
    return errors


def _is_scoped_finding_list_all_query(lower_command: str) -> bool:
    if (
        "context.type==context_type_main" in lower_command
        and "spec.project_uuid" in lower_command
        and "system_evaluation_method_definition_ai_sast" in lower_command
    ):
        return True
    return (
        "uuid==" in lower_command
        or "spec.target" in lower_command
        or "target_dependency" in lower_command
    )


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


def _remediation_options_contain_uia_evidence(value: Any) -> bool:
    for item in _list(value):
        if not isinstance(item, dict):
            continue
        if _text(item.get("version_upgrade_uuid") or item.get("uia_uuid")):
            return True
        if _item_mentions(item, ("VersionUpgrade", "UIA", "version_upgrade")):
            return True
        if _int(item.get("total_findings_fixed") or item.get("findings_fixed")) > 0:
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
                "no remembered",
                "without remembered",
                "without using remembered",
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

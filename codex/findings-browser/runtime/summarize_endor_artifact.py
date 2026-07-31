#!/usr/bin/env python3
"""Summarize a large Endor Agent API artifact without exposing its rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, Sequence


SCHEMA_VERSION = "endor.agent-artifact-summary/v1"
CICD_SCORE_SCHEMA_VERSION = "endor.cicd-posture-score/v1"
DEFAULT_COLLECTION_PATH = "list.objects"
DEFAULT_UNIQUE_FIELD = "uuid"
DEFAULT_MAX_BYTES = 512 * 1024 * 1024
DEFAULT_CAPTURE_TIMEOUT_SECONDS = 300
PROJECTIONS = frozenset(
    {
        "integrity",
        "ai-sast-selection",
        "configuration-selected-projects",
        "configuration-fleet-projects",
        "configuration-scans",
        "configuration-packages",
    }
)
CICD_RAW_COUNT_KEYS = (
    "repositories_in_scope",
    "repositories_with_branch_protection",
    "repositories_with_required_reviews",
    "workflows_reviewed",
    "third_party_actions",
    "unpinned_actions",
    "overbroad_permissions",
    "risky_triggers",
    "self_hosted_runners",
    "update_automation_present",
    "endor_critical_findings",
    "endor_high_findings",
    "endor_cicd_findings",
    "endor_scpm_findings",
    "endor_gha_findings",
    "endor_supply_chain_findings",
)
CICD_DIMENSION_SCORE_KEYS = (
    "branch_protection",
    "workflow_hardening",
    "action_pinning",
    "permissions",
    "runner_security",
    "endor_findings",
)
CICD_CRITICAL_OVERRIDE_TYPES = (
    "endor_critical_finding",
    "exposed_self_hosted_runner",
    "privileged_workflow_risky_trigger",
)
AI_SAST_METHOD = "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"
AI_SAST_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
AI_SAST_LEVEL_RANK = {
    level: len(AI_SAST_LEVELS) - index
    for index, level in enumerate(AI_SAST_LEVELS)
}
AI_SAST_SELECTION_FIELD_MASK = frozenset(
    {
        "uuid",
        "context.type",
        "spec.project_uuid",
        "spec.method",
        "spec.level",
        "spec.source_code_version",
    }
)


class ArtifactSummaryError(ValueError):
    """A safe, machine-readable artifact validation failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def summarize_artifact(
    artifact: str | Path,
    *,
    collection_path: str = DEFAULT_COLLECTION_PATH,
    unique_field: str = DEFAULT_UNIQUE_FIELD,
    max_bytes: int = DEFAULT_MAX_BYTES,
    projection: str = "integrity",
) -> dict[str, Any]:
    """Read one artifact once and return compact integrity metadata.

    The returned record never contains row values. The default contract accepts
    the JSON envelope emitted by ``endorctl agent api ... list -o json`` and
    requires a unique, non-empty UUID for each object.
    """

    path = Path(artifact).expanduser().absolute()
    if max_bytes <= 0:
        raise ArtifactSummaryError("invalid_max_bytes", "max_bytes must be positive")
    try:
        path_stat = path.lstat()
    except OSError as exc:
        raise ArtifactSummaryError("artifact_unavailable", "artifact is not readable") from exc
    if stat.S_ISLNK(path_stat.st_mode):
        raise ArtifactSummaryError("artifact_symlink_rejected", "artifact must not be a symlink")
    if not stat.S_ISREG(path_stat.st_mode):
        raise ArtifactSummaryError("artifact_not_regular", "artifact must be a regular file")
    if path_stat.st_size > max_bytes:
        raise ArtifactSummaryError(
            "artifact_too_large",
            f"artifact exceeds configured maximum of {max_bytes} bytes",
        )

    try:
        with path.open("rb") as handle:
            opened_stat = os.fstat(handle.fileno())
            data = handle.read(max_bytes + 1)
            final_stat = os.fstat(handle.fileno())
    except OSError as exc:
        raise ArtifactSummaryError("artifact_unavailable", "artifact is not readable") from exc
    if len(data) > max_bytes:
        raise ArtifactSummaryError(
            "artifact_too_large",
            f"artifact exceeds configured maximum of {max_bytes} bytes",
        )
    if (
        opened_stat.st_dev != final_stat.st_dev
        or opened_stat.st_ino != final_stat.st_ino
        or opened_stat.st_size != final_stat.st_size
        or opened_stat.st_mtime_ns != final_stat.st_mtime_ns
        or len(data) != final_stat.st_size
    ):
        raise ArtifactSummaryError(
            "artifact_changed_during_read",
            "artifact changed while it was being summarized",
        )

    try:
        payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactSummaryError("invalid_json", "artifact is not valid JSON") from exc
    objects = _mapping_path(payload, collection_path)
    if not isinstance(objects, list):
        raise ArtifactSummaryError(
            "collection_not_array",
            f"collection path {collection_path!r} must contain an array",
        )

    values: list[str] = []
    missing_unique_count = 0
    for row in objects:
        if not isinstance(row, dict):
            raise ArtifactSummaryError(
                "row_not_object",
                "every collection row must be a JSON object",
            )
        value = _optional_mapping_path(row, unique_field)
        if not isinstance(value, str) or not value.strip():
            missing_unique_count += 1
        else:
            values.append(value)
    unique_count = len(set(values))
    duplicate_count = len(values) - unique_count
    if missing_unique_count:
        raise ArtifactSummaryError(
            "missing_unique_values",
            f"{missing_unique_count} rows are missing a non-empty {unique_field!r}",
        )
    if duplicate_count:
        raise ArtifactSummaryError(
            "duplicate_unique_values",
            f"{duplicate_count} rows contain duplicate {unique_field!r} values",
        )

    if projection not in PROJECTIONS:
        raise ArtifactSummaryError("invalid_projection", "unknown artifact projection")
    summary: dict[str, Any] = {
        "artifact_ref": str(path),
        "bytes": len(data),
        "collection_path": collection_path,
        "duplicate_count": duplicate_count,
        "format": "json",
        "missing_unique_count": missing_unique_count,
        "row_count": len(objects),
        "schema_version": SCHEMA_VERSION,
        "sha256": hashlib.sha256(data).hexdigest(),
        "status": "valid",
        "unique_count": unique_count,
        "unique_field": unique_field,
    }
    if projection == "ai-sast-selection":
        summary["projection"] = projection
        summary["selection_summary"] = _ai_sast_selection_projection(objects)
    elif projection != "integrity":
        summary["projection"] = projection
        summary["configuration_summary"] = _configuration_projection(
            objects,
            projection=projection,
        )
    return summary


def capture_and_summarize(
    command: Sequence[str],
    *,
    artifact_dir: str | Path | None = None,
    collection_path: str = DEFAULT_COLLECTION_PATH,
    unique_field: str = DEFAULT_UNIQUE_FIELD,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_seconds: int = DEFAULT_CAPTURE_TIMEOUT_SECONDS,
    projection: str = "integrity",
) -> dict[str, Any]:
    """Execute one read-only Agent API list directly into a protected artifact."""

    normalized = tuple(command[1:] if command and command[0] == "--" else command)
    _validate_capture_command(normalized, projection=projection)
    if timeout_seconds <= 0:
        raise ArtifactSummaryError("invalid_timeout", "timeout_seconds must be positive")

    if artifact_dir is None:
        destination = Path(tempfile.gettempdir()) / "endor-agent-artifacts"
    else:
        destination = Path(artifact_dir).expanduser().absolute()
    try:
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, artifact_name = tempfile.mkstemp(
            prefix="agent-api-",
            suffix=".json",
            dir=destination,
        )
        os.fchmod(descriptor, 0o600)
    except OSError as exc:
        raise ArtifactSummaryError(
            "artifact_create_failed",
            "unable to create a protected host artifact",
        ) from exc

    artifact = Path(artifact_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            completed = subprocess.run(
                normalized,
                check=False,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
            )
    except subprocess.TimeoutExpired as exc:
        artifact.unlink(missing_ok=True)
        raise ArtifactSummaryError(
            "endorctl_timeout",
            f"endorctl Agent API capture exceeded {timeout_seconds} seconds",
        ) from exc
    except OSError as exc:
        artifact.unlink(missing_ok=True)
        raise ArtifactSummaryError(
            "endorctl_unavailable",
            "unable to execute the selected endorctl binary",
        ) from exc
    if completed.returncode != 0:
        artifact.unlink(missing_ok=True)
        raise ArtifactSummaryError(
            "endorctl_failed",
            f"endorctl Agent API capture exited with status {completed.returncode}",
        )

    try:
        summary = summarize_artifact(
            artifact,
            collection_path=collection_path,
            unique_field=unique_field,
            max_bytes=max_bytes,
            projection=projection,
        )
        if projection == "ai-sast-selection":
            summary["query_completeness"] = "list_all"
        return summary
    except ArtifactSummaryError:
        artifact.unlink(missing_ok=True)
        raise


def score_cicd_posture(
    raw_counts: dict[str, Any],
    *,
    declared_override_types: Sequence[str] = (),
) -> dict[str, Any]:
    """Return the deterministic CI/CD posture score without an LLM arithmetic loop."""

    if not isinstance(raw_counts, dict):
        raise ArtifactSummaryError("invalid_raw_counts", "raw_counts must be a JSON object")
    missing = [key for key in CICD_RAW_COUNT_KEYS if key not in raw_counts]
    unknown = sorted(set(raw_counts) - set(CICD_RAW_COUNT_KEYS))
    if missing:
        raise ArtifactSummaryError(
            "missing_raw_counts",
            "raw_counts is missing required keys",
        )
    if unknown:
        raise ArtifactSummaryError(
            "unknown_raw_counts",
            "raw_counts contains unsupported keys",
        )
    counts: dict[str, int] = {}
    for key in CICD_RAW_COUNT_KEYS:
        value = raw_counts[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ArtifactSummaryError(
                "invalid_raw_count",
                f"raw_counts.{key} must be a non-negative integer",
            )
        counts[key] = value

    repositories = counts["repositories_in_scope"]
    if any(
        counts[key] > repositories
        for key in (
            "repositories_with_branch_protection",
            "repositories_with_required_reviews",
            "update_automation_present",
        )
    ):
        raise ArtifactSummaryError(
            "invalid_repository_count",
            "repository posture counts cannot exceed repositories_in_scope",
        )
    if counts["unpinned_actions"] > counts["third_party_actions"]:
        raise ArtifactSummaryError(
            "invalid_action_count",
            "unpinned_actions cannot exceed third_party_actions",
        )

    overrides = tuple(dict.fromkeys(declared_override_types))
    if any(value not in CICD_CRITICAL_OVERRIDE_TYPES for value in overrides):
        raise ArtifactSummaryError(
            "invalid_critical_override",
            "critical override type is unsupported",
        )
    posture_findings = sum(
        counts[key]
        for key in (
            "endor_cicd_findings",
            "endor_scpm_findings",
            "endor_gha_findings",
            "endor_supply_chain_findings",
        )
    )
    update_gap_penalty = (
        _round_half_up(
            20
            * (repositories - min(counts["update_automation_present"], repositories))
            / repositories
        )
        if repositories
        else 0
    )
    workflows_reviewed = counts["workflows_reviewed"]
    third_party_actions = counts["third_party_actions"]
    if third_party_actions:
        action_pinning = _clamp_score(
            100
            - _round_half_up(
                100 * counts["unpinned_actions"] / third_party_actions
            )
        )
    elif workflows_reviewed:
        action_pinning = 100
    else:
        action_pinning = 60
    dimensions = {
        "branch_protection": (
            _clamp_score(
                _round_half_up(
                    100
                    * (
                        counts["repositories_with_branch_protection"]
                        + counts["repositories_with_required_reviews"]
                    )
                    / (2 * repositories)
                )
            )
            if repositories
            else 0
        ),
        "workflow_hardening": _clamp_score(
            100
            - counts["risky_triggers"] * 15
            - counts["overbroad_permissions"] * 10
            - update_gap_penalty
        ),
        "action_pinning": action_pinning,
        "permissions": (
            _clamp_score(100 - counts["overbroad_permissions"] * 20)
            if workflows_reviewed or counts["overbroad_permissions"]
            else 60
        ),
        "runner_security": (
            _clamp_score(100 - counts["self_hosted_runners"] * 20)
            if workflows_reviewed or counts["self_hosted_runners"]
            else 60
        ),
        "endor_findings": _clamp_score(
            100
            - counts["endor_critical_findings"] * 25
            - counts["endor_high_findings"] * 8
            - posture_findings * 2
        ),
    }
    overall = _round_half_up(sum(dimensions.values()) / len(dimensions))
    critical = counts["endor_critical_findings"] > 0 or any(
        value in CICD_CRITICAL_OVERRIDE_TYPES for value in overrides
    )
    verdict = _cicd_verdict(overall, critical=critical)
    return {
        "critical_override_required": critical,
        "dimension_scores": dimensions,
        "posture_verdict": verdict,
        "schema_version": CICD_SCORE_SCHEMA_VERSION,
        "score_validation": {
            "dimension_weights": {key: 1 for key in CICD_DIMENSION_SCORE_KEYS},
            "formula_version": "cicd-posture-v2",
            "overall_score": overall,
            "recomputed": True,
            "verdict_band": verdict,
        },
        "status": "valid",
    }


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _cicd_verdict(overall: int, *, critical: bool) -> str:
    if critical or overall < 40:
        return "CRITICAL"
    if overall < 60:
        return "HIGH_RISK"
    if overall < 80:
        return "NEEDS_ATTENTION"
    return "HEALTHY"


def _validate_capture_command(
    command: Sequence[str],
    *,
    projection: str = "integrity",
) -> None:
    if len(command) < 6 or Path(command[0]).name != "endorctl":
        raise ArtifactSummaryError(
            "invalid_capture_command",
            "capture requires a direct endorctl Agent API list command",
        )
    if tuple(command[1:3]) != ("agent", "api") or "list" not in command[3:]:
        raise ArtifactSummaryError(
            "invalid_capture_command",
            "capture permits only endorctl agent api list",
        )
    if "--agent-id" not in command or not _option_value(command, "--agent-id"):
        raise ArtifactSummaryError(
            "missing_agent_id",
            "capture requires a canonical --agent-id",
        )
    if not any(option in command for option in ("-r", "--resource")):
        raise ArtifactSummaryError(
            "missing_resource",
            "capture requires an explicit resource",
        )
    if "--field-mask" not in command or not _option_value(command, "--field-mask"):
        raise ArtifactSummaryError(
            "missing_field_mask",
            "capture requires an explicit minimal field mask",
        )
    if "--count" in command:
        raise ArtifactSummaryError(
            "count_capture_rejected",
            "capture is for row artifacts, not --count output",
        )
    output_format = _option_value(command, "-o") or _option_value(command, "--output")
    if output_format != "json":
        raise ArtifactSummaryError(
            "invalid_output_format",
            "capture requires JSON output",
        )
    if projection == "ai-sast-selection":
        _validate_ai_sast_capture_command(command)


def _option_value(command: Sequence[str], option: str) -> str:
    try:
        index = command.index(option)
    except ValueError:
        return ""
    if index + 1 >= len(command):
        return ""
    value = command[index + 1]
    return "" if value.startswith("-") else value


def _validate_ai_sast_capture_command(command: Sequence[str]) -> None:
    resource = _option_value(command, "-r") or _option_value(command, "--resource")
    if resource != "Finding":
        raise ArtifactSummaryError(
            "invalid_ai_sast_resource",
            "AI SAST selection capture requires the Finding resource",
        )
    if "--list-all" not in command:
        raise ArtifactSummaryError(
            "ai_sast_complete_inventory_required",
            "AI SAST selection capture requires one complete --list-all inventory",
        )
    if "--traverse" in command:
        raise ArtifactSummaryError(
            "ai_sast_traverse_rejected",
            "project-scoped AI SAST selection must not traverse child namespaces",
        )
    field_mask = _option_value(command, "--field-mask")
    fields = frozenset(part.strip() for part in field_mask.split(",") if part.strip())
    if fields != AI_SAST_SELECTION_FIELD_MASK:
        raise ArtifactSummaryError(
            "invalid_ai_sast_field_mask",
            "AI SAST selection capture requires the exact compact selection field mask",
        )
    filter_expression = _option_value(command, "--filter") or _option_value(command, "-f")
    required_filters = (
        "context.type==CONTEXT_TYPE_MAIN",
        "spec.project_uuid==",
        f'spec.method=="{AI_SAST_METHOD}"',
    )
    if not filter_expression or any(
        required not in filter_expression for required in required_filters
    ):
        raise ArtifactSummaryError(
            "invalid_ai_sast_filter",
            "AI SAST selection capture requires main context, one project UUID, and the full AI SAST method enum",
        )


def _mapping_path(payload: Any, dotted_path: str) -> Any:
    value = payload
    for segment in _path_segments(dotted_path):
        if not isinstance(value, dict) or segment not in value:
            raise ArtifactSummaryError(
                "missing_collection_path",
                f"artifact is missing collection path {dotted_path!r}",
            )
        value = value[segment]
    return value


def _optional_mapping_path(payload: dict[str, Any], dotted_path: str) -> Any:
    value: Any = payload
    for segment in _path_segments(dotted_path):
        if not isinstance(value, dict) or segment not in value:
            return None
        value = value[segment]
    return value


def _ai_sast_selection_projection(objects: list[dict[str, Any]]) -> dict[str, Any]:
    severity_counts = {level: 0 for level in AI_SAST_LEVELS}
    candidates: list[tuple[int, str, str]] = []
    project_uuids: set[str] = set()
    for row in objects:
        context = row.get("context") if isinstance(row.get("context"), dict) else {}
        spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
        if context.get("type") != "CONTEXT_TYPE_MAIN":
            raise ArtifactSummaryError(
                "invalid_ai_sast_context",
                "AI SAST selection rows must all use main context",
            )
        if spec.get("method") != AI_SAST_METHOD:
            raise ArtifactSummaryError(
                "invalid_ai_sast_method",
                "AI SAST selection rows must all use the full AI SAST method enum",
            )
        project_uuid = spec.get("project_uuid")
        if not isinstance(project_uuid, str) or not project_uuid:
            raise ArtifactSummaryError(
                "missing_ai_sast_project_uuid",
                "AI SAST selection rows require one non-empty project UUID",
            )
        project_uuids.add(project_uuid)
        raw_level = spec.get("level")
        if not isinstance(raw_level, str):
            raise ArtifactSummaryError(
                "invalid_ai_sast_level",
                "AI SAST selection rows require a supported severity level",
            )
        level = raw_level.removeprefix("FINDING_LEVEL_").upper()
        if level not in AI_SAST_LEVEL_RANK:
            raise ArtifactSummaryError(
                "invalid_ai_sast_level",
                "AI SAST selection rows require a supported severity level",
            )
        finding_uuid = row["uuid"]
        severity_counts[level] += 1
        candidates.append((AI_SAST_LEVEL_RANK[level], finding_uuid, level))
    if len(project_uuids) > 1:
        raise ArtifactSummaryError(
            "mixed_ai_sast_project_scope",
            "AI SAST selection rows must belong to one project",
        )
    candidates.sort(key=lambda item: (-item[0], item[1]))
    selected = candidates[0] if candidates else None
    selected_level = selected[2] if selected else None
    return {
        "all_artifact_rows_evaluated": True,
        "project_uuid": next(iter(project_uuids), None),
        "selected_finding_uuid": selected[1] if selected else None,
        "selected_level": selected_level,
        "selection_rule": "severity_desc_uuid_asc_v1",
        "severity_counts": severity_counts,
        "tie_count_at_selected_level": (
            severity_counts[selected_level] if selected_level is not None else 0
        ),
    }


def _path_segments(dotted_path: str) -> tuple[str, ...]:
    segments = tuple(dotted_path.split("."))
    if not segments or any(not segment for segment in segments):
        raise ArtifactSummaryError("invalid_path", "JSON paths must use non-empty dot segments")
    return segments


def _configuration_projection(
    objects: list[dict[str, Any]],
    *,
    projection: str,
) -> dict[str, Any]:
    if projection in {
        "configuration-selected-projects",
        "configuration-fleet-projects",
    }:
        return _configuration_projects(objects, selected=projection.endswith("selected-projects"))
    if projection == "configuration-scans":
        return _configuration_scans(objects)
    if projection == "configuration-packages":
        return _configuration_packages(objects)
    raise ArtifactSummaryError("invalid_projection", "unknown configuration projection")


def _configuration_projects(
    objects: list[dict[str, Any]],
    *,
    selected: bool,
) -> dict[str, Any]:
    projects: list[dict[str, Any]] = []
    invalid_uuid_count = 0
    for row in objects:
        uuid = row.get("uuid")
        if not isinstance(uuid, str) or not uuid or not all(
            character.isalnum() or character in "-_" for character in uuid
        ):
            invalid_uuid_count += 1
            continue
        spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
        git = spec.get("git") if isinstance(spec.get("git"), dict) else {}
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        repo = git.get("full_name") or git.get("repository") or meta.get("name")
        projects.append(
            {
                "project_uuid": uuid,
                "repo_full_name": repo if isinstance(repo, str) else None,
                "parent_uuid": meta.get("parent_uuid"),
            }
        )
    projects.sort(key=lambda item: (str(item["repo_full_name"]), item["project_uuid"]))
    result: dict[str, Any] = {
        "project_count": len(projects),
        "invalid_uuid_count": invalid_uuid_count,
        "project_samples": projects[:50],
        "project_samples_truncated": len(projects) > 50,
    }
    if selected:
        if len(projects) > 100:
            raise ArtifactSummaryError(
                "selected_scope_too_large",
                "selected repository projection supports at most 100 projects; use fleet mode",
            )
        ids = [item["project_uuid"] for item in projects]
        if not ids:
            raise ArtifactSummaryError(
                "selected_scope_empty",
                "selected repository projection did not resolve any safe project UUIDs",
            )
        scan_selector = "(" + " or ".join(
            f'meta.parent_uuid=="{uuid}"' for uuid in ids
        ) + ")"
        package_selector = "(" + " or ".join(
            f'spec.project_uuid=="{uuid}"' for uuid in ids
        ) + ")"
        result.update(
            {
                "projects": projects,
                "scan_project_filter": (
                    f"{scan_selector} and context.type==CONTEXT_TYPE_MAIN"
                ),
                "package_project_filter": (
                    f"{package_selector} and context.type==CONTEXT_TYPE_MAIN"
                ),
            }
        )
    return result


def _configuration_scans(objects: list[dict[str, Any]]) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    for row in objects:
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        project_uuid = meta.get("parent_uuid")
        if not isinstance(project_uuid, str) or not project_uuid:
            continue
        timestamp = str(meta.get("create_time") or meta.get("update_time") or "")
        prior = latest.get(project_uuid)
        if prior is None or timestamp > prior["timestamp"]:
            spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
            stats = spec.get("stats") if isinstance(spec.get("stats"), dict) else {}
            latest[project_uuid] = {
                "project_uuid": project_uuid,
                "scan_result_uuid": row.get("uuid"),
                "timestamp": timestamp,
                "status": spec.get("status"),
                "refs": (spec.get("refs") or [])[:8],
                "stats": {
                    key: int(stats.get(key) or 0)
                    for key in (
                        "scan_failures",
                        "call_graph_errors",
                        "dependency_analysis_num_unresolved",
                        "remediations_num_errors",
                        "notifications_num_errors",
                    )
                },
            }
    cohorts: dict[str, list[str]] = {}
    unhealthy: list[dict[str, Any]] = []
    for row in latest.values():
        reasons: list[str] = []
        if row["status"] != "STATUS_SUCCESS":
            reasons.append(str(row["status"] or "STATUS_UNKNOWN"))
        reasons.extend(key for key, value in row["stats"].items() if value > 0)
        if reasons:
            unhealthy.append({**row, "failure_signatures": reasons})
            for reason in reasons:
                cohorts.setdefault(reason, []).append(row["project_uuid"])
    unhealthy.sort(key=lambda item: item["project_uuid"])
    return {
        "projects_with_scan_results": len(latest),
        "healthy_project_count": len(latest) - len(unhealthy),
        "unhealthy_project_count": len(unhealthy),
        "issue_cohorts": [
            {
                "signature": signature,
                "project_count": len(projects),
                "project_uuid_samples": sorted(projects)[:25],
                "samples_truncated": len(projects) > 25,
            }
            for signature, projects in sorted(cohorts.items())
        ],
        "unhealthy_project_samples": unhealthy[:100],
        "unhealthy_project_samples_truncated": len(unhealthy) > 100,
    }


def _configuration_packages(objects: list[dict[str, Any]]) -> dict[str, Any]:
    cohorts: dict[str, set[str]] = {}
    affected_projects: set[str] = set()
    for row in objects:
        spec = row.get("spec") if isinstance(row.get("spec"), dict) else {}
        project_uuid = spec.get("project_uuid")
        if not isinstance(project_uuid, str) or not project_uuid:
            continue
        resolution_errors = spec.get("resolution_errors")
        signatures: list[str] = []
        if isinstance(resolution_errors, dict):
            signatures = sorted(
                str(key) for key, value in resolution_errors.items() if value not in (None, {}, [], "")
            )
        elif isinstance(resolution_errors, list) and resolution_errors:
            signatures = ["resolution_errors"]
        for signature in signatures:
            affected_projects.add(project_uuid)
            cohorts.setdefault(signature, set()).add(project_uuid)
    return {
        "package_version_count": len(objects),
        "affected_project_count": len(affected_projects),
        "issue_cohorts": [
            {
                "signature": signature,
                "project_count": len(projects),
                "project_uuid_samples": sorted(projects)[:25],
                "samples_truncated": len(projects) > 25,
            }
            for signature, projects in sorted(cohorts.items())
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="summarize_endor_artifact.py",
        description="Validate and summarize one Endor Agent API JSON artifact.",
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)
    summarize = subparsers.add_parser("summarize", help="Summarize an existing artifact")
    summarize.add_argument("artifact", help="Path to the host artifact JSON file")
    capture = subparsers.add_parser(
        "capture",
        help="Capture one endorctl Agent API list and summarize it without model-visible rows",
    )
    capture.add_argument("--artifact-dir", help="Protected host directory for the raw artifact")
    capture.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_CAPTURE_TIMEOUT_SECONDS,
        help=f"endorctl timeout in seconds (default: {DEFAULT_CAPTURE_TIMEOUT_SECONDS})",
    )
    capture.add_argument("command", nargs=argparse.REMAINDER)
    score = subparsers.add_parser(
        "score-cicd-posture",
        help="Compute deterministic CI/CD posture scores from normalized raw counts",
    )
    score.add_argument(
        "--raw-counts-json",
        required=True,
        help="JSON object containing the exact CI/CD posture raw count keys",
    )
    score.add_argument(
        "--critical-override",
        action="append",
        default=[],
        choices=CICD_CRITICAL_OVERRIDE_TYPES,
        help="Verified critical override type; repeat only for distinct types",
    )
    for command_parser in (summarize, capture):
        _add_summary_options(command_parser)
    return parser


def _add_summary_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--projection",
        choices=sorted(PROJECTIONS),
        default="integrity",
        help="Optional deterministic compact projection for a supported workflow",
    )
    parser.add_argument(
        "--collection-path",
        default=DEFAULT_COLLECTION_PATH,
        help=f"JSON collection path (default: {DEFAULT_COLLECTION_PATH})",
    )
    parser.add_argument(
        "--unique-field",
        default=DEFAULT_UNIQUE_FIELD,
        help=f"Unique field required on every row (default: {DEFAULT_UNIQUE_FIELD})",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Maximum artifact size (default: {DEFAULT_MAX_BYTES})",
    )
def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if arguments and arguments[0] not in {
        "capture",
        "score-cicd-posture",
        "summarize",
        "-h",
        "--help",
    }:
        arguments.insert(0, "summarize")
    args = _parser().parse_args(arguments)
    try:
        if args.operation == "capture":
            summary = capture_and_summarize(
                args.command,
                artifact_dir=args.artifact_dir,
                collection_path=args.collection_path,
                unique_field=args.unique_field,
                max_bytes=args.max_bytes,
                timeout_seconds=args.timeout,
                projection=args.projection,
            )
        elif args.operation == "summarize":
            summary = summarize_artifact(
                args.artifact,
                collection_path=args.collection_path,
                unique_field=args.unique_field,
                max_bytes=args.max_bytes,
                projection=args.projection,
            )
        else:
            try:
                raw_counts = json.loads(args.raw_counts_json)
            except json.JSONDecodeError as exc:
                raise ArtifactSummaryError(
                    "invalid_raw_counts_json",
                    "raw counts input is not valid JSON",
                ) from exc
            summary = score_cicd_posture(
                raw_counts,
                declared_override_types=args.critical_override,
            )
    except ArtifactSummaryError as exc:
        error = {
            "error_code": exc.code,
            "message": exc.message,
            "schema_version": SCHEMA_VERSION,
            "status": "invalid",
        }
        sys.stderr.write(json.dumps(error, separators=(",", ":"), sort_keys=True) + "\n")
        return 2
    sys.stdout.write(json.dumps(summary, separators=(",", ":"), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the installed helper
    raise SystemExit(main())

"""Mechanical contracts for CI/CD posture agent outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FORMULA_VERSION = "cicd-posture-v1"

RAW_COUNT_KEYS = (
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

DIMENSION_SCORE_KEYS = (
    "branch_protection",
    "workflow_hardening",
    "action_pinning",
    "permissions",
    "runner_security",
    "endor_findings",
)

VERDICT_BANDS = frozenset({
    "HEALTHY",
    "NEEDS_ATTENTION",
    "HIGH_RISK",
    "CRITICAL",
    "INSUFFICIENT_DATA",
})


def load_json_payload(path: str | Path) -> dict[str, Any]:
    """Load a JSON object used by CI/CD posture contract commands."""

    payload_path = Path(path)
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def validate_cicd_posture_payload(
    payload: dict[str, Any],
    *,
    gate: str = "posture",
) -> list[str]:
    """Validate deterministic CI/CD posture structured output."""

    if gate != "posture":
        return [f"gate: unsupported CI/CD posture gate {gate!r}"]
    if not isinstance(payload, dict):
        return ["payload: must be an object"]

    errors: list[str] = []
    raw_counts = _dict(payload.get("raw_counts"))
    dimension_scores = _dict(payload.get("dimension_scores"))
    score_validation = _dict(payload.get("score_validation"))

    if not raw_counts:
        errors.append("raw_counts: required object")
    if not dimension_scores:
        errors.append("dimension_scores: required object")
    if not score_validation:
        errors.append("score_validation: required object")

    counts = _validated_counts(raw_counts, errors)
    expected_scores = compute_cicd_posture_scores(counts)

    for key in DIMENSION_SCORE_KEYS:
        actual = _optional_int(dimension_scores.get(key))
        if actual is None:
            errors.append(f"dimension_scores.{key}: required integer")
        elif actual != expected_scores["dimension_scores"][key]:
            errors.append(
                f"dimension_scores.{key}: expected {expected_scores['dimension_scores'][key]}, got {actual}"
            )

    formula_version = _text(score_validation.get("formula_version"))
    if formula_version != FORMULA_VERSION:
        errors.append(f"score_validation.formula_version: must be {FORMULA_VERSION}")

    overall = _optional_int(score_validation.get("overall_score"))
    if overall is None:
        errors.append("score_validation.overall_score: required integer")
    elif overall != expected_scores["overall_score"]:
        errors.append(
            f"score_validation.overall_score: expected {expected_scores['overall_score']}, got {overall}"
        )

    expected_band = expected_scores["verdict_band"]
    verdict_band = _text(score_validation.get("verdict_band"))
    if verdict_band != expected_band:
        errors.append(f"score_validation.verdict_band: expected {expected_band}, got {verdict_band or '<missing>'}")

    posture_verdict = _text(payload.get("posture_verdict"))
    if posture_verdict not in VERDICT_BANDS:
        errors.append("posture_verdict: must be one of " + ", ".join(sorted(VERDICT_BANDS)))
    elif posture_verdict == "INSUFFICIENT_DATA":
        if not _list(payload.get("data_gaps")):
            errors.append("data_gaps: required when posture_verdict is INSUFFICIENT_DATA")
    elif posture_verdict != expected_band:
        errors.append(f"posture_verdict: expected {expected_band}, got {posture_verdict}")

    critical_overrides = _list(payload.get("critical_overrides"))
    if expected_scores["critical_override_required"] and not critical_overrides:
        errors.append("critical_overrides: required when critical Endor findings are present")

    for field in (
        "endor_findings",
        "github_evidence",
        "local_ci_evidence",
        "recommended_actions",
        "evidence_queries",
        "data_gaps",
    ):
        if not isinstance(payload.get(field), list):
            errors.append(f"{field}: required array")

    return errors


def compute_cicd_posture_scores(raw_counts: dict[str, int]) -> dict[str, Any]:
    """Compute deterministic CI/CD posture scores from raw counts."""

    counts = {key: _int(raw_counts.get(key)) for key in RAW_COUNT_KEYS}
    repositories = counts["repositories_in_scope"]
    third_party_actions = counts["third_party_actions"]
    posture_finding_count = (
        counts["endor_cicd_findings"]
        + counts["endor_scpm_findings"]
        + counts["endor_gha_findings"]
        + counts["endor_supply_chain_findings"]
    )
    dimension_scores = {
        "branch_protection": (
            _clamp(round(100 * counts["repositories_with_branch_protection"] / repositories))
            if repositories > 0
            else 0
        ),
        "workflow_hardening": _clamp(
            100 - counts["risky_triggers"] * 15 - counts["overbroad_permissions"] * 10
        ),
        "action_pinning": (
            _clamp(100 - round(100 * counts["unpinned_actions"] / third_party_actions))
            if third_party_actions > 0
            else 100
        ),
        "permissions": _clamp(100 - counts["overbroad_permissions"] * 20),
        "runner_security": _clamp(100 - counts["self_hosted_runners"] * 20),
        "endor_findings": _clamp(
            100
            - counts["endor_critical_findings"] * 25
            - counts["endor_high_findings"] * 10
            - posture_finding_count * 5
        ),
    }
    overall = round(sum(dimension_scores.values()) / len(dimension_scores))
    critical_override = counts["endor_critical_findings"] > 0
    verdict_band = _band_for(overall, critical_override=critical_override)
    return {
        "formula_version": FORMULA_VERSION,
        "dimension_scores": dimension_scores,
        "overall_score": overall,
        "verdict_band": verdict_band,
        "critical_override_required": critical_override,
    }


def _band_for(overall_score: int, *, critical_override: bool) -> str:
    if critical_override or overall_score < 40:
        return "CRITICAL"
    if overall_score < 60:
        return "HIGH_RISK"
    if overall_score < 80:
        return "NEEDS_ATTENTION"
    return "HEALTHY"


def _validated_counts(raw_counts: dict[str, Any], errors: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in RAW_COUNT_KEYS:
        value = _optional_int(raw_counts.get(key))
        if value is None:
            errors.append(f"raw_counts.{key}: required integer")
            counts[key] = 0
        elif value < 0:
            errors.append(f"raw_counts.{key}: must be non-negative")
            counts[key] = 0
        else:
            counts[key] = value
    if counts["repositories_with_branch_protection"] > counts["repositories_in_scope"]:
        errors.append("raw_counts.repositories_with_branch_protection: cannot exceed repositories_in_scope")
    if counts["repositories_with_required_reviews"] > counts["repositories_in_scope"]:
        errors.append("raw_counts.repositories_with_required_reviews: cannot exceed repositories_in_scope")
    if counts["unpinned_actions"] > counts["third_party_actions"]:
        errors.append("raw_counts.unpinned_actions: cannot exceed third_party_actions")
    return counts


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    return str(value).strip()


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    parsed = _optional_int(value)
    return parsed if parsed is not None else 0


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))

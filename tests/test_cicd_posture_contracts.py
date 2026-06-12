from __future__ import annotations

import json

from endor_agent_kit.cli import main
from endor_agent_kit.workflow_output_contracts.cicd_posture import (
    FORMULA_VERSION,
    compute_cicd_posture_scores,
    validate_cicd_posture_payload,
)


def _raw_counts() -> dict[str, int]:
    return {
        "repositories_in_scope": 4,
        "repositories_with_branch_protection": 3,
        "repositories_with_required_reviews": 2,
        "workflows_reviewed": 8,
        "third_party_actions": 10,
        "unpinned_actions": 2,
        "overbroad_permissions": 1,
        "risky_triggers": 2,
        "self_hosted_runners": 1,
        "update_automation_present": 3,
        "endor_critical_findings": 0,
        "endor_high_findings": 2,
        "endor_cicd_findings": 3,
        "endor_scpm_findings": 1,
        "endor_gha_findings": 1,
        "endor_supply_chain_findings": 1,
    }


def _payload() -> dict:
    raw_counts = _raw_counts()
    scores = compute_cicd_posture_scores(raw_counts)
    return {
        "posture_verdict": "NEEDS_ATTENTION",
        "summary": "Namespace posture needs attention due to workflow hardening and Endor findings.",
        "scope": {
            "namespace": "acme",
            "scope_mode": "namespace",
            "github_org": "acme",
            "repository_urls": [],
        },
        "raw_counts": raw_counts,
        "dimension_scores": scores["dimension_scores"],
        "score_validation": {
            "formula_version": FORMULA_VERSION,
            "dimension_weights": {
                key: 1
                for key in scores["dimension_scores"]
            },
            "overall_score": scores["overall_score"],
            "verdict_band": scores["verdict_band"],
            "recomputed": True,
        },
        "critical_overrides": [],
        "endor_findings": [],
        "github_evidence": [],
        "local_ci_evidence": [],
        "recommended_actions": [],
        "evidence_queries": [
            {
                "name": "cicd-posture-findings",
                "resource": "Finding",
                "source": "endorctl_api",
                "status": "succeeded",
                "query_template_id": "cicd-posture-findings",
                "filter_summary": "FINDING_CATEGORY_CICD",
                "field_mask_summary": "uuid,meta.name,spec",
                "result_count": 6,
                "reason": "Find posture findings by category.",
            }
        ],
        "data_gaps": [],
    }


def test_compute_cicd_posture_scores_uses_deterministic_formula():
    scores = compute_cicd_posture_scores(_raw_counts())

    assert scores == {
        "formula_version": FORMULA_VERSION,
        "dimension_scores": {
            "branch_protection": 63,
            "workflow_hardening": 55,
            "action_pinning": 80,
            "permissions": 80,
            "runner_security": 80,
            "endor_findings": 50,
        },
        "overall_score": 68,
        "verdict_band": "NEEDS_ATTENTION",
        "critical_override_required": False,
    }


def test_compute_cicd_posture_scores_rounds_half_up_at_boundaries():
    counts = _raw_counts()
    counts["third_party_actions"] = 8
    counts["unpinned_actions"] = 1

    scores = compute_cicd_posture_scores(counts)

    # 100 * 1 / 8 = 12.5 must round half-up to 13, not banker's-round to 12.
    assert scores["dimension_scores"]["action_pinning"] == 87


def test_validate_cicd_posture_payload_accepts_matching_scores():
    assert validate_cicd_posture_payload(_payload()) == []


def test_validate_cicd_posture_payload_rejects_score_mismatch():
    payload = _payload()
    payload["dimension_scores"]["action_pinning"] = 100

    errors = validate_cicd_posture_payload(payload)

    assert "dimension_scores.action_pinning: expected 80, got 100" in errors


def test_validate_cicd_posture_payload_requires_critical_override_rows():
    payload = _payload()
    payload["raw_counts"]["endor_critical_findings"] = 1
    scores = compute_cicd_posture_scores(payload["raw_counts"])
    payload["dimension_scores"] = scores["dimension_scores"]
    payload["score_validation"]["overall_score"] = scores["overall_score"]
    payload["score_validation"]["verdict_band"] = "CRITICAL"
    payload["posture_verdict"] = "CRITICAL"

    errors = validate_cicd_posture_payload(payload)

    assert (
        "critical_overrides: an endor_critical_finding override row is required when critical Endor findings are present"
        in errors
    )


def _critical_override_payload(override_type: str) -> dict:
    payload = _payload()
    payload["critical_overrides"] = [
        {
            "type": override_type,
            "evidence": "github_evidence[0]",
            "summary": "Documented non-Endor critical override.",
        }
    ]
    scores = compute_cicd_posture_scores(
        payload["raw_counts"],
        declared_override_types=(override_type,),
    )
    payload["dimension_scores"] = scores["dimension_scores"]
    payload["score_validation"]["overall_score"] = scores["overall_score"]
    payload["score_validation"]["verdict_band"] = scores["verdict_band"]
    payload["posture_verdict"] = scores["verdict_band"]
    return payload


def test_validate_cicd_posture_payload_accepts_runner_exposure_override():
    payload = _critical_override_payload("exposed_self_hosted_runner")

    assert payload["posture_verdict"] == "CRITICAL"
    assert validate_cicd_posture_payload(payload) == []


def test_validate_cicd_posture_payload_accepts_privileged_trigger_override():
    payload = _critical_override_payload("privileged_workflow_risky_trigger")

    assert payload["posture_verdict"] == "CRITICAL"
    assert validate_cicd_posture_payload(payload) == []


def test_validate_cicd_posture_payload_rejects_unknown_override_type():
    payload = _payload()
    payload["critical_overrides"] = [
        {"type": "vibes", "evidence": "github_evidence[0]"}
    ]

    errors = validate_cicd_posture_payload(payload)

    assert any(error.startswith("critical_overrides[0].type: must be one of") for error in errors)


def test_validate_cicd_posture_payload_rejects_override_without_evidence():
    payload = _payload()
    payload["critical_overrides"] = [{"type": "exposed_self_hosted_runner"}]

    errors = validate_cicd_posture_payload(payload)

    assert "critical_overrides[0].evidence: required text" in errors


def test_validate_cicd_posture_payload_requires_equal_dimension_weights():
    payload = _payload()
    payload["score_validation"]["dimension_weights"]["endor_findings"] = 2

    errors = validate_cicd_posture_payload(payload)

    assert (
        "score_validation.dimension_weights: must map each dimension to the equal weight 1"
        in errors
    )


def test_validate_cicd_posture_payload_rejects_update_automation_above_scope():
    payload = _payload()
    payload["raw_counts"]["update_automation_present"] = 9

    errors = validate_cicd_posture_payload(payload)

    assert "raw_counts.update_automation_present: cannot exceed repositories_in_scope" in errors


def test_validate_cicd_posture_output_cli_accepts_valid_payload(tmp_path, capsys):
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps(_payload()), encoding="utf-8")

    status = main(["validate-cicd-posture-output", str(payload), "--gate", "posture"])
    output = capsys.readouterr().out

    assert status == 0
    assert f"OK: {payload}" in output


def test_validate_cicd_posture_output_cli_rejects_verdict_mismatch(tmp_path, capsys):
    data = _payload()
    data["posture_verdict"] = "HEALTHY"
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps(data), encoding="utf-8")

    status = main(["validate-cicd-posture-output", str(payload), "--gate", "posture"])
    output = capsys.readouterr().out

    assert status == 1
    assert "ERROR: posture_verdict: expected NEEDS_ATTENTION, got HEALTHY" in output

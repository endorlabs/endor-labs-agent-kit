"""Unit tests for result shaping and the human-readable summary."""

from __future__ import annotations

from service.a2a.models import (
    AnalysisStatus,
    RecommendedAction,
    ScaFinding,
    Severity,
)
from service.a2a.result_formatter import build_analysis_result, human_summary
from service.endor_client.base import EndorSCAResult


def _finding(severity: Severity) -> ScaFinding:
    return ScaFinding(
        package="acme:widget",
        current_version="1.0.0",
        severity=severity,
        recommended_action=RecommendedAction.UPGRADE,
    )


def test_status_completed_and_counts():
    result = build_analysis_result(
        EndorSCAResult(
            namespace="acme",
            findings=[_finding(Severity.P0), _finding(Severity.P1), _finding(Severity.P1)],
            data_gaps=[],
        )
    )

    assert result.status is AnalysisStatus.COMPLETED
    assert result.findings_summary.p0_count == 1
    assert result.findings_summary.p1_count == 2


def test_status_data_gap_when_gaps_recorded():
    result = build_analysis_result(
        EndorSCAResult(namespace="acme", findings=[], data_gaps=["missing_uia"])
    )
    assert result.status is AnalysisStatus.DATA_GAP


def test_human_summary_zero_findings_names_namespace():
    result = build_analysis_result(
        EndorSCAResult(namespace="acme-ns", findings=[], data_gaps=[])
    )
    assert human_summary(result) == "No P0/P1 SCA findings for acme-ns."


def test_human_summary_reports_counts_and_read_only_stance():
    result = build_analysis_result(
        EndorSCAResult(
            namespace="acme-ns",
            findings=[_finding(Severity.P0), _finding(Severity.P1)],
            data_gaps=[],
        )
    )

    text = human_summary(result)

    assert "1 P0" in text and "1 P1" in text
    assert "acme-ns" in text
    assert "read-only analysis" in text and "no code changes" in text


def test_human_summary_appends_data_gap_note():
    result = build_analysis_result(
        EndorSCAResult(namespace="acme", findings=[], data_gaps=["a", "b"])
    )
    assert human_summary(result).endswith("Note: 2 data gap(s) recorded.")

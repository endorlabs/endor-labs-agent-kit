"""Shape an :class:`EndorSCAResult` into the §10 task-result contract."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import FindingsSummary, ScaAnalysisResult, Severity

if TYPE_CHECKING:
    from ..endor_client.base import EndorSCAResult


def build_analysis_result(result: "EndorSCAResult") -> ScaAnalysisResult:
    """Compute summary counts and pick the overall task status.

    Status follows the recipe convention: ``data_gap`` when evidence is
    missing but partial results are still returned; ``completed`` otherwise.
    """

    p0 = sum(1 for f in result.findings if f.severity is Severity.P0)
    p1 = sum(1 for f in result.findings if f.severity is Severity.P1)

    status = "data_gap" if result.data_gaps else "completed"

    return ScaAnalysisResult(
        status=status,
        namespace=result.namespace,
        findings_summary=FindingsSummary(p0_count=p0, p1_count=p1),
        findings=result.findings,
        data_gaps=result.data_gaps,
    )


def human_summary(result: ScaAnalysisResult) -> str:
    """A short natural-language summary to accompany the structured payload."""

    summary = result.findings_summary
    total = summary.p0_count + summary.p1_count
    if total == 0:
        base = f"No P0/P1 SCA findings for {result.namespace}."
    else:
        base = (
            f"Found {summary.p0_count} P0 and {summary.p1_count} P1 SCA "
            f"finding(s) for {result.namespace}. This is a read-only analysis; "
            f"no code changes were made."
        )
    if result.data_gaps:
        base += f" Note: {len(result.data_gaps)} data gap(s) recorded."
    return base

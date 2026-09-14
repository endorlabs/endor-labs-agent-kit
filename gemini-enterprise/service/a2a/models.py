"""Data models for the SCA Remediation analysis contract.

The task-result payload mirrors §10 of the design doc and is kept
output-compatible with the shape the CLI SCA Remediation recipe produces
where practical. v1 is read-only: findings + remediation guidance, no code
changes.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"


class AnalysisStatus(str, Enum):
    """Task status values from the §10 result contract.

    ``NEEDS_MORE_INFO`` is part of the contract but v1 never produces it: an
    unresolvable target is rejected up front as an ``AmbiguousTargetError``
    (§2), so there is no mid-task "ask the user" path yet.
    """

    COMPLETED = "completed"
    NEEDS_MORE_INFO = "needs_more_info"
    DATA_GAP = "data_gap"


class RecommendedAction(str, Enum):
    UPGRADE = "upgrade"
    PATCH = "patch"
    NO_FIX_AVAILABLE = "no_fix_available"
    MANUAL_REVIEW = "manual_review"


class BreakingChangeRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class ScaFinding(BaseModel):
    """One package-level remediation row (§10)."""

    package: str
    current_version: str
    vulnerability_ids: list[str] = Field(default_factory=list)
    severity: Severity
    recommended_action: RecommendedAction
    target_version: str | None = None
    breaking_change_risk: BreakingChangeRisk = BreakingChangeRisk.UNKNOWN
    patch_available: bool = False


class FindingsSummary(BaseModel):
    p0_count: int = 0
    p1_count: int = 0


class ScaAnalysisResult(BaseModel):
    """The structured task result returned to Gemini Enterprise (§10).

    ``status`` follows the recipe convention: return partial results with
    populated ``data_gaps`` rather than failing the whole task when some
    evidence is missing.
    """

    status: AnalysisStatus
    namespace: str
    findings_summary: FindingsSummary
    findings: list[ScaFinding] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    """Internal, validated intake derived from the natural-language task message.

    A2A skills are natural-language triggered, so the input shape lives in the
    task message rather than a rigid schema (§2). This is what the parser
    distills that message down to before the Endor client is called.
    """

    raw_text: str = ""
    repo_url: str | None = None
    repo_full_name: str | None = None
    ref: str | None = None
    namespace: str | None = None
    project_id: str | None = None
    severity_filter: list[Severity] = Field(default_factory=list)

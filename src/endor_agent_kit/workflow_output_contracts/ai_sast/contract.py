"""AI SAST workflow output contract Interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from . import _implementation
from .exception_gate import (
    EXCEPTION_GATE,
    lint_ai_sast_approval_comment,
    lint_ai_sast_exception_policy_comment,
    render_ai_sast_approval_comment,
    render_ai_sast_exception_policy_comment,
)
from .remediation_gate import (
    PR_GATE,
    REMEDIATION_GATE,
    lint_ai_sast_pr_body,
    render_ai_sast_pr_body,
)
from .triage_gate import TRIAGE_GATE


class AiSastGate(Protocol):
    """Gate-local validator used by the workflow-level contract."""

    name: str

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for this gate."""


AI_SAST_GATES: dict[str, AiSastGate] = {
    "triage": TRIAGE_GATE,
    "remediation": REMEDIATION_GATE,
    "pr": PR_GATE,
    "exception": EXCEPTION_GATE,
}


def load_json_payload(path: str | Path) -> dict[str, Any]:
    """Load a JSON object used by AI SAST contract commands."""

    return _implementation.load_json_payload(path)


def validate_ai_sast_gate_payload(
    payload: dict[str, Any],
    *,
    gate: str = "triage",
) -> list[str]:
    """Validate structured output through the requested AI SAST workflow gate."""

    return AI_SAST_GATES.get(gate, TRIAGE_GATE).validate(payload)


def normalize_ai_sast_branch(finding_uuid: str, finding_name: str = "") -> str:
    """Return a stable AI SAST remediation branch name."""

    return _implementation.normalize_ai_sast_branch(finding_uuid, finding_name)


__all__ = [
    "AI_SAST_GATES",
    "AiSastGate",
    "EXCEPTION_GATE",
    "PR_GATE",
    "REMEDIATION_GATE",
    "TRIAGE_GATE",
    "lint_ai_sast_approval_comment",
    "lint_ai_sast_exception_policy_comment",
    "lint_ai_sast_pr_body",
    "load_json_payload",
    "normalize_ai_sast_branch",
    "render_ai_sast_approval_comment",
    "render_ai_sast_exception_policy_comment",
    "render_ai_sast_pr_body",
    "validate_ai_sast_gate_payload",
]

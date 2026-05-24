"""SCA remediation workflow output contract Interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from . import _implementation
from .apply_gate import APPLY_GATE
from .pr_gate import PR_GATE, lint_sca_pr_body, render_sca_pr_body
from .selection_gate import SELECTION_PLAN_GATE
from .validation_gate import VALIDATION_GATE


class ScaGate(Protocol):
    """Gate-local validator used by the SCA workflow-level contract."""

    name: str

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for this gate."""


SCA_GATES: dict[str, ScaGate] = {
    "selection-plan": SELECTION_PLAN_GATE,
    "apply": APPLY_GATE,
    "validate": VALIDATION_GATE,
    "pr": PR_GATE,
}


def load_json_payload(path: str | Path) -> dict[str, Any]:
    """Load a JSON object used by SCA contract commands."""

    return _implementation.load_json_payload(path)


def validate_sca_gate_payload(
    payload: dict[str, Any],
    *,
    gate: str = "selection-plan",
) -> list[str]:
    """Validate structured output through the requested SCA workflow gate."""

    return SCA_GATES.get(gate, SELECTION_PLAN_GATE).validate(payload)


def normalize_sca_branch(package: str, target_version: str) -> str:
    """Return the stable SCA remediation branch name for a package upgrade."""

    return _implementation.normalize_sca_branch(package, target_version)


__all__ = [
    "APPLY_GATE",
    "PR_GATE",
    "SCA_GATES",
    "SELECTION_PLAN_GATE",
    "VALIDATION_GATE",
    "ScaGate",
    "lint_sca_pr_body",
    "load_json_payload",
    "normalize_sca_branch",
    "render_sca_pr_body",
    "validate_sca_gate_payload",
]

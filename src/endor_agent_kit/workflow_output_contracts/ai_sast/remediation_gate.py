"""AI SAST remediation and PR/MR gate contracts."""

from __future__ import annotations

from typing import Any

from . import _implementation


class AiSastRemediationGate:
    """Validate AI SAST remediation output and rendered PR/MR artifacts."""

    name = "remediation"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for this remediation-like gate."""

        if not isinstance(payload, dict):
            return ["payload: must be an object"]

        errors: list[str] = []
        _implementation._validate_project_resolution(payload, errors)
        _implementation._validate_verdicts(payload, self.name, errors)
        _implementation._validate_patches(payload, errors)
        _implementation._validate_change_requests(payload, errors)
        return errors

    def render_pr_body(self, payload: dict[str, Any]) -> str:
        """Render the reviewer-facing PR/MR body for this gate."""

        return _implementation.render_ai_sast_pr_body(payload)

    def lint_pr_body(self, body: str) -> list[str]:
        """Lint the reviewer-facing PR/MR body for this gate."""

        return _implementation.lint_ai_sast_pr_body(body)


class AiSastPrGate(AiSastRemediationGate):
    """Validate AI SAST PR/MR gate output."""

    name = "pr"


REMEDIATION_GATE = AiSastRemediationGate()
PR_GATE = AiSastPrGate()


def render_ai_sast_pr_body(payload: dict[str, Any]) -> str:
    """Render a reviewer-facing AI SAST remediation PR/MR body."""

    return REMEDIATION_GATE.render_pr_body(payload)


def lint_ai_sast_pr_body(body: str) -> list[str]:
    """Lint a reviewer-facing AI SAST remediation PR/MR body."""

    return REMEDIATION_GATE.lint_pr_body(body)

"""AI SAST exception-policy gate contract."""

from __future__ import annotations

from typing import Any

from . import _implementation


class AiSastExceptionGate:
    """Validate AI SAST exception output and rendered approval artifacts."""

    name = "exception"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for the exception-policy gate."""

        if not isinstance(payload, dict):
            return ["payload: must be an object"]

        errors: list[str] = []
        _implementation._validate_project_resolution(payload, errors)
        _implementation._validate_verdicts(payload, self.name, errors)
        _implementation._validate_approvals(payload, errors)
        _implementation._validate_exception_policies(payload, errors)
        return errors

    def render_approval_comment(self, payload: dict[str, Any]) -> str:
        """Render the standalone AppSec approval request comment."""

        return _implementation.render_ai_sast_approval_comment(payload)

    def lint_approval_comment(self, body: str) -> list[str]:
        """Lint the standalone AppSec approval request comment."""

        return _implementation.lint_ai_sast_approval_comment(body)

    def render_policy_comment(self, payload: dict[str, Any]) -> str:
        """Render the Endor exception policy decision comment."""

        return _implementation.render_ai_sast_exception_policy_comment(payload)

    def lint_policy_comment(self, body: str) -> list[str]:
        """Lint the Endor exception policy decision comment."""

        return _implementation.lint_ai_sast_exception_policy_comment(body)


EXCEPTION_GATE = AiSastExceptionGate()


def render_ai_sast_approval_comment(payload: dict[str, Any]) -> str:
    """Render the standalone AppSec approval request comment."""

    return EXCEPTION_GATE.render_approval_comment(payload)


def lint_ai_sast_approval_comment(body: str) -> list[str]:
    """Lint an AI SAST standalone exception approval request comment."""

    return EXCEPTION_GATE.lint_approval_comment(body)


def render_ai_sast_exception_policy_comment(payload: dict[str, Any]) -> str:
    """Render a reviewer-facing comment after an Endor exception policy decision."""

    return EXCEPTION_GATE.render_policy_comment(payload)


def lint_ai_sast_exception_policy_comment(body: str) -> list[str]:
    """Lint a reviewer-facing Endor exception policy decision comment."""

    return EXCEPTION_GATE.lint_policy_comment(body)

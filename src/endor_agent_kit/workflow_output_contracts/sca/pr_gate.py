"""SCA remediation PR/MR gate contract."""

from __future__ import annotations

from typing import Any

from . import _implementation


class ScaPrGate:
    """Validate SCA PR/MR output and rendered PR/MR artifacts."""

    name = "pr"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for this SCA gate."""

        return _implementation.validate_sca_gate_payload(payload, gate=self.name)

    def render_pr_body(self, payload: dict[str, Any]) -> str:
        """Render the AURI-style SCA remediation PR/MR body."""

        return _implementation.render_sca_pr_body(payload)

    def lint_pr_body(self, body: str) -> list[str]:
        """Lint the AURI-style SCA remediation PR/MR body."""

        return _implementation.lint_sca_pr_body(body)


PR_GATE = ScaPrGate()


def render_sca_pr_body(payload: dict[str, Any]) -> str:
    """Render the AURI-style SCA remediation PR body from normalized data."""

    return PR_GATE.render_pr_body(payload)


def lint_sca_pr_body(body: str) -> list[str]:
    """Lint an AURI-style SCA remediation PR body."""

    return PR_GATE.lint_pr_body(body)

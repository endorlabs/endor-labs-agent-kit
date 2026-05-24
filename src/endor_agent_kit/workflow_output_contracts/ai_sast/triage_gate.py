"""AI SAST triage gate contract."""

from __future__ import annotations

from typing import Any

from . import _implementation


class AiSastTriageGate:
    """Validate AI SAST triage output before workflow escalation."""

    name = "triage"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for the triage gate."""

        if not isinstance(payload, dict):
            return ["payload: must be an object"]

        errors: list[str] = []
        _implementation._validate_project_resolution(payload, errors)
        _implementation._validate_verdicts(payload, self.name, errors)
        return errors


TRIAGE_GATE = AiSastTriageGate()

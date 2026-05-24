"""SCA remediation Selection / Plan gate contract."""

from __future__ import annotations

from typing import Any

from . import _implementation


class ScaSelectionPlanGate:
    """Validate SCA remediation Selection / Plan output."""

    name = "selection-plan"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for this SCA gate."""

        return _implementation.validate_sca_gate_payload(payload, gate=self.name)


SELECTION_PLAN_GATE = ScaSelectionPlanGate()

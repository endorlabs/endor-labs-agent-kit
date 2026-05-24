"""SCA remediation apply gate contract."""

from __future__ import annotations

from typing import Any

from . import _implementation


class ScaApplyGate:
    """Validate SCA remediation apply-gate output."""

    name = "apply"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for this SCA gate."""

        return _implementation.validate_sca_gate_payload(payload, gate=self.name)


APPLY_GATE = ScaApplyGate()

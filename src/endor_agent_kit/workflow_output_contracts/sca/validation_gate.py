"""SCA remediation validation gate contract."""

from __future__ import annotations

from typing import Any

from . import _implementation


class ScaValidationGate:
    """Validate SCA remediation validation-gate output."""

    name = "validate"

    def validate(self, payload: dict[str, Any]) -> list[str]:
        """Validate structured output for this SCA gate."""

        return _implementation.validate_sca_gate_payload(payload, gate=self.name)


VALIDATION_GATE = ScaValidationGate()

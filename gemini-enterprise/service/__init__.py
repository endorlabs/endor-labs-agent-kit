"""Endor Labs SCA Remediation agent for Gemini Enterprise Marketplace.

v1 hosted A2A service. This package currently implements build-order step 3
from the design doc: the A2A task round-trip against mocked findings or the
real Endor REST client (``ENDOR_CLIENT=rest``). Auth (OAuth/DCR), procurement,
and infra-as-code are deferred to later build-order steps.
"""

__all__ = ["__version__"]

__version__ = "1.0.0"

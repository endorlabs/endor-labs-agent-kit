"""Endor Labs SCA Remediation agent for Gemini Enterprise Marketplace.

v1 hosted A2A service. This package currently implements build-order step 2
from the design doc: a local, mocked A2A task round-trip. Auth (OAuth/DCR),
procurement, the real Endor REST client, and infra-as-code are deferred to
later build-order steps.
"""

__all__ = ["__version__"]

__version__ = "1.0.0"

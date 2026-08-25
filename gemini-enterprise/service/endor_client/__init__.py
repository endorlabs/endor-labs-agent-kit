"""Endor SCA data access.

The design doc confirms there is no reusable in-repo Endor REST client, and v1
will talk to the Endor REST API directly (decision recorded in the module
README). This package defines the client seam:

* :class:`~service.endor_client.base.EndorSCAClient` -- the interface the task
  handler depends on.
* :class:`~service.endor_client.mock.MockEndorSCAClient` -- deterministic
  fixtures for build-order step 2 (mocked round-trip).

The real ``rest.py`` client (build-order step 3) implements the same interface
so the task handler does not change when it is swapped in.
"""

from .base import EndorSCAClient, EndorSCAResult
from .mock import MockEndorSCAClient
from .rest import RestEndorSCAClient

__all__ = [
    "EndorSCAClient",
    "EndorSCAResult",
    "MockEndorSCAClient",
    "RestEndorSCAClient",
]

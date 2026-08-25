"""Runtime configuration and Endor client selection.

v1 defaults to the mock client (build-order step 2). When the real REST client
lands (step 3), set ``ENDOR_CLIENT=rest`` and provide the §11 environment
variables; ``build_endor_client`` will construct it then.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .endor_client.base import EndorSCAClient
from .endor_client.mock import MockEndorSCAClient


@lru_cache(maxsize=1)
def build_endor_client() -> EndorSCAClient:
    kind = os.environ.get("ENDOR_CLIENT", "mock").strip().lower()
    if kind == "mock":
        return MockEndorSCAClient()
    if kind == "rest":
        # Direct Endor REST API client (build-order step 3). Credentials come
        # from env (deployed: Secret Manager) or ~/.endorctl/config.yaml (dev).
        from .endor_client.auth import TokenProvider, load_credentials
        from .endor_client.rest import RestEndorSCAClient

        credentials = load_credentials()
        return RestEndorSCAClient(
            token_provider=TokenProvider(credentials),
            default_namespace=credentials.namespace,
        )
    raise ValueError(f"Unknown ENDOR_CLIENT value: {kind!r} (expected 'mock' or 'rest')")

"""Runtime configuration and Endor client selection.

v1 defaults to the mock client. Set ``ENDOR_CLIENT=rest`` and provide the §11
environment variables to use the real Endor REST client (build-order step 3).
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
        # from env (deployed: Secret Manager); ~/.endorctl/config.yaml is an
        # explicit opt-in dev fallback (ENDOR_ALLOW_ENDORCTL_CONFIG=1).
        from .endor_client.auth import TokenProvider, load_credentials
        from .endor_client.rest import RestEndorSCAClient

        credentials = load_credentials()
        return RestEndorSCAClient(
            token_provider=TokenProvider(credentials),
            default_namespace=credentials.namespace,
        )
    raise ValueError(f"Unknown ENDOR_CLIENT value: {kind!r} (expected 'mock' or 'rest')")

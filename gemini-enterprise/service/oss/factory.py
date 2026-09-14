"""Build the OSS client and question router from environment (Option A).

* ``OSS_CLIENT`` = ``mock`` (default) | ``rest`` — where OSS data comes from.
* ``OSS_ROUTER`` = ``rule`` (default) | ``model`` — how questions are routed.

The ``rest`` client uses Endor's own service credential against the shared
``oss`` namespace (never a customer tenant). ``model`` is pending the
model-runtime decision.
"""

from __future__ import annotations

import os
from functools import lru_cache

from .client import OssIntelClient
from .mock import OssMockClient
from .router import ModelRouter, QuestionRouter, RuleBasedRouter


def build_oss_client() -> OssIntelClient:
    kind = os.environ.get("OSS_CLIENT", "mock").strip().lower()
    if kind == "mock":
        return OssMockClient()
    if kind == "rest":
        import httpx

        from ..endor_client.auth import TokenProvider, load_credentials
        from .client import OssRestClient

        creds = load_credentials()
        http = httpx.Client(base_url=creds.base_url, timeout=45.0)
        return OssRestClient(TokenProvider(creds, client=http))
    raise ValueError(f"Unknown OSS_CLIENT: {kind!r} (expected 'mock' or 'rest')")


@lru_cache(maxsize=1)
def build_oss_router() -> QuestionRouter:
    client = build_oss_client()
    kind = os.environ.get("OSS_ROUTER", "rule").strip().lower()
    if kind == "rule":
        return RuleBasedRouter(client)
    if kind == "model":
        from .model import build_model_backend

        return ModelRouter(client, build_model_backend())
    raise ValueError(f"Unknown OSS_ROUTER: {kind!r} (expected 'rule' or 'model')")

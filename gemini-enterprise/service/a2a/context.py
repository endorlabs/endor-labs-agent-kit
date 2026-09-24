"""Caller context — the single seam where auth becomes a tenant.

This is the injection point that makes the service multi-tenant-ready. Today it
derives the tenant namespace from ``ENDOR_NAMESPACE`` (the deployed single-tenant
/ dev case). When OAuth + DCR land (build-order step 4), the resolver validates
the inbound bearer token, maps the user to their Endor tenant/namespace, sets
``identity``, and enforces that any request-supplied namespace is within the
caller's authorized tenant. Nothing else in the request path changes — the
handler already sources the effective namespace from here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CallerContext:
    """Who is calling and which Endor tenant they are scoped to."""

    namespace: str | None = None
    identity: str | None = None


def resolve_caller_context(authorization: str | None = None) -> CallerContext:
    """Resolve the caller's tenant context from the request.

    v1: namespace from ``ENDOR_NAMESPACE`` env (unset in the mock/dev case, so
    the target then comes from the message itself). The ``authorization`` header
    is accepted but not yet used to scope the tenant.

    NEXT (step 4): validate the OAuth bearer token in ``authorization`` against
    the IdP, resolve the user's Endor namespace(s), populate ``identity``, and
    make this the authoritative tenant boundary.
    """

    namespace = os.environ.get("ENDOR_NAMESPACE") or None
    identity = None  # populated from the validated token in step 4.
    _ = authorization  # reserved: token validation plugs in here.
    return CallerContext(namespace=namespace, identity=identity)

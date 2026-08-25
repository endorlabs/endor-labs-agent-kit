"""Endor API authentication for the hosted service.

The service authenticates to the Endor REST API with an **API key + secret**
that it exchanges for a short-lived bearer token, then sends
``Authorization: Bearer <token>`` on each request.

Credential sources, in priority order:

1. Environment: ``ENDOR_API_CREDENTIALS_KEY`` / ``ENDOR_API_CREDENTIALS_SECRET``
   (this is how the deployed service gets them, from Secret Manager -- §8.4).
2. A local ``~/.endorctl/config.yaml`` (developer convenience only). Only the
   two credential keys and the namespace are read; the file is never echoed.

The secret is held only inside this module and sent to Endor's auth endpoint;
it is never logged, returned, or placed in task output.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "https://api.endorlabs.com"
# Fallback token lifetime when the server does not return a usable expiry.
_TOKEN_TTL_SECONDS = 50 * 60
# Refresh this many seconds before the server-reported expiry.
_EXPIRY_SAFETY_MARGIN = 5 * 60
_AUTH_EXCHANGE_PATH = "/v1/auth/api-key"


def _ttl_from_expiration(expiration: object) -> float:
    """Seconds until ``expiration`` (ISO8601), minus a safety margin.

    Falls back to a fixed TTL when the value is missing or unparseable.
    """

    if isinstance(expiration, str) and expiration:
        text = expiration.replace("Z", "+00:00")
        try:
            expires_at = datetime.fromisoformat(text)
        except ValueError:
            return _TOKEN_TTL_SECONDS
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
        usable = remaining - _EXPIRY_SAFETY_MARGIN
        if usable > 0:
            return usable
    return _TOKEN_TTL_SECONDS


@dataclass(frozen=True)
class EndorCredentials:
    key: str
    secret: str
    namespace: str | None = None
    base_url: str = DEFAULT_BASE_URL


def _read_endorctl_config_value(text: str, field: str) -> str | None:
    """Minimal flat-YAML read of a single top-level ``FIELD: value`` line.

    Avoids a YAML dependency and, more importantly, never surfaces the whole
    file -- it extracts exactly the requested key and nothing else.
    """

    prefix = f"{field}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            value = stripped[len(prefix):].strip()
            return value.strip('"').strip("'") or None
    return None


def load_credentials() -> EndorCredentials:
    """Load Endor credentials from env, falling back to the endorctl config."""

    key = os.environ.get("ENDOR_API_CREDENTIALS_KEY")
    secret = os.environ.get("ENDOR_API_CREDENTIALS_SECRET")
    namespace = os.environ.get("ENDOR_NAMESPACE")
    base_url = os.environ.get("ENDOR_API_BASE_URL", DEFAULT_BASE_URL)

    if not (key and secret):
        config_path = Path(
            os.environ.get("ENDORCTL_CONFIG", "~/.endorctl/config.yaml")
        ).expanduser()
        if config_path.is_file():
            text = config_path.read_text(encoding="utf-8")
            key = key or _read_endorctl_config_value(text, "ENDOR_API_CREDENTIALS_KEY")
            secret = secret or _read_endorctl_config_value(
                text, "ENDOR_API_CREDENTIALS_SECRET"
            )
            namespace = namespace or _read_endorctl_config_value(
                text, "ENDOR_NAMESPACE"
            )

    if not (key and secret):
        raise RuntimeError(
            "Endor API credentials not found. Set ENDOR_API_CREDENTIALS_KEY and "
            "ENDOR_API_CREDENTIALS_SECRET, or provide ~/.endorctl/config.yaml."
        )

    return EndorCredentials(
        key=key, secret=secret, namespace=namespace, base_url=base_url
    )


class TokenProvider:
    """Exchange an API key/secret for a bearer token and cache it in memory."""

    def __init__(
        self,
        credentials: EndorCredentials,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._credentials = credentials
        self._client = client or httpx.Client(
            base_url=credentials.base_url, timeout=30.0
        )
        self._token: str | None = None
        self._expires_at: float = 0.0

    def _exchange(self) -> tuple[str, float]:
        """Return ``(token, ttl_seconds)`` from the api-key exchange.

        The endpoint returns ``{"token": ..., "expirationTime": <ISO8601>}``.
        We honor ``expirationTime`` (minus a safety margin) when it parses,
        and otherwise fall back to a conservative fixed TTL.
        """

        response = self._client.post(
            _AUTH_EXCHANGE_PATH,
            json={
                "key": self._credentials.key,
                "secret": self._credentials.secret,
            },
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token")
        if not token:
            raise RuntimeError(
                "Endor auth exchange succeeded but returned no token field."
            )
        return token, _ttl_from_expiration(payload.get("expirationTime"))

    def token(self) -> str:
        now = time.monotonic()
        if self._token is None or now >= self._expires_at:
            self._token, ttl = self._exchange()
            self._expires_at = now + ttl
        return self._token

    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}

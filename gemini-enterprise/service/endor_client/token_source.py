"""How a REST client obtains its ``Authorization`` header.

Sources satisfy one shape (:class:`TokenSource`) — a ``base_url`` and an
``auth_header()`` — so clients work with any of them without changing:

* :class:`~service.endor_client.auth.TokenProvider` — **service credential**:
  the process authenticates with its own api-key (used by the OSS client and the
  SCA client).
* :class:`ForwardedBearer` — forward a caller-supplied bearer token verbatim.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenSource(Protocol):
    """A source of an Endor bearer ``Authorization`` header for one base URL."""

    @property
    def base_url(self) -> str: ...

    def auth_header(self) -> dict[str, str]: ...


class ForwardedBearer:
    """Forward a caller-supplied Endor bearer token verbatim."""

    def __init__(self, token: str, base_url: str) -> None:
        self._token = token
        self._base_url = base_url

    @property
    def base_url(self) -> str:
        return self._base_url

    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

"""Unit tests for credential loading and the bearer-token provider.

Everything runs offline: the endorctl config is a tmp file selected via
``ENDORCTL_CONFIG`` and the token exchange uses ``httpx.MockTransport``.
"""

from __future__ import annotations

import httpx
import pytest

from service.a2a.errors import AuthenticationError
from service.endor_client.auth import (
    _TOKEN_TTL_SECONDS,
    EndorCredentials,
    TokenProvider,
    _ttl_from_expiration,
    load_credentials,
)


@pytest.fixture(autouse=True)
def _isolated_credential_env(monkeypatch, tmp_path):
    """No ambient credentials or real endorctl config can leak into a test."""

    for var in (
        "ENDOR_API_CREDENTIALS_KEY",
        "ENDOR_API_CREDENTIALS_SECRET",
        "ENDOR_API_BASE_URL",
        "ENDOR_ALLOW_ENDORCTL_CONFIG",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ENDORCTL_CONFIG", str(tmp_path / "config.yaml"))
    yield


def _write_config(tmp_path, lines: list[str]) -> None:
    (tmp_path / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# -- load_credentials ----------------------------------------------------------


def test_env_credentials_used_directly(monkeypatch):
    monkeypatch.setenv("ENDOR_API_CREDENTIALS_KEY", "env-key")
    monkeypatch.setenv("ENDOR_API_CREDENTIALS_SECRET", "env-secret")
    monkeypatch.setenv("ENDOR_NAMESPACE", "acme")

    creds = load_credentials()

    assert creds.key == "env-key"
    assert creds.secret == "env-secret"
    assert creds.namespace == "acme"
    assert creds.base_url == "https://api.endorlabs.com"


def test_base_url_env_override(monkeypatch):
    monkeypatch.setenv("ENDOR_API_CREDENTIALS_KEY", "k")
    monkeypatch.setenv("ENDOR_API_CREDENTIALS_SECRET", "s")
    monkeypatch.setenv("ENDOR_API_BASE_URL", "https://api.test")

    assert load_credentials().base_url == "https://api.test"


def test_missing_credentials_raise_authentication_error():
    with pytest.raises(AuthenticationError, match="credentials not found"):
        load_credentials()


def test_endorctl_fallback_requires_explicit_opt_in(tmp_path):
    _write_config(
        tmp_path,
        ["ENDOR_API_CREDENTIALS_KEY: file-key", "ENDOR_API_CREDENTIALS_SECRET: file-secret"],
    )
    # The file is complete, but without the opt-in it must not be read.
    with pytest.raises(AuthenticationError, match="credentials not found"):
        load_credentials()


def test_endorctl_fallback_reads_key_secret_and_namespace(monkeypatch, tmp_path):
    monkeypatch.setenv("ENDOR_ALLOW_ENDORCTL_CONFIG", "1")
    _write_config(
        tmp_path,
        [
            'ENDOR_API_CREDENTIALS_KEY: "file-key"',
            "ENDOR_API_CREDENTIALS_SECRET: 'file-secret'",
            "ENDOR_NAMESPACE: file-ns",
        ],
    )

    creds = load_credentials()

    assert creds.key == "file-key"
    assert creds.secret == "file-secret"
    assert creds.namespace == "file-ns"


def test_env_values_fill_gaps_in_config(monkeypatch, tmp_path):
    monkeypatch.setenv("ENDOR_ALLOW_ENDORCTL_CONFIG", "1")
    monkeypatch.setenv("ENDOR_API_CREDENTIALS_KEY", "env-key")
    _write_config(tmp_path, ["ENDOR_API_CREDENTIALS_SECRET: file-secret"])

    creds = load_credentials()

    assert creds.key == "env-key"
    assert creds.secret == "file-secret"


def test_namespace_conflict_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("ENDOR_ALLOW_ENDORCTL_CONFIG", "1")
    monkeypatch.setenv("ENDOR_NAMESPACE", "env-ns")
    _write_config(
        tmp_path,
        [
            "ENDOR_API_CREDENTIALS_KEY: k",
            "ENDOR_API_CREDENTIALS_SECRET: s",
            "ENDOR_NAMESPACE: other-ns",
        ],
    )

    with pytest.raises(AuthenticationError, match="Namespace conflict"):
        load_credentials()


def test_matching_namespaces_do_not_conflict(monkeypatch, tmp_path):
    monkeypatch.setenv("ENDOR_ALLOW_ENDORCTL_CONFIG", "1")
    monkeypatch.setenv("ENDOR_NAMESPACE", "same-ns")
    _write_config(
        tmp_path,
        [
            "ENDOR_API_CREDENTIALS_KEY: k",
            "ENDOR_API_CREDENTIALS_SECRET: s",
            "ENDOR_NAMESPACE: same-ns",
        ],
    )

    assert load_credentials().namespace == "same-ns"


# -- _ttl_from_expiration ------------------------------------------------------


def test_ttl_honors_future_expiry_minus_margin():
    from datetime import datetime, timedelta, timezone

    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    ttl = _ttl_from_expiration(expiry.isoformat().replace("+00:00", "Z"))
    # 3600s remaining minus the 300s safety margin, allowing test runtime skew.
    assert 3200 < ttl <= 3300


def test_ttl_treats_naive_datetime_as_utc():
    from datetime import datetime, timedelta, timezone

    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None)
    ttl = _ttl_from_expiration(expiry.isoformat())
    assert 3200 < ttl <= 3300


@pytest.mark.parametrize("value", [None, "", "not-a-date", 12345])
def test_ttl_falls_back_on_unusable_values(value):
    assert _ttl_from_expiration(value) == _TOKEN_TTL_SECONDS


def test_ttl_falls_back_when_already_within_margin():
    from datetime import datetime, timedelta, timezone

    expiry = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert _ttl_from_expiration(expiry.isoformat()) == _TOKEN_TTL_SECONDS


# -- TokenProvider -------------------------------------------------------------


class _AuthHandler:
    def __init__(self, *, token: str | None = "tok-1"):
        self.posts = 0
        self.token = token

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/auth/api-key"
        self.posts += 1
        payload: dict = {"expirationTime": "2999-01-01T00:00:00Z"}
        if self.token is not None:
            payload["token"] = f"{self.token}-{self.posts}"
        return httpx.Response(200, json=payload)


def _provider(handler: _AuthHandler) -> TokenProvider:
    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.test"
    )
    creds = EndorCredentials(key="k", secret="s", base_url="https://api.test")
    return TokenProvider(creds, client=http)


def test_token_is_cached_across_calls():
    handler = _AuthHandler()
    provider = _provider(handler)

    first = provider.token()
    second = provider.token()

    assert first == second == "tok-1-1"
    assert handler.posts == 1


def test_expired_token_is_re_exchanged(monkeypatch):
    handler = _AuthHandler()
    provider = _provider(handler)
    provider.token()

    import service.endor_client.auth as auth_module

    real_monotonic = auth_module.time.monotonic
    # The mock expiry is centuries out, so jump far past any plausible TTL.
    monkeypatch.setattr(
        auth_module.time, "monotonic", lambda: real_monotonic() + 10**12
    )

    assert provider.token() == "tok-1-2"
    assert handler.posts == 2


def test_missing_token_field_raises_authentication_error():
    provider = _provider(_AuthHandler(token=None))
    with pytest.raises(AuthenticationError, match="no token field"):
        provider.token()


def test_rejected_credentials_at_exchange_raise_authentication_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthenticated"})

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.test"
    )
    provider = TokenProvider(
        EndorCredentials(key="bad", secret="bad", base_url="https://api.test"),
        client=http,
    )

    with pytest.raises(AuthenticationError, match="rejected the service credentials"):
        provider.token()


def test_namespace_conflict_message_does_not_leak_config_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ENDOR_ALLOW_ENDORCTL_CONFIG", "1")
    monkeypatch.setenv("ENDOR_NAMESPACE", "env-ns")
    _write_config(
        tmp_path,
        [
            "ENDOR_API_CREDENTIALS_KEY: k",
            "ENDOR_API_CREDENTIALS_SECRET: s",
            "ENDOR_NAMESPACE: other-ns",
        ],
    )

    with pytest.raises(AuthenticationError) as excinfo:
        load_credentials()

    # The error is serialized to remote callers; the server-local config path
    # (and the namespaces themselves) must not appear in it.
    assert str(tmp_path) not in str(excinfo.value)


def test_auth_header_and_base_url():
    provider = _provider(_AuthHandler())
    assert provider.auth_header() == {"Authorization": "Bearer tok-1-1"}
    assert provider.base_url == "https://api.test"

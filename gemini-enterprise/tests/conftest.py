import pytest


@pytest.fixture(autouse=True)
def _clean_endor_env(monkeypatch):
    """Keep tests hermetic: no ambient tenant/client selection leaks in."""

    monkeypatch.delenv("ENDOR_NAMESPACE", raising=False)
    monkeypatch.delenv("ENDOR_CLIENT", raising=False)

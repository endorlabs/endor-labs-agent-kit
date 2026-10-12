"""Phase 5 (Google/Veer #5): Endor brand theme on A2UI surfaces, env-tunable."""

from __future__ import annotations

import pytest

from service.oss.ui import _create_surface


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("OSS_BRAND_COLOR", raising=False)
    yield


def test_surface_carries_brand_theme_by_default():
    cs = _create_surface("x")
    assert cs["theme"]["primaryColor"].startswith("#")
    assert cs["surfaceId"] == "x"


def test_brand_color_is_env_tunable(monkeypatch):
    monkeypatch.setenv("OSS_BRAND_COLOR", "#123456")
    assert _create_surface("x")["theme"]["primaryColor"] == "#123456"


def test_empty_brand_color_disables_theme(monkeypatch):
    monkeypatch.setenv("OSS_BRAND_COLOR", "")
    assert "theme" not in _create_surface("x")

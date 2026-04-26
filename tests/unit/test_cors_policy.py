"""Unit tests for FastAPI CORS policy helpers."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from api.cors_policy import build_allowed_origins
from src.config.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    """Clear cached settings before and after each CORS policy test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.unit
def test_development_allowed_origins_include_loopback_frontend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Development CORS defaults allow the loopback host used by local Next.js."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    allowed_origins = build_allowed_origins()

    assert "http://127.0.0.1:3000" in allowed_origins

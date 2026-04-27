"""Unit tests for FastAPI CORS policy helpers."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from api.cors_policy import build_allowed_origins, validate_origin
from src.config.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    """Clear cached settings before and after each CORS policy test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


_LOOPBACK_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://127.0.0.1:7860",
    "https://127.0.0.1:3000",
    "https://127.0.0.1:7860",
]


@pytest.mark.unit
@pytest.mark.parametrize("origin", _LOOPBACK_ORIGINS)
def test_development_allowed_origins_include_loopback_frontend(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    """Development CORS defaults allow all loopback origins used by local dev servers."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    allowed_origins = build_allowed_origins()

    assert origin in allowed_origins


@pytest.mark.unit
@pytest.mark.parametrize("origin", _LOOPBACK_ORIGINS)
def test_production_allowed_origins_exclude_loopback_frontend(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    """Production CORS defaults do not allow loopback frontend origins."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    allowed_origins = build_allowed_origins()

    assert origin not in allowed_origins


@pytest.mark.unit
@pytest.mark.parametrize("origin", _LOOPBACK_ORIGINS)
def test_production_validate_origin_excludes_loopback_frontend(
    monkeypatch: pytest.MonkeyPatch, origin: str
) -> None:
    """Production origin validation rejects all loopback frontend origins by default."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)

    assert validate_origin(origin) is False

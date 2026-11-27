"""Unit tests for shared rate-limit store validation, Upstash fallback, and fail-closed guards."""

from __future__ import annotations

import logging

import pytest

from api.rate_limit import (
    DEFAULT_STORAGE_URI,
    build_limiter,
    classify_rate_limit_backend,
    resolve_rate_limit_storage_uri,
    validate_rate_limit_storage_uri,
)


def _clear_rate_limit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "RATE_LIMIT_STORAGE_URI",
        "UPSTASH_REDIS_URL",
        "REDIS_URL",
        "REQUIRE_SHARED_RATE_LIMIT_STORE",
        "ENV",
    ):
        monkeypatch.delenv(key, raising=False)


def test_resolve_rate_limit_storage_uri_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Precedence is RATE_LIMIT_STORAGE_URI > UPSTASH_REDIS_URL > REDIS_URL > memory://."""
    _clear_rate_limit_env(monkeypatch)
    assert resolve_rate_limit_storage_uri() == DEFAULT_STORAGE_URI

    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    assert resolve_rate_limit_storage_uri() == "redis://localhost:6379/0"
    assert classify_rate_limit_backend() == "redis"

    monkeypatch.setenv("UPSTASH_REDIS_URL", "rediss://default:secret@example.upstash.io:6379")
    assert resolve_rate_limit_storage_uri() == "rediss://default:secret@example.upstash.io:6379"
    assert classify_rate_limit_backend() == "redis"

    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memcached://cache.internal:11211")
    assert resolve_rate_limit_storage_uri() == "memcached://cache.internal:11211"
    assert classify_rate_limit_backend() == "memcached"


def test_validate_rate_limit_storage_uri_rejects_invalid_scheme() -> None:
    """Unsupported URI schemes raise ValueError without leaking credentials."""
    with pytest.raises(ValueError, match="Unsupported rate-limit storage scheme"):
        validate_rate_limit_storage_uri("http://user:supersecret@example.com")

    with pytest.raises(ValueError, match="must include a host or socket path"):
        validate_rate_limit_storage_uri("rediss://")


def test_require_shared_rate_limit_store_fails_closed_on_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQUIRE_SHARED_RATE_LIMIT_STORE=true raises RuntimeError when falling back to memory://."""
    _clear_rate_limit_env(monkeypatch)
    monkeypatch.setenv("REQUIRE_SHARED_RATE_LIMIT_STORE", "true")
    with pytest.raises(RuntimeError, match="REQUIRE_SHARED_RATE_LIMIT_STORE"):
        build_limiter()


def test_production_memory_fallback_emits_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Running with memory:// in ENV=production emits an operational warning."""
    _clear_rate_limit_env(monkeypatch)
    monkeypatch.setenv("ENV", "production")
    with caplog.at_level(logging.WARNING, logger="api.rate_limit"):
        limiter = build_limiter()
    assert limiter is not None
    assert any("in-memory storage in production" in rec.message for rec in caplog.records)

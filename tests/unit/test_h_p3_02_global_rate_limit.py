"""Unit tests for H-P3-02: global rate limits, proxy-aware IP extraction, and shared store."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.rate_limit import (
    build_limiter,
    get_client_ip,
    resolve_default_rate_limits,
    resolve_rate_limit_storage_uri,
)


def _fake_request(headers: dict[str, str] | None = None, client_host: str = "10.0.0.5") -> Request:
    """Create a minimal Request-like object for IP extraction testing."""
    lower_headers = {k.lower(): v for k, v in (headers or {}).items()}
    return cast(
        Request,
        SimpleNamespace(headers=lower_headers, client=SimpleNamespace(host=client_host)),
    )


def test_get_client_ip_ignores_proxy_headers_when_untrusted(monkeypatch: pytest.MonkeyPatch) -> None:
    """When TRUST_PROXY_HEADERS is false, X-Forwarded-For cannot spoof the rate-limit key."""
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("VERCEL_ENV", raising=False)

    req = _fake_request(headers={"X-Forwarded-For": "203.0.113.99"}, client_host="198.51.100.7")
    assert get_client_ip(req) == "198.51.100.7"


def test_get_client_ip_uses_trusted_proxy_headers_and_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When TRUST_PROXY_HEADERS is true, extracts validated client IP from proxy headers."""
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")

    req_xff = _fake_request(headers={"X-Forwarded-For": "198.51.100.1, 203.0.113.42"})
    assert get_client_ip(req_xff) == "203.0.113.42"

    req_vercel = _fake_request(headers={"X-Vercel-Forwarded-For": "203.0.113.77", "X-Forwarded-For": "198.51.100.1"})
    assert get_client_ip(req_vercel) == "203.0.113.77"

    req_invalid = _fake_request(headers={"X-Forwarded-For": "not-an-ip"}, client_host="198.51.100.8")
    assert get_client_ip(req_invalid) == "198.51.100.8"


def test_rate_limit_defaults_and_storage_uri_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Global defaults and shared storage URI are read from environment configuration."""
    monkeypatch.delenv("RATE_LIMIT_DEFAULT", raising=False)
    monkeypatch.delenv("RATE_LIMIT_STORAGE_URI", raising=False)
    assert resolve_default_rate_limits() == ["120/minute"]
    assert resolve_rate_limit_storage_uri() == "memory://"

    monkeypatch.setenv("RATE_LIMIT_DEFAULT", "60/minute;1000/hour")
    monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://shared-test")
    assert resolve_default_rate_limits() == ["60/minute", "1000/hour"]
    assert resolve_rate_limit_storage_uri() == "memory://shared-test"


def test_global_rate_limit_middleware_enforces_429(monkeypatch: pytest.MonkeyPatch) -> None:
    """Global SlowAPIMiddleware enforces default rate limits across undecorated endpoints."""
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    test_limiter = build_limiter(default_limits=["2/minute"], storage_uri="memory://")

    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    headers = {"X-Forwarded-For": "203.0.113.55"}
    assert client.get("/ping", headers=headers).status_code == 200
    assert client.get("/ping", headers=headers).status_code == 200
    assert client.get("/ping", headers=headers).status_code == 429
    # A distinct client IP is still permitted
    assert client.get("/ping", headers={"X-Forwarded-For": "203.0.113.56"}).status_code == 200

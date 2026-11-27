"""Unit tests for H-P3-01 production lockdown of OpenAPI, metrics, and SLO endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app_factory import _openapi_urls_for_environment
from api.routers.system import router as system_router


def _build_test_app() -> FastAPI:
    """Create a minimal FastAPI app mounting system routes with environment-aware OpenAPI URLs."""
    docs_url, redoc_url, openapi_url = _openapi_urls_for_environment()
    app = FastAPI(docs_url=docs_url, redoc_url=redoc_url, openapi_url=openapi_url)
    app.include_router(system_router)
    return app


def test_openapi_docs_disabled_in_production(monkeypatch) -> None:
    """Production hides /docs, /redoc, and /openapi.json unless explicitly enabled."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENABLE_OPENAPI_DOCS", raising=False)
    client = TestClient(_build_test_app())
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_openapi_docs_available_in_non_production(monkeypatch) -> None:
    """Non-production environments keep /docs and /openapi.json enabled."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ENABLE_OPENAPI_DOCS", raising=False)
    client = TestClient(_build_test_app())
    assert client.get("/openapi.json").status_code == 200


def test_observability_endpoints_require_auth_in_production(monkeypatch) -> None:
    """Production rejects unauthenticated and invalid-token requests to /api/metrics and /api/slo/status."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("OBSERVABILITY_BEARER_TOKEN", "prod-scrape-token-123")
    client = TestClient(_build_test_app())

    for path in ("/api/metrics", "/api/slo/status"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer wrong-token"}).status_code == 401
        resp = client.get(path, headers={"Authorization": "Bearer prod-scrape-token-123"})
        assert resp.status_code == 200


def test_observability_endpoints_open_in_non_production(monkeypatch) -> None:
    """Non-production environments keep /api/metrics and /api/slo/status accessible for local/CI checks."""
    monkeypatch.setenv("ENV", "test")
    monkeypatch.delenv("OBSERVABILITY_BEARER_TOKEN", raising=False)
    client = TestClient(_build_test_app())

    assert client.get("/api/metrics").status_code == 200
    assert client.get("/api/slo/status").status_code == 200

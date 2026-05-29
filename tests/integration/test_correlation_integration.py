"""Integration tests for correlation identifiers using a isolated minimal app."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.correlation import CorrelationMiddleware


@pytest.fixture
def isolated_app():
    """Create a minimal FastAPI app with only the CorrelationMiddleware."""
    app = FastAPI()
    app.add_middleware(CorrelationMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


def test_app_correlation_integration(isolated_app):
    """Test that the app correctly handles correlation headers."""
    client = TestClient(isolated_app)
    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Correlation-ID" in response.headers

    # IDs should be valid (generated as UUIDs)
    req_id = response.headers["X-Request-ID"]
    corr_id = response.headers["X-Correlation-ID"]

    assert len(req_id) > 0
    assert req_id == corr_id


def test_app_correlation_respects_headers(isolated_app):
    """Test that the app respects provided correlation headers."""
    client = TestClient(isolated_app)
    custom_req = "req-123"
    custom_corr = "corr-456"

    response = client.get(
        "/health",
        headers={
            "X-Request-ID": custom_req,
            "X-Correlation-ID": custom_corr,
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_req
    assert response.headers["X-Correlation-ID"] == custom_corr

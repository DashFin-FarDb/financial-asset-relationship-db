"""Integration tests for correlation identifiers in the main application."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


def test_app_correlation_integration():
    """Test that the main app correctly handles correlation headers."""
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert "X-Correlation-ID" in response.headers

    # IDs should be valid UUIDs (at least the generated ones)
    req_id = response.headers["X-Request-ID"]
    corr_id = response.headers["X-Correlation-ID"]

    assert len(req_id) > 0
    assert req_id == corr_id


def test_app_correlation_respects_headers():
    """Test that the main app respects provided correlation headers."""
    client = TestClient(app)
    custom_req = "req-123"
    custom_corr = "corr-456"

    response = client.get(
        "/api/health",
        headers={
            "X-Request-ID": custom_req,
            "X-Correlation-ID": custom_corr,
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_req
    assert response.headers["X-Correlation-ID"] == custom_corr

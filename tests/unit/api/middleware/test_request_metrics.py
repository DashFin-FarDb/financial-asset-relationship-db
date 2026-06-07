"""Unit tests for RequestMetricsMiddleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from api.middleware.request_metrics import RequestMetricsMiddleware


@pytest.mark.unit
def test_request_metrics_middleware_collects_metrics():
    """Test that RequestMetricsMiddleware collects requests and duration metrics."""
    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    @app.get("/items/{item_id}")
    async def get_item(item_id: str):
        """Mock route with path parameters."""
        return {"item_id": item_id}

    client = TestClient(app)

    # Get initial values or set them to 0 if not tracked yet
    initial_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/items/{item_id}", "status_group": "2xx"},
        )
        or 0.0
    )

    # Make request
    response = client.get("/items/AAPL")
    assert response.status_code == 200

    # Verify requests counter increased by 1
    new_count = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "route": "/items/{item_id}", "status_group": "2xx"},
    )
    assert new_count == initial_count + 1.0

    # Verify duration histogram observed a sample
    duration_count = REGISTRY.get_sample_value(
        "http_request_duration_seconds_count",
        {"method": "GET", "route": "/items/{item_id}", "status_group": "2xx"},
    )
    assert duration_count is not None
    assert duration_count >= 1.0


@pytest.mark.unit
def test_request_metrics_middleware_excludes_metrics_endpoint():
    """Test that RequestMetricsMiddleware bypasses the /api/metrics endpoint."""
    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    @app.get("/api/metrics")
    async def metrics_route():
        """Mock metrics endpoint."""
        return "ok"

    client = TestClient(app)

    # Get initial count
    initial_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/api/metrics", "status_group": "2xx"},
        )
        or 0.0
    )

    # Make request to /api/metrics
    response = client.get("/api/metrics")
    assert response.status_code == 200

    # Verify no metrics were incremented for the metrics route
    new_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/api/metrics", "status_group": "2xx"},
        )
        or 0.0
    )
    assert new_count == initial_count


@pytest.mark.unit
def test_request_metrics_middleware_excludes_metrics_endpoint_with_trailing_slash():
    """Test that RequestMetricsMiddleware bypasses the /api/metrics/ endpoint with a trailing slash."""
    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    @app.get("/api/metrics")
    async def metrics_route():
        """Mock metrics endpoint."""
        return "ok"

    client = TestClient(app)

    # Get initial count
    initial_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/api/metrics", "status_group": "2xx"},
        )
        or 0.0
    )

    # Make request to /api/metrics/
    response = client.get("/api/metrics/")
    assert response.status_code == 200

    # Verify no metrics were incremented for the metrics route
    new_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/api/metrics", "status_group": "2xx"},
        )
        or 0.0
    )
    assert new_count == initial_count


@pytest.mark.unit
def test_request_metrics_middleware_handles_error_status_groups():
    """Test that RequestMetricsMiddleware groups errors into correct status groups."""
    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    @app.get("/error")
    async def raise_error():
        """Mock route that raises an exception resulting in 500."""
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail="Server Error")

    client = TestClient(app)

    # Get initial count
    initial_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/error", "status_group": "5xx"},
        )
        or 0.0
    )

    response = client.get("/error")
    assert response.status_code == 500

    new_count = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "route": "/error", "status_group": "5xx"},
    )
    assert new_count == initial_count + 1.0


@pytest.mark.unit
def test_request_metrics_middleware_handles_unhandled_exceptions():
    """Test that RequestMetricsMiddleware records 5xx metrics for unhandled raw exceptions."""
    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    @app.get("/unhandled")
    async def raise_unhandled():
        """Mock route that raises a raw exception."""
        raise ValueError("Raw server error")

    client = TestClient(app, raise_server_exceptions=False)

    initial_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/unhandled", "status_group": "5xx"},
        )
        or 0.0
    )

    response = client.get("/unhandled")
    assert response.status_code == 500

    new_count = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "route": "/unhandled", "status_group": "5xx"},
    )
    assert new_count == initial_count + 1.0


@pytest.mark.unit
def test_request_metrics_middleware_falls_back_to_unknown_route():
    """Test that RequestMetricsMiddleware falls back to route="unknown" for non-existent endpoints."""
    app = FastAPI()
    app.add_middleware(RequestMetricsMiddleware)

    client = TestClient(app)

    # Get initial count
    initial_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "unknown", "status_group": "4xx"},
        )
        or 0.0
    )

    response = client.get("/non-existent-route")
    assert response.status_code == 404

    new_count = (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "unknown", "status_group": "4xx"},
        )
        or 0.0
    )
    assert new_count == initial_count + 1.0

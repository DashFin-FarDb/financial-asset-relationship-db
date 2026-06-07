"""Integration tests for request metrics collection."""

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from api.app_factory import create_app


@pytest.mark.integration
def test_metrics_integration_exposes_http_request_metrics():
    """Test that HTTP request metrics are exposed on the /api/metrics endpoint."""
    app = create_app()
    with TestClient(app) as client:
        # Clean registry state check or record initial
        initial_count = (
            REGISTRY.get_sample_value(
                "http_requests_total",
                {"method": "GET", "route": "/api/health", "status_group": "2xx"},
            )
            or 0.0
        )

        # Call a real endpoint to trigger metrics
        response = client.get("/api/health")
        assert response.status_code == 200

        # Query metrics endpoint
        metrics_response = client.get("/api/metrics")
        assert metrics_response.status_code == 200
        metrics_content = metrics_response.text

        # Verify metrics content format and values
        assert "http_requests_total" in metrics_content
        assert "http_request_duration_seconds" in metrics_content
        assert 'route="/api/health"' in metrics_content
        assert 'status_group="2xx"' in metrics_content
        assert 'method="GET"' in metrics_content

        # Double check sample values directly
        new_count = REGISTRY.get_sample_value(
            "http_requests_total",
            {"method": "GET", "route": "/api/health", "status_group": "2xx"},
        )
        assert new_count == pytest.approx(initial_count + 1.0)

"""Unit tests for resilient Prometheus/OpenMetrics /api/metrics endpoint.

Contract:
- Endpoint must never require JSON parsing
- Endpoint must never raise exceptions to caller
- Endpoint must always return a valid OpenMetrics payload
- Failures degrade into fallback metrics, not HTTP errors
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


def _assert_metrics_text_response(response) -> str:
    """Assert /api/metrics returns valid Prometheus/OpenMetrics response."""
    assert response.status_code == 200

    content_type = response.headers.get("content-type", "")
    assert (
        "text/plain" in content_type
        or "application/openmetrics-text" in content_type
        or "text/plain; version=0.0.4" in content_type
    )

    body = response.text
    assert "graph_rebuild_requests_total" in body
    assert "graph_assets_count" in body
    assert "graph_relationships_count" in body
    return body


@pytest.fixture
def client() -> TestClient:
    """Create an isolated TestClient for /api/metrics tests with automatic teardown."""
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.mark.unit
class TestMetricsEndpoint:
    """Resilient metrics endpoint contract tests."""

    def test_metrics_happy_path(self, client: TestClient) -> None:
        """Metrics endpoint returns a valid OpenMetrics payload."""
        body = _assert_metrics_text_response(client.get("/api/metrics"))
        assert "# HELP graph_rebuild_requests_total" in body
        assert "# TYPE graph_rebuild_requests_total counter" in body

    def test_metrics_degrades_when_generation_fails(self, client: TestClient) -> None:
        """Metrics generation failures return a degraded OpenMetrics payload, not an HTTP error."""
        with patch("api.routers.system.generate_latest", side_effect=Exception("metrics generation error")):
            body = _assert_metrics_text_response(client.get("/api/metrics"))
        assert "graph_rebuild_requests_total" in body

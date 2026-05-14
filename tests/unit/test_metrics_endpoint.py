"""Unit tests for Prometheus/OpenMetrics /api/metrics endpoint."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


def _assert_metrics_text_response(response) -> str:
    """Assert /api/metrics returns Prometheus/OpenMetrics plaintext."""
    assert response.status_code == 200

    content_type = response.headers.get("content-type", "")
    assert "text/plain" in content_type or "application/openmetrics-text" in content_type

    body = response.text

    # Core invariants: metrics must always exist
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
    """Tests for /api/metrics Prometheus/OpenMetrics endpoint."""

    def test_get_metrics(
        self,
        client,
    ):
        """Metrics endpoint returns valid OpenMetrics payload."""
        _assert_metrics_text_response(client.get("/api/metrics"))

    def test_metrics_exposes_help_and_type(
        self,
        client,
    ):
        """Metrics endpoint includes HELP and TYPE metadata."""
        body = _assert_metrics_text_response(client.get("/api/metrics"))

        assert "# HELP graph_rebuild_requests_total" in body
        assert "# TYPE graph_rebuild_requests_total counter" in body

    def test_metrics_handles_empty_graph(
        self,
        client,
    ):
        """Metrics endpoint remains stable without graph patching."""

        body = _assert_metrics_text_response(client.get("/api/metrics"))

        # Minimal structural validation for empty-state safety
        assert "graph_assets_count" in body
        assert "graph_relationships_count" in body

"""Unit tests for Prometheus/OpenMetrics /api/metrics endpoint.

This module validates:
- Correct OpenMetrics exposition
- Metric presence and metadata (HELP/TYPE)
- Resilience under empty graph state
"""

from unittest.mock import patch

import pytest

from src.logic.asset_graph import AssetRelationshipGraph


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


@pytest.mark.unit
class TestMetricsEndpoint:
    """Tests for /api/metrics Prometheus/OpenMetrics endpoint."""

    @patch("api.main.graph")
    def test_get_metrics(
        self,
        mock_graph_instance,
        client,
        mock_graph,
        apply_mock_graph,
    ):
        """Metrics endpoint returns valid OpenMetrics payload."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        _assert_metrics_text_response(client.get("/api/metrics"))

    @patch("api.main.graph")
    def test_metrics_exposes_help_and_type(
        self,
        mock_graph_instance,
        client,
        mock_graph,
        apply_mock_graph,
    ):
        """Metrics endpoint includes HELP and TYPE metadata."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        body = _assert_metrics_text_response(client.get("/api/metrics"))

        assert "# HELP graph_rebuild_requests_total" in body
        assert "# TYPE graph_rebuild_requests_total counter" in body

    @patch("api.main.graph")
    def test_metrics_handles_empty_graph(
        self,
        mock_graph_instance,
        client,
    ):
        """
        Metrics endpoint remains stable under empty graph state.

        This validates resilience of metric collectors when no assets
        or relationships exist.
        """
        empty_graph = AssetRelationshipGraph()

        mock_graph_instance.assets = empty_graph.assets
        mock_graph_instance.relationships = empty_graph.relationships
        mock_graph_instance.calculate_metrics = empty_graph.calculate_metrics

        body = _assert_metrics_text_response(client.get("/api/metrics"))

        # Minimal structural validation for empty-state safety
        assert "graph_assets_count" in body
        assert "graph_relationships_count" in body

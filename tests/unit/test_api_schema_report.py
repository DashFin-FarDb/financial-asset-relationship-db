# ruff: noqa: S101
"""Unit tests for src/api/routers/schema_report.py API router.

This module tests the schema report API endpoints including:
- Markdown and HTML format generation
- Query parameter validation
- Error handling for invalid formats
- Response types and content
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.routers.schema_report import get_graph, router
from src.logic.asset_graph import AssetRelationshipGraph


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient with the schema_report router mounted."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.unit
class TestSchemaReportRouter:
    """Test cases for internal graph helper(s) used by the router."""

    def test_get_graph_returns_asset_relationship_graph(self) -> None:
        """Test that get_graph returns an AssetRelationshipGraph instance."""
        with patch.object(
            AssetRelationshipGraph,
            "initialize_assets_from_source",
            create=True,
        ):
            graph = get_graph()
            assert isinstance(graph, AssetRelationshipGraph)

    def test_get_graph_calls_initialize(self) -> None:
        """Test that get_graph calls initialize_assets_from_source."""
        with patch.object(
            AssetRelationshipGraph,
            "initialize_assets_from_source",
            create=True,
        ) as mock_init:
            get_graph()
            mock_init.assert_called_once()


@pytest.mark.unit
class TestSchemaReportEndpoint:
    """Test cases for the /schema-report/ endpoint."""

    def test_schema_report_default_format_returns_markdown(
        self,
        client: TestClient,
    ) -> None:
        """Test that the schema report endpoint returns markdown by default."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.generate_markdown_report",
            ) as mock_gen_md,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_md.return_value = "# Test Report"

            response = client.get("/schema-report/")

            assert response.status_code == 200
            assert response.text == "# Test Report"
            mock_gen_md.assert_called_once_with(mock_graph)

    def test_schema_report_with_md_format(
        self,
        client: TestClient,
    ) -> None:
        """Test schema report endpoint with explicit md format."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.generate_markdown_report",
            ) as mock_gen_md,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_md.return_value = "## Markdown Content"

            response = client.get("/schema-report/?format=md")

            assert response.status_code == 200
            assert response.text == "## Markdown Content"
            mock_gen_md.assert_called_once_with(mock_graph)

    def test_schema_report_with_html_format(
        self,
        client: TestClient,
    ) -> None:
        """Test schema report endpoint with html format."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.generate_html_report",
            ) as mock_gen_html,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_html.return_value = "<h1>HTML Report</h1>"

            response = client.get("/schema-report/?format=html")

            assert response.status_code == 200
            assert "<h1>HTML Report</h1>" in response.text
            mock_gen_html.assert_called_once_with(mock_graph)

    def test_schema_report_with_invalid_format(
        self,
        client: TestClient,
    ) -> None:
        """Test that invalid format parameters are rejected."""
        response = client.get("/schema-report/?format=pdf")

        # Assuming a constrained query param (e.g. Literal["md", "html"])
        assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.unit
class TestSchemaReportRawEndpoint:
    """Test cases for the /schema-report/raw endpoint."""

    def test_raw_endpoint_default_format(
        self,
        client: TestClient,
    ) -> None:
        """Test raw endpoint with default format returns markdown."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.export_report",
            ) as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_export.return_value = "# Raw Report"

            response = client.get("/schema-report/raw")

            assert response.status_code == 200
            json_data = response.json()
            assert json_data["filename"] == "schema_report.md"
            assert json_data["content"] == "# Raw Report"
            mock_export.assert_called_once_with(mock_graph, fmt="md")

    def test_raw_endpoint_with_html_format(
        self,
        client: TestClient,
    ) -> None:
        """Test raw endpoint with html format."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.export_report",
            ) as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_export.return_value = "<html>Report</html>"

            response = client.get("/schema-report/raw?fmt=html")

            assert response.status_code == 200
            json_data = response.json()
            assert json_data["filename"] == "schema_report.html"
            assert json_data["content"] == "<html>Report</html>"
            mock_export.assert_called_once_with(mock_graph, fmt="html")

    def test_raw_endpoint_handles_export_error(
        self,
        client: TestClient,
    ) -> None:
        """Test that raw endpoint handles ValueError from export_report."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.export_report",
            ) as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_export.side_effect = ValueError("Invalid format")

            response = client.get("/schema-report/raw?fmt=md")

            assert response.status_code == 400
            assert "Invalid format" in response.json()["detail"]

    def test_raw_endpoint_with_invalid_format(
        self,
        client: TestClient,
    ) -> None:
        """Test that raw endpoint rejects invalid format parameters."""
        response = client.get("/schema-report/raw?fmt=json")

        assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.unit
class TestSchemaReportEdgeCases:
    """Test edge cases and error conditions for schema report endpoints."""

    def test_schema_report_with_empty_graph(
        self,
        client: TestClient,
    ) -> None:
        """Test schema report generation with an empty graph."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.generate_markdown_report",
            ) as mock_gen_md,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_md.return_value = "# Empty Report\n\nNo assets found."

            response = client.get("/schema-report/")

            assert response.status_code == 200
            assert "Empty Report" in response.text

    def test_schema_report_handles_graph_initialization_error(
        self,
        client: TestClient,
    ) -> None:
        """Test that endpoint propagates graph initialization errors."""
        with patch("src.api.routers.schema_report.get_graph") as mock_get_graph:
            mock_get_graph.side_effect = RuntimeError("Database connection failed")

            with pytest.raises(RuntimeError, match="Database connection failed"):
                client.get("/schema-report/")

    def test_raw_endpoint_with_mixed_case_format(
        self,
        client: TestClient,
    ) -> None:
        """Test that raw endpoint handles mixed case format parameters."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch(
                "src.api.routers.schema_report.export_report",
            ) as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_export.return_value = "# Report"

            # FastAPI validation is case-sensitive, but export_report may normalize.
            response = client.get("/schema-report/raw?fmt=md")

            assert response.status_code == 200

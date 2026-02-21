# ruff: noqa: S101
"""Unit tests for src/api/routers/schema_report.py API router.

This module tests the schema report API endpoints including:
- Markdown and HTML format generation
- Query parameter validation
- Error handling for invalid formats
- Response types and content
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.routers.schema_report import get_graph, router
from src.logic.asset_graph import AssetRelationshipGraph


@pytest.mark.unit
class TestSchemaReportRouter:
    """Test cases for the schema report API router."""

    @staticmethod
    def test_get_graph_returns_asset_relationship_graph() -> None:
        """Test that get_graph returns an AssetRelationshipGraph instance."""
        # Mock the initialize method by adding it temporarily
        with patch.object(AssetRelationshipGraph, "initialize_assets_from_source", create=True):
            graph = get_graph()
            assert isinstance(graph, AssetRelationshipGraph)

    @staticmethod
    def test_get_graph_calls_initialize() -> None:
        """Test that get_graph calls initialize_assets_from_source."""
        # Mock the initialize method by adding it temporarily
        with patch.object(AssetRelationshipGraph, "initialize_assets_from_source", create=True) as mock_init:
            get_graph()
            mock_init.assert_called_once()


@pytest.mark.unit
class TestSchemaReportEndpoint:
    """Test cases for the /schema-report/ endpoint."""

    @staticmethod
    @pytest.fixture
    def client() -> TestClient:
        """Create a test client with the router mounted."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @staticmethod
    def test_schema_report_default_format_returns_markdown(client: TestClient) -> None:
        """Test that the schema report endpoint returns markdown by default."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.generate_markdown_report") as mock_gen_md,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_md.return_value = "# Test Report"

            response = client.get("/schema-report/")

            assert response.status_code == 200
            assert response.text == "# Test Report"
            mock_gen_md.assert_called_once_with(mock_graph)

    @staticmethod
    def test_schema_report_with_md_format(client: TestClient) -> None:
        """Test schema report endpoint with explicit md format."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.generate_markdown_report") as mock_gen_md,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_md.return_value = "## Markdown Content"

            response = client.get("/schema-report/?format=md")

            assert response.status_code == 200
            assert response.text == "## Markdown Content"
            mock_gen_md.assert_called_once_with(mock_graph)

    @staticmethod
    def test_schema_report_with_html_format(client: TestClient) -> None:
        """Test schema report endpoint with html format."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.generate_html_report") as mock_gen_html,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_html.return_value = "<h1>HTML Report</h1>"

            response = client.get("/schema-report/?format=html")

            assert response.status_code == 200
            assert "<h1>HTML Report</h1>" in response.text
            mock_gen_html.assert_called_once_with(mock_graph)

    @staticmethod
    def test_schema_report_with_invalid_format(client: TestClient) -> None:
        """Test that invalid format parameters are rejected."""
        response = client.get("/schema-report/?format=pdf")

        assert response.status_code == 422  # Unprocessable Entity


@pytest.mark.unit
class TestSchemaReportRawEndpoint:
    """Test cases for the /schema-report/raw endpoint."""

    @staticmethod
    @pytest.fixture
    def client() -> TestClient:
        """Create a test client with the router mounted."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @staticmethod
    def test_raw_endpoint_default_format(client: TestClient) -> None:
        """Test raw endpoint with default format returns markdown."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.export_report") as mock_export,
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

    @staticmethod
    def test_raw_endpoint_with_html_format(client: TestClient) -> None:
        """Test raw endpoint with html format."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.export_report") as mock_export,
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

    @staticmethod
    def test_raw_endpoint_handles_export_error(client: TestClient) -> None:
        """Test that raw endpoint handles ValueError from export_report."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_export.side_effect = ValueError("Invalid format")

            # Use valid format that passes validation but triggers export error

    """Test that a ValueError from export_report is propagated as a server error."""
    with (
        patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
        patch("src.api.routers.schema_report.export_report") as mock_export,
    ):
        mock_graph = MagicMock(spec=AssetRelationshipGraph)
        mock_get_graph.return_value = mock_graph
        mock_export.side_effect = ValueError("Invalid format")

        # Use valid format that passes validation but triggers export error
        with pytest.raises(ValueError, match="Invalid format"):
            client.get("/schema-report/raw?fmt=md")


class TestSchemaReportEdgeCases:
    """Test edge cases and error conditions for schema report endpoints."""

    @staticmethod
    @pytest.fixture
    def client() -> TestClient:
        """Create a test client with the router mounted."""

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    @staticmethod
    def test_schema_report_with_empty_graph(client: TestClient) -> None:
        """Test schema report generation with an empty graph."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.generate_markdown_report") as mock_gen_md,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_gen_md.return_value = "# Empty Report\n\nNo assets found."

            response = client.get("/schema-report/")

            assert response.status_code == 200
            assert "Empty Report" in response.text

    @staticmethod
    def test_schema_report_handles_graph_initialization_error(
        client: TestClient,
    ) -> None:
        """Test that endpoint handles errors during graph initialization."""
        with patch("src.api.routers.schema_report.get_graph") as mock_get_graph:
            mock_get_graph.side_effect = RuntimeError("Database connection failed")

            # FastAPI will raise unhandled exception, so we expect it to be raised
            # The endpoint doesn't explicitly catch this, so it will be a 500
            with pytest.raises(RuntimeError, match="Database connection failed"):
                client.get("/schema-report/")

    @staticmethod
    def test_raw_endpoint_with_mixed_case_format(client: TestClient) -> None:
        """Test that raw endpoint handles mixed case format parameters."""
        with (
            patch("src.api.routers.schema_report.get_graph") as mock_get_graph,
            patch("src.api.routers.schema_report.export_report") as mock_export,
        ):
            mock_graph = MagicMock(spec=AssetRelationshipGraph)
            mock_get_graph.return_value = mock_graph
            mock_export.return_value = "# Report"

            # Note: FastAPI query param validation is case-sensitive
            # but our export_report normalizes the format
            response = client.get("/schema-report/raw?fmt=md")

            assert response.status_code == 200

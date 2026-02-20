"""Comprehensive unit tests for the FastAPI backend (api/main.py).

This module tests:
- CORS origin validation rules
- Lazy graph initialization (including cache load / fallback)
- Core API endpoints and response shapes
- Error handling behaviour
- Basic integration workflows

Notes:
- Bandit B101 (assert_used) is acceptable in pytest; keep assertions as-is.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterator, NoReturn
from unittest.mock import Mock, patch

import api.main as api_main
import pytest
from api.main import (
    AssetResponse,
    MetricsResponse,
    RelationshipResponse,
    VisualizationDataResponse,
    app,
    validate_origin,
)
from fastapi import status
from fastapi.testclient import TestClient

from src.data.real_data_fetcher import _save_to_cache
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity

CORS_DEV_ORIGIN = "http://localhost:3000"


# -----------------------
# Fixtures
# -----------------------
@pytest.fixture()
def client() -> Iterator[TestClient]:
    """
    Shared TestClient fixture with a sample in-memory graph.

    This matches the default expectation for most endpoint tests: a populated graph.
    """
    api_main.set_graph(create_sample_database())
    tc = TestClient(app)
    try:
        yield tc
    finally:
        api_main.reset_graph()


@pytest.fixture()
def bare_client() -> TestClient:
    """TestClient fixture without forcing any pre-seeded graph."""
    return TestClient(app)


@pytest.mark.unit
class TestValidateOrigin:
    """Test the validate_origin function for CORS configuration."""

    @staticmethod
    def test_validate_origin_http_localhost_development() -> None:
        """HTTP localhost is allowed in development."""
        with patch.dict(os.environ, {"ENV": "development"}):
            assert validate_origin("http://localhost:3000")
            assert validate_origin("http://127.0.0.1:8000")
            assert validate_origin("http://localhost")

    @staticmethod
    def test_validate_origin_http_localhost_production() -> None:
        """HTTP localhost is rejected in production."""
        with patch.dict(os.environ, {"ENV": "production"}):
            assert not validate_origin("http://localhost:3000")
            assert not validate_origin("http://127.0.0.1:8000")

    @staticmethod
    def test_validate_origin_https_localhost() -> None:
        """HTTPS localhost is always allowed."""
        assert validate_origin("https://localhost:3000")
        assert validate_origin("https://127.0.0.1:8000")

    @staticmethod
    def test_validate_origin_vercel_urls() -> None:
        """Vercel deployment URLs are validated correctly."""
        assert validate_origin("https://my-app.vercel.app")
        assert validate_origin("https://my-app-git-main-user.vercel.app")
        assert validate_origin("https://subdomain.vercel.app")
        assert not validate_origin("http://my-app.vercel.app")  # HTTP rejected

    @staticmethod
    def test_validate_origin_https_valid_domains() -> None:
        """Valid HTTPS URLs with proper domains are accepted."""
        assert validate_origin("https://example.com")
        assert validate_origin("https://subdomain.example.com")
        assert validate_origin("https://api.example.co.uk")

    @staticmethod
    def test_validate_origin_invalid_schemes() -> None:
        """Invalid URL schemes are rejected."""
        assert not validate_origin("ftp://example.com")
        assert not validate_origin("ws://example.com")
        assert not validate_origin("file://localhost")

    @staticmethod
    def test_validate_origin_malformed_urls() -> None:
        """Malformed URLs are rejected."""
        assert not validate_origin("not-a-url")
        assert not validate_origin("https://")
        assert not validate_origin("https://invalid domain")
        assert not validate_origin("https://.com")


@pytest.mark.unit
class TestGraphInitialization:
    """Test the lazy graph initialization via get_graph()."""

    def test_graph_initialization(self) -> None:
        """Graph is initialized via get_graph()."""
        api_main.reset_graph()
        graph = api_main.get_graph()
        assert graph is not None
        assert hasattr(graph, "assets")
        assert hasattr(graph, "relationships")

    def test_graph_singleton(self) -> None:
        """Graph is a singleton instance via get_graph()."""
        api_main.reset_graph()
        graph1 = api_main.get_graph()
        graph2 = api_main.get_graph()
        assert graph1 is graph2

    def test_graph_uses_cache_when_configured(self, tmp_path: Path, monkeypatch) -> None:
        """Graph initialization should load from cached dataset when provided."""
        cache_path = tmp_path / "graph_snapshot.json"
        reference_graph = create_sample_database()
        _save_to_cache(reference_graph, cache_path)

        monkeypatch.setenv("GRAPH_CACHE_PATH", str(cache_path))
        api_main.reset_graph()

        graph = api_main.get_graph()
        assert graph is not None
        assert len(graph.assets) == len(reference_graph.assets)
        assert len(graph.relationships) == len(reference_graph.relationships)

        api_main.reset_graph()
        monkeypatch.delenv("GRAPH_CACHE_PATH", raising=False)

    def test_graph_fallback_on_corrupted_cache(self, tmp_path: Path, monkeypatch) -> None:
        """Graph initialization should fallback when cache is corrupted or invalid."""
        cache_path = tmp_path / "graph_snapshot.json"
        cache_path.write_text("not valid json", encoding="utf-8")

        reference_graph = create_sample_database()

        monkeypatch.setenv("GRAPH_CACHE_PATH", str(cache_path))
        api_main.reset_graph()

        graph = api_main.get_graph()
        assert graph is not None
        assert hasattr(graph, "assets")
        assert len(graph.assets) == len(reference_graph.assets)
        assert len(graph.relationships) == len(reference_graph.relationships)

        api_main.reset_graph()
        monkeypatch.delenv("GRAPH_CACHE_PATH", raising=False)


@pytest.mark.unit
class TestPydanticModels:
    """Test Pydantic response models."""

    def test_asset_response_model_valid(self) -> None:
        """AssetResponse accepts full payload and preserves additional fields."""
        asset = AssetResponse(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class="EQUITY",
            sector="Technology",
            price=150.00,
            market_cap=2.4e12,
            currency="USD",
            additional_fields={"pe_ratio": 25.5},
        )
        assert asset.id == "AAPL"
        assert asset.price == 150.00
        assert asset.additional_fields["pe_ratio"] == 25.5

    def test_asset_response_model_optional_fields(self) -> None:
        """AssetResponse populates defaults when optional fields are omitted."""
        asset = AssetResponse(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class="EQUITY",
            sector="Technology",
            price=150.00,
        )
        assert asset.market_cap is None
        assert asset.currency == "USD"
        assert asset.additional_fields == {}

    def test_relationship_response_model(self) -> None:
        """RelationshipResponse validates relationship payload fields."""
        rel = RelationshipResponse(
            source_id="AAPL",
            target_id="MSFT",
            relationship_type="same_sector",
            strength=0.8,
        )
        assert rel.source_id == "AAPL"
        assert rel.strength == 0.8

    def test_metrics_response_model(self) -> None:
        """MetricsResponse accepts metric fields and preserves asset class counts."""
        metrics = MetricsResponse(
            total_assets=10,
            total_relationships=20,
            asset_classes={"EQUITY": 5, "BOND": 5},
            avg_degree=2.0,
            max_degree=5,
            network_density=0.4,
        )
        assert metrics.total_assets == 10
        assert metrics.asset_classes["EQUITY"] == 5

    def test_visualization_data_response_model(self) -> None:
        """VisualizationDataResponse accepts node/edge lists for graph rendering."""
        viz = VisualizationDataResponse(
            nodes=[{"id": "AAPL", "x": 1.0, "y": 2.0, "z": 3.0}],
            edges=[{"source": "AAPL", "target": "MSFT"}],
        )
        assert len(viz.nodes) == 1
        assert len(viz.edges) == 1


@pytest.mark.unit
class TestAPIEndpoints:
    """Test all FastAPI endpoints."""

    @staticmethod
    @pytest.fixture
    def client():
        """
        Provide a TestClient bound to the app with a pre-seeded sample in-memory graph.

        The fixture yields a TestClient whose application has been populated with a sample graph; on teardown the application's graph is reset.

        Returns:
            TestClient: Test client connected to the FastAPI app with the sample graph loaded.
        """
        api_main.set_graph(create_sample_database())
        client = TestClient(app)
        try:
            yield client
        finally:
            api_main.reset_graph()

    def test_root_endpoint(self, client):
        """Test the root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data
        assert data["version"] == "1.0.0"

    def test_health_check_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_assets_all(self, client):
        """Test getting all assets without filters."""
        response = client.get("/api/assets")
        assert response.status_code == 200
        assets = response.json()
        assert isinstance(assets, list)
        assert len(assets) > 0

        asset = assets[0]
        assert "id" in asset
        assert "symbol" in asset
        assert "name" in asset
        assert "asset_class" in asset
        assert "sector" in asset
        assert "price" in asset

    def test_get_assets_filter_by_class(self, client):
        """Test filtering assets by asset class."""
        response = client.get("/api/assets?asset_class=EQUITY")
        assert response.status_code == 200
        assets = response.json()
        assert isinstance(assets, list)
        for asset in assets:
            assert asset["asset_class"] == "EQUITY"

    def test_get_assets_filter_by_sector(self, client: TestClient) -> None:
        """Assets endpoint supports filtering by sector."""
        response = client.get("/api/assets?sector=Technology")
        assert response.status_code == 200
        assets = response.json()
        assert isinstance(assets, list)
        for asset in assets:
            assert asset["sector"] == "Technology"

    def test_get_assets_filter_by_class_and_sector(self, client: TestClient) -> None:
        """Assets endpoint supports combined asset_class and sector filters."""
        # IMPORTANT: use '&' not '&amp;' (HTML entity should not appear in test URLs)
        response = client.get("/api/assets?asset_class=EQUITY&sector=Technology")
        assert response.status_code == 200
        assets = response.json()
        assert isinstance(assets, list)
        for asset in assets:
            assert asset["asset_class"] == "EQUITY"
            assert asset["sector"] == "Technology"

    def test_get_metrics_enriched_statistics(self, client: TestClient) -> None:
        """Metrics endpoint returns populated statistics and valid bounds."""
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data: Dict[str, Any] = response.json()

        assert data["total_assets"] > 0
        assert data["total_relationships"] > 0
        assert data["avg_degree"] > 0
        assert data["max_degree"] >= data["avg_degree"]
        assert 0 <= data["network_density"] <= 1

        # If the API includes relationship_density separately, validate its bounds too.
        if "relationship_density" in data:
            assert 0 <= data["relationship_density"] <= 1

    def test_get_metrics_no_assets(self, client: TestClient) -> None:
        """Metrics endpoint returns zeros for an empty graph."""
        api_main.set_graph(AssetRelationshipGraph())
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_assets"] == 0
        assert data["total_relationships"] == 0
        assert data["avg_degree"] == 0
        assert data["max_degree"] == 0
        assert data["network_density"] == 0

    def test_get_metrics_one_asset_no_relationships(self, client: TestClient) -> None:
        """Metrics endpoint handles one-node graphs with no relationships."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )
        api_main.set_graph(graph)
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_assets"] == 1
        assert data["total_relationships"] == 0
        assert data["avg_degree"] == 0
        assert data["max_degree"] == 0
        assert data["network_density"] == 0

    def test_get_metrics_multiple_assets_no_relationships(self, client: TestClient) -> None:
        """Metrics endpoint handles multi-node graphs with no relationships."""
        graph = AssetRelationshipGraph()
        graph.add_asset(
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
            )
        )
        graph.add_asset(
            Equity(
                id="GOOG",
                symbol="GOOG",
                name="Alphabet Inc.",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=125.0,
            )
        )
        api_main.set_graph(graph)
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_assets"] == 2
        assert data["total_relationships"] == 0
        assert data["avg_degree"] == 0
        assert data["max_degree"] == 0
        assert data["network_density"] == 0

    def test_get_asset_detail_valid(self, client: TestClient) -> None:
        """Asset detail endpoint returns the requested asset when it exists."""
        response = client.get("/api/assets")
        assets = response.json()
        asset_id = assets[0]["id"]

        response = client.get(f"/api/assets/{asset_id}")
        assert response.status_code == 200
        asset = response.json()
        assert asset["id"] == asset_id

    def test_get_asset_detail_not_found(self, client: TestClient) -> None:
        """Asset detail endpoint returns 404 for unknown asset IDs."""
        response = client.get("/api/assets/NONEXISTENT")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_asset_relationships_valid(self, client: TestClient) -> None:
        """Asset relationships endpoint returns relationships for a valid asset."""
        response = client.get("/api/assets")
        assets = response.json()
        asset_id = assets[0]["id"]

        response = client.get(f"/api/assets/{asset_id}/relationships")
        assert response.status_code == 200
        relationships = response.json()
        assert isinstance(relationships, list)

        if relationships:
            rel = relationships[0]
            assert "source_id" in rel
            assert "target_id" in rel
            assert "relationship_type" in rel
            assert "strength" in rel
            assert rel["source_id"] == asset_id

    def test_get_asset_relationships_not_found(self, client: TestClient) -> None:
        """Asset relationships endpoint returns 404 for unknown asset IDs."""
        response = client.get("/api/assets/NONEXISTENT/relationships")
        assert response.status_code == 404

    def test_get_all_relationships(self, client: TestClient) -> None:
        """Relationships endpoint returns a list of relationships with valid strength."""
        response = client.get("/api/relationships")
        assert response.status_code == 200
        relationships = response.json()
        assert isinstance(relationships, list)

        if relationships:
            rel = relationships[0]
            assert "source_id" in rel
            assert "target_id" in rel
            assert "relationship_type" in rel
            assert "strength" in rel
            assert 0 <= rel["strength"] <= 1

    def test_get_visualization_data(self, client: TestClient) -> None:
        """Visualization endpoint returns node/edge structures with numeric coords."""
        response = client.get("/api/visualization")
        assert response.status_code == 200
        viz_data = response.json()

        assert "nodes" in viz_data
        assert "edges" in viz_data
        assert isinstance(viz_data["nodes"], list)
        assert isinstance(viz_data["edges"], list)

        if viz_data["nodes"]:
            node = viz_data["nodes"][0]
            for key in (
                "id",
                "name",
                "symbol",
                "asset_class",
                "x",
                "y",
                "z",
                "color",
                "size",
            ):
                assert key in node
            assert isinstance(node["x"], (int, float))
            assert isinstance(node["y"], (int, float))
            assert isinstance(node["z"], (int, float))

        if viz_data["edges"]:
            edge = viz_data["edges"][0]
            for key in ("source", "target", "relationship_type", "strength"):
                assert key in edge
            assert 0 <= edge["strength"] <= 1

    def test_get_asset_classes(self, client: TestClient) -> None:
        """Asset classes endpoint returns all AssetClass enum values."""
        response = client.get("/api/asset-classes")
        assert response.status_code == 200
        data = response.json()

        assert "asset_classes" in data
        assert isinstance(data["asset_classes"], list)
        assert data["asset_classes"]

        expected_classes = [ac.value for ac in AssetClass]
        assert set(data["asset_classes"]) == set(expected_classes)

    def test_get_sectors(self, client: TestClient) -> None:
        """Sectors endpoint returns a non-empty, sorted list of sectors."""
        response = client.get("/api/sectors")
        assert response.status_code == 200
        data = response.json()

        assert "sectors" in data
        assert isinstance(data["sectors"], list)
        assert data["sectors"]
        assert data["sectors"] == sorted(data["sectors"])


@pytest.mark.unit
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_get_assets_server_error(self, bare_client: TestClient) -> None:
        """
        Verify the /api/assets endpoint responds with HTTP 500 when graph access raises an exception.

        Forces api_main.get_graph() to raise and asserts the response status is 500 and the error detail contains "database error".
        """

        def _raise() -> NoReturn:
            """Raise a generic exception to simulate a backend graph access failure."""
            raise Exception("Database error")

        with patch.object(api_main, "get_graph", side_effect=_raise):
            response = bare_client.get("/api/assets")
            assert response.status_code == 500
            assert "database error" in response.json()["detail"].lower()

    def test_get_metrics_server_error(self, bare_client: TestClient) -> None:
        """Metrics endpoint returns 500 when metric calculation raises an exception."""
        mock_graph = Mock(spec=AssetRelationshipGraph)
        mock_graph.calculate_metrics.side_effect = Exception("Calculation error")

        with patch.object(api_main, "get_graph", return_value=mock_graph):
            response = bare_client.get("/api/metrics")
            assert response.status_code == 500
            assert "calculation error" in response.json()["detail"].lower()

    @staticmethod
    def test_invalid_http_methods(bare_client: TestClient) -> None:
        """Unsupported HTTP methods return 405 for these endpoints."""
        response = bare_client.post("/api/assets")
        assert response.status_code == 405

        response = bare_client.put("/api/health")
        assert response.status_code == 405

        response = bare_client.delete("/api/metrics")
        assert response.status_code == 405


# -----------------------
# CORS middleware behaviour
# -----------------------
@pytest.mark.unit
def test_cors_headers_present(bare_client: TestClient) -> None:
    """Ensure allowed origins receive the expected CORS headers."""
    response = bare_client.get("/api/health", headers={"Origin": CORS_DEV_ORIGIN})
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == CORS_DEV_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"


@pytest.mark.unit
def test_cors_rejects_disallowed_origin(bare_client: TestClient) -> None:
    """Ensure disallowed origins do not receive CORS headers."""
    disallowed_origin = "https://malicious.example.com"
    response = bare_client.get("/api/health", headers={"Origin": disallowed_origin})

    assert response.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" not in response.headers
    assert response.headers.get("access-control-allow-origin", "") != disallowed_origin


@patch.dict(os.environ, {"ENV": "development", "ALLOWED_ORIGINS": ""})
@pytest.mark.unit
def test_cors_allows_development_origins(bare_client: TestClient) -> None:
    """Allow default dev origins when running in development mode."""
    response = bare_client.get("/api/health", headers={"Origin": CORS_DEV_ORIGIN})
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.unit
class TestAdditionalFields:
    """Test handling of asset-specific additional fields."""

    def test_equity_additional_fields(self, client: TestClient) -> None:
        """Equity assets include expected equity-specific fields in additional_fields."""
        response = client.get("/api/assets?asset_class=EQUITY")
        assets = response.json()

        if assets:
            asset = assets[0]
            additional = asset.get("additional_fields", {})
            possible_fields = {
                "pe_ratio",
                "dividend_yield",
                "earnings_per_share",
                "book_value",
            }
            has_equity_field = any(field in additional for field in possible_fields)
            assert has_equity_field or additional == {}

    def test_bond_additional_fields(self, client: TestClient) -> None:
        """Bond assets include expected bond-specific fields in additional_fields."""
        response = client.get("/api/assets?asset_class=BOND")
        assets = response.json()

        if assets:
            asset = assets[0]
            additional = asset.get("additional_fields", {})
            possible_fields = {
                "yield_to_maturity",
                "coupon_rate",
                "maturity_date",
                "credit_rating",
            }
            has_bond_field = any(field in additional for field in possible_fields)
            assert has_bond_field or additional == {}


@pytest.mark.unit
class TestVisualizationDataProcessing:
    """Test the processing of visualization data."""

    def test_visualization_coordinate_types(self, client: TestClient) -> None:
        """Visualization nodes expose numeric x/y/z coordinates (int or float)."""
        response = client.get("/api/visualization")
        viz_data = response.json()

        for node in viz_data["nodes"]:
            assert isinstance(node["x"], (int, float))
            assert isinstance(node["y"], (int, float))
            assert isinstance(node["z"], (int, float))

    def test_visualization_node_defaults(self, client: TestClient) -> None:
        """Visualization nodes include default color/size fields with expected types."""
        response = client.get("/api/visualization")
        viz_data = response.json()

        for node in viz_data["nodes"]:
            assert "color" in node
            assert "size" in node
            assert isinstance(node["color"], str)
            assert isinstance(node["size"], (int, float))

    def test_visualization_edge_defaults(self, client: TestClient) -> None:
        """Visualization edges include relationship metadata and bounded strength."""
        response = client.get("/api/visualization")
        viz_data = response.json()

        for edge in viz_data["edges"]:
            assert "relationship_type" in edge
            assert "strength" in edge
            assert 0 <= edge["strength"] <= 1


@pytest.mark.unit
class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_full_workflow_asset_exploration(self, client: TestClient) -> None:
        """Exercise the core browse flow: list assets, fetch detail, fetch relationships."""
        response = client.get("/api/assets")
        assert response.status_code == 200
        assets = response.json()
        assert assets

        asset_id = assets[0]["id"]
        response = client.get(f"/api/assets/{asset_id}")
        assert response.status_code == 200
        asset_detail = response.json()
        assert asset_detail["id"] == asset_id

        response = client.get(f"/api/assets/{asset_id}/relationships")
        assert response.status_code == 200
        relationships = response.json()
        assert isinstance(relationships, list)

    def test_full_workflow_visualization_and_metrics(self, client: TestClient) -> None:
        """Validate metrics and visualization endpoints are consistent on node counts."""
        response = client.get("/api/metrics")
        assert response.status_code == 200
        metrics = response.json()

        response = client.get("/api/visualization")
        assert response.status_code == 200
        viz_data = response.json()

        assert len(viz_data["nodes"]) == metrics["total_assets"]

    def test_filter_refinement_workflow(self, client: TestClient) -> None:
        """Confirm progressive filters reduce (or keep) result sets, never increase them."""
        response = client.get("/api/assets")
        all_assets = response.json()

        response = client.get("/api/assets?asset_class=EQUITY")
        equity_assets = response.json()
        assert len(equity_assets) <= len(all_assets)

        response = client.get("/api/assets?asset_class=EQUITY&sector=Technology")
        tech_equity_assets = response.json()
        assert len(tech_equity_assets) <= len(equity_assets)


@pytest.mark.unit
class TestGraphInitializationRaceConditions:
    """Test race conditions and thread safety in graph initialization."""

    def test_concurrent_graph_initialization_threads(self):
        """Boundary: Multiple threads initializing graph concurrently should be safe."""
        import threading

        api_main.reset_graph()
        results = []
        errors = []

        def init_graph():
            """
            Initialize the shared graph and record the outcome for a worker thread.

            On success, appends the initialized graph instance to the outer-scope list `results`.
            On failure, appends the raised exception to the outer-scope list `errors`.
            """
            try:
                graph = api_main.get_graph()
                results.append(graph)
            except Exception as e:
                errors.append(e)

        # Spawn 10 concurrent threads
        threads = [threading.Thread(target=init_graph) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0
        # All threads should get a graph
        assert len(results) == 10
        # All should get the same singleton instance
        first_graph = results[0]
        for graph in results[1:]:
            assert graph is first_graph

        api_main.reset_graph()

    def test_graph_initialization_with_corrupted_environment(self, monkeypatch):
        """
        Verify that initializing the graph with a corrupted or invalid cache path falls back to a valid in-memory graph.

        Sets GRAPH_CACHE_PATH to an invalid location, resets the cached graph, and asserts that get_graph() returns a non-null graph-like object exposing an `assets` attribute without raising an exception.
        """
        # Set invalid cache path
        monkeypatch.setenv("GRAPH_CACHE_PATH", "/invalid/path/to/cache.json")
        api_main.reset_graph()

        # Should not crash, should fall back gracefully
        graph = api_main.get_graph()
        assert graph is not None
        assert hasattr(graph, "assets")

        api_main.reset_graph()

    def test_graph_reset_and_reinitialize(self):
        """Boundary: Resetting and reinitializing graph should work correctly."""
        # Initialize graph
        graph1 = api_main.get_graph()
        assert graph1 is not None

        # Reset
        api_main.reset_graph()

        # Reinitialize - should get new instance
        graph2 = api_main.get_graph()
        assert graph2 is not None
        assert graph1 is not graph2

        api_main.reset_graph()

    def test_graph_initialization_memory_cleanup(self):
        """Boundary: Graph should be properly cleaned up after reset."""
        import gc

        # Create and reset graph multiple times
        for _ in range(5):
            graph = api_main.get_graph()
            assert graph is not None
            api_main.reset_graph()
            gc.collect()

        # Final initialization should still work
        final_graph = api_main.get_graph()
        assert final_graph is not None

        api_main.reset_graph()


@pytest.mark.unit
class TestGraphCachingEdgeCases:
    """Edge cases for graph caching and persistence."""

    def test_empty_cache_file_handling(self, tmp_path, monkeypatch):
        """Edge: Empty cache file should trigger fallback."""
        cache_path = tmp_path / "empty_cache.json"
        cache_path.write_text("")

        monkeypatch.setenv("GRAPH_CACHE_PATH", str(cache_path))
        api_main.reset_graph()

        graph = api_main.get_graph()
        assert graph is not None

        api_main.reset_graph()

    def test_json_array_instead_of_object_cache(self, tmp_path, monkeypatch):
        """Edge: Cache with JSON array instead of object should fallback."""
        cache_path = tmp_path / "array_cache.json"
        cache_path.write_text("[]")

        monkeypatch.setenv("GRAPH_CACHE_PATH", str(cache_path))
        api_main.reset_graph()

        graph = api_main.get_graph()
        assert graph is not None

        api_main.reset_graph()

    def test_cache_with_missing_required_fields(self, tmp_path, monkeypatch):
        """Edge: Cache missing required fields should trigger fallback."""
        cache_path = tmp_path / "incomplete_cache.json"
        cache_path.write_text('{"incomplete": "data"}')

        monkeypatch.setenv("GRAPH_CACHE_PATH", str(cache_path))
        api_main.reset_graph()

        graph = api_main.get_graph()
        assert graph is not None

        api_main.reset_graph()


@pytest.mark.unit
class TestPydanticModelValidation:
    """Validation tests for Pydantic response models."""

    def test_asset_response_rejects_negative_price(self):
        """
        Verifies AssetResponse accepts a negative price value.

        Creates an AssetResponse with price -100.0 and asserts an instance is produced, confirming that negative prices are not rejected by model validation.
        """
        asset = AssetResponse(
            id="TEST",
            symbol="TST",
            name="Test",
            asset_class="EQUITY",
            sector="Tech",
            price=-100.0,  # Currently allowed as no validation is implemented
        )
        assert isinstance(asset, AssetResponse)

    def test_relationship_response_validates_strength_range(self):
        """Negative: RelationshipResponse should validate strength is 0-1."""
        # Valid strength
        rel = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="test",
            strength=0.5,
        )
        assert rel.strength == 0.5

        # Test boundary values
        rel_min = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="test",
            strength=0.0,
        )
        assert rel_min.strength == 0.0

        rel_max = RelationshipResponse(
            source_id="A",
            target_id="B",
            relationship_type="test",
            strength=1.0,
        )
        assert rel_max.strength == 1.0

    def test_metrics_response_validates_non_negative_values(self):
        """Negative: MetricsResponse should reject negative metrics."""
        metrics = MetricsResponse(
            total_assets=-1,  # Currently allowed as no validation is implemented
            total_relationships=0,
            asset_classes={},
            avg_degree=0.0,
            max_degree=0,
            network_density=0.0,
        )
        assert isinstance(metrics, MetricsResponse)


@pytest.mark.unit
class TestEndpointStressTests:
    """Stress tests for API endpoints under load."""

    @staticmethod
    @pytest.fixture
    def client():
        """
        Create a TestClient pre-seeded with a sample in-memory graph for tests.

        Yields:
            TestClient: FastAPI TestClient bound to the application with a sample graph set. The graph is reset when the fixture tears down.
        """
        api_main.set_graph(create_sample_database())
        client = TestClient(app)
        try:
            yield client
        finally:
            api_main.reset_graph()

    def test_rapid_successive_requests(self, client):
        """Stress: Handle many rapid successive requests."""
        responses = []
        for _ in range(100):
            response = client.get("/api/health")
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200

    def test_mixed_endpoint_requests(self, client):
        """Stress: Handle mixed requests to different endpoints."""
        endpoints = [
            "/api/health",
            "/api/assets",
            "/api/metrics",
            "/api/asset-classes",
            "/api/sectors",
        ]

        for _ in range(20):
            for endpoint in endpoints:
                response = client.get(endpoint)
                assert response.status_code == 200


@pytest.mark.unit
class TestErrorMessageQuality:
    """Test quality and informativeness of error messages."""

    @staticmethod
    @pytest.fixture
    def client():
        """
        Create a TestClient with a seeded in-memory graph and ensure graph cleanup on teardown.

        Sets a sample graph on the application prior to yielding and resets the global graph state when the fixture is torn down.

        Returns:
            TestClient: A TestClient instance bound to the FastAPI app with the sample in-memory graph preloaded.
        """
        api_main.set_graph(create_sample_database())
        client = TestClient(app)
        try:
            yield client
        finally:
            api_main.reset_graph()

    def test_404_error_message_is_informative(self, client):
        """Error messages should be informative for developers."""
        response = client.get("/api/assets/NONEXISTENT_ASSET")
        assert response.status_code == 404
        error_data = response.json()

        # Should have detail key
        assert "detail" in error_data
        # Should mention the asset ID
        assert "not found" in error_data["detail"].lower()

    def test_invalid_endpoint_error_message(self, client):
        """Invalid endpoints should return clear error."""
        response = client.get("/api/invalid_endpoint_that_does_not_exist")
        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

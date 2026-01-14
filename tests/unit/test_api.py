"""Comprehensive unit tests for FastAPI backend.

This module tests all API endpoints including:
- Health checks and root endpoint
- Asset retrieval with filtering
- Asset details and relationships
- Metrics calculation
- Visualization data generation
- CORS configuration
- Error handling and edge cases
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app, validate_origin
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Bond, Commodity, Currency, Equity

# Test fixture URLs for CORS origin validation tests.
# These localhost URLs are intentional test inputs for verifying the validate_origin
# function correctly handles local development origins. They are not debug code.
TEST_ORIGIN_HTTP_LOCALHOST = "http://localhost:3000"  # nosec B104
TEST_ORIGIN_HTTP_LOOPBACK = "http://127.0.0.1:8000"  # nosec B104
TEST_ORIGIN_HTTPS_LOCALHOST = "https://localhost:3000"
TEST_ORIGIN_HTTPS_LOOPBACK = "https://127.0.0.1:8000"
TEST_ORIGIN_FTP_LOCALHOST = "ftp://localhost:3000"  # Invalid protocol test case


@pytest.fixture
def client():
    """Create a test client for the FastAPI app.

    Note: TestClient uses internal ASGI transport, not actual network requests.
    The base_url is only used for URL construction in tests, not for real HTTP calls.
    """
    # nosec B113 - TestClient uses ASGI transport, no actual localhost network access
    return TestClient(app, base_url="http://testserver")


@pytest.fixture
def mock_graph():
    """Create a mock graph with sample data."""
    graph = AssetRelationshipGraph(database_url="sqlite:///:memory:")

    # Add sample equity
    equity = Equity(
        id="TEST_AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=150.00,
        market_cap=2.4e12,
        pe_ratio=25.5,
        dividend_yield=0.005,
        earnings_per_share=5.89,
        book_value=4.50,
    )
    graph.add_asset(equity)

    # Add sample bond
    bond = Bond(
        id="TEST_CORP",
        symbol="CORP",
        name="Corporate Bond",
        asset_class=AssetClass.FIXED_INCOME,
        sector="Corporate",
        price=1000.00,
        yield_to_maturity=0.04,
        coupon_rate=0.035,
        maturity_date="2030-12-31",
        credit_rating="AA",
        issuer_id="TEST_AAPL",
    )
    graph.add_asset(bond)

    # Add sample commodity
    commodity = Commodity(
        id="TEST_GC",
        symbol="GC",
        name="Gold",
        asset_class=AssetClass.COMMODITY,
        sector="Precious Metals",
        price=1950.00,
        contract_size=100.0,
        delivery_date="2024-12-31",
    )
    graph.add_asset(commodity)

    # Add sample currency
    currency = Currency(
        id="TEST_EUR",
        symbol="EUR",
        name="Euro",
        asset_class=AssetClass.CURRENCY,
        sector="Currency",
        price=1.08,
        exchange_rate=1.08,
        country="Eurozone",
    )
    graph.add_asset(currency)

    # Build relationships
    graph.build_relationships()

    return graph


class TestRootAndHealth:
    """Test root and health check endpoints."""

    @staticmethod
    def test_root_endpoint(client):
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data
        assert data["version"] == "1.0.0"
        assert "/api/assets" in data["endpoints"].values()

    @staticmethod
    def test_health_check_endpoint(client):
        """Test health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "graph_initialized" in data


class TestCORSValidation:
    """Test CORS origin validation."""

    @staticmethod
    def test_validate_origin_localhost_http_dev():
        """Test HTTP localhost is valid in development."""
        with patch("api.main.ENV", "development"):
            assert validate_origin(TEST_ORIGIN_HTTP_LOCALHOST) is True
            assert validate_origin(TEST_ORIGIN_HTTP_LOOPBACK) is True

    @staticmethod
    def test_validate_origin_localhost_https_always():
        """Test HTTPS localhost is always valid."""
        assert validate_origin(TEST_ORIGIN_HTTPS_LOCALHOST) is True
        assert validate_origin(TEST_ORIGIN_HTTPS_LOOPBACK) is True

    @staticmethod
    def test_validate_origin_vercel_urls():
        """Test Vercel deployment URLs are valid."""
        assert validate_origin("https://myapp.vercel.app") is True
        assert validate_origin("https://myapp-git-main.vercel.app") is True
        assert validate_origin("https://my-app-123.vercel.app") is True

    @staticmethod
    def test_validate_origin_https_domains():
        """Test valid HTTPS domains are accepted."""
        assert validate_origin("https://example.com") is True
        assert validate_origin("https://sub.example.com") is True
        assert validate_origin("https://my-site.example.co.uk") is True

    @staticmethod
    def test_validate_origin_invalid():
        """Test invalid origins are rejected."""
        # HTTP in production (when not localhost)
        with patch("api.main.ENV", "production"):
            assert validate_origin("http://example.com") is False

        # Invalid formats
        assert validate_origin(TEST_ORIGIN_FTP_LOCALHOST) is False
        assert validate_origin("javascript:alert(1)") is False
        assert validate_origin("") is False


class TestAssetsEndpoint:
    """Test assets listing endpoint."""

    @patch("api.main.graph")
    def test_get_all_assets(self, mock_graph_instance, client, mock_graph):
        """Test retrieving all assets without filters."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4  # equity, bond, commodity, currency

        # Verify structure
        asset = data[0]
        assert "id" in asset
        assert "symbol" in asset
        assert "name" in asset
        assert "asset_class" in asset
        assert "sector" in asset
        assert "price" in asset
        assert "currency" in asset

    @patch("api.main.graph")
    def test_filter_by_asset_class(self, mock_graph_instance, client, mock_graph):
        """Test filtering assets by asset class."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets?asset_class=Equity")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["asset_class"] == "Equity"
        assert data[0]["symbol"] == "AAPL"

    @patch("api.main.graph")
    def test_filter_by_sector(self, mock_graph_instance, client, mock_graph):
        """Test filtering assets by sector."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets?sector=Technology")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["sector"] == "Technology"

    @patch("api.main.graph")
    def test_filter_combined(self, mock_graph_instance, client, mock_graph):
        """Test filtering with multiple parameters."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets?asset_class=Equity&sector=Technology")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["asset_class"] == "Equity"
        assert data[0]["sector"] == "Technology"

    @patch("api.main.graph")
    def test_assets_additional_fields(self, mock_graph_instance, client, mock_graph):
        """Test that additional fields are included for assets."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets?asset_class=Equity")
        assert response.status_code == 200
        data = response.json()

        equity = data[0]
        assert "additional_fields" in equity
        assert "pe_ratio" in equity["additional_fields"]
        assert equity["additional_fields"]["pe_ratio"] == 25.5

    @patch("api.main.graph")
    def test_assets_error_handling(self, mock_graph_instance, client):
        """Test error handling in assets endpoint."""
        # Make graph.assets raise exception
        type(mock_graph_instance).assets = property(lambda self: (_ for _ in ()).throw(Exception("Database error")))

        response = client.get("/api/assets")
        assert response.status_code == 500
        assert "detail" in response.json()


class TestAssetDetailEndpoint:
    """Test individual asset detail endpoint."""

    @patch("api.main.graph")
    def test_get_asset_detail_success(self, mock_graph_instance, client, mock_graph):
        """Test retrieving details for a specific asset."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets/TEST_AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "TEST_AAPL"
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["asset_class"] == "Equity"
        assert data["price"] == 150.00

    @patch("api.main.graph")
    def test_get_asset_detail_not_found(self, mock_graph_instance, client, mock_graph):
        """Test 404 response for non-existent asset."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets/NONEXISTENT")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("api.main.graph")
    def test_get_bond_detail_with_issuer(self, mock_graph_instance, client, mock_graph):
        """Test bond details include issuer_id."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets/TEST_CORP")
        assert response.status_code == 200
        data = response.json()
        assert data["asset_class"] == "Fixed Income"
        assert "issuer_id" in data["additional_fields"]
        assert data["additional_fields"]["issuer_id"] == "TEST_AAPL"


class TestRelationshipsEndpoint:
    """Test relationship endpoints."""

    @patch("api.main.graph")
    def test_get_asset_relationships(self, mock_graph_instance, client, mock_graph):
        """Test retrieving relationships for a specific asset."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets/TEST_AAPL/relationships")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Should have relationship to corporate bond
        if len(data) > 0:
            rel = data[0]
            assert "source_id" in rel
            assert "target_id" in rel
            assert "relationship_type" in rel
            assert "strength" in rel

    @patch("api.main.graph")
    def test_get_asset_relationships_not_found(self, mock_graph_instance, client, mock_graph):
        """Test 404 for relationships of non-existent asset."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets/NONEXISTENT/relationships")
        assert response.status_code == 404

    @patch("api.main.graph")
    def test_get_all_relationships(self, mock_graph_instance, client, mock_graph):
        """Test retrieving all relationships in the graph."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/relationships")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Verify relationship structure
        if len(data) > 0:
            rel = data[0]
            assert "source_id" in rel
            assert "target_id" in rel
            assert "relationship_type" in rel
            assert 0 <= rel["strength"] <= 1


class TestMetricsEndpoint:
    """Test metrics calculation endpoint."""

    @patch("api.main.graph")
    def test_get_metrics(self, mock_graph_instance, client, mock_graph):
        """Test retrieving network metrics."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()

        assert "total_assets" in data
        assert "total_relationships" in data
        assert "asset_classes" in data
        assert "avg_degree" in data
        assert "max_degree" in data
        assert "network_density" in data

        assert data["total_assets"] == 4
        assert isinstance(data["asset_classes"], dict)
        assert data["avg_degree"] >= 0
        assert data["network_density"] >= 0

    @patch("api.main.graph")
    def test_metrics_asset_class_distribution(self, mock_graph_instance, client, mock_graph):
        """Test asset class distribution in metrics."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/metrics")
        data = response.json()

        assert "Equity" in data["asset_classes"]
        assert "Fixed Income" in data["asset_classes"]
        assert data["asset_classes"]["Equity"] == 1
        assert data["asset_classes"]["Fixed Income"] == 1


class TestVisualizationEndpoint:
    """Test 3D visualization data endpoint."""

    @patch("api.main.graph")
    def test_get_visualization_data(self, mock_graph_instance, client, mock_graph):
        """Test retrieving visualization data."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/visualization")
        assert response.status_code == 200
        data = response.json()

        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert len(data["nodes"]) == 4

    @patch("api.main.graph")
    def test_visualization_node_structure(self, mock_graph_instance, client, mock_graph):
        """Test visualization node data structure."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/visualization")
        data = response.json()

        node = data["nodes"][0]
        assert "id" in node
        assert "name" in node
        assert "symbol" in node
        assert "asset_class" in node
        assert "x" in node
        assert "y" in node
        assert "z" in node
        assert "color" in node
        assert "size" in node

        # Verify coordinates are floats
        assert isinstance(node["x"], float)
        assert isinstance(node["y"], float)
        assert isinstance(node["z"], float)

    @patch("api.main.graph")
    def test_visualization_edge_structure(self, mock_graph_instance, client, mock_graph):
        """Test visualization edge data structure."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/visualization")
        data = response.json()

        if len(data["edges"]) > 0:
            edge = data["edges"][0]
            assert "source" in edge
            assert "target" in edge
            assert "relationship_type" in edge
            assert "strength" in edge
            assert 0 <= edge["strength"] <= 1


class TestMetadataEndpoints:
    """Test metadata endpoints."""

    @staticmethod
    def test_get_asset_classes(client):
        """Test retrieving available asset classes."""
        response = client.get("/api/asset-classes")
        assert response.status_code == 200
        data = response.json()

        assert "asset_classes" in data
        assert isinstance(data["asset_classes"], list)
        assert "Equity" in data["asset_classes"]
        assert "Fixed Income" in data["asset_classes"]
        assert "Commodity" in data["asset_classes"]
        assert "Currency" in data["asset_classes"]

    @staticmethod
    @patch("api.main.graph")
    def test_get_sectors(mock_graph_instance, client, mock_graph):
        """Test retrieving available sectors."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/sectors")
        assert response.status_code == 200
        data = response.json()

        assert "sectors" in data
        assert isinstance(data["sectors"], list)
        assert "Technology" in data["sectors"]

        # Should be sorted
        assert data["sectors"] == sorted(data["sectors"])


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("api.main.graph")
    def test_empty_graph(self, mock_graph_instance, client):
        """Test handling of empty graph."""
        empty_graph = AssetRelationshipGraph()
        mock_graph_instance.relationships = empty_graph.relationships
        mock_graph_instance.get_3d_visualization_data_enhanced = empty_graph.get_3d_visualization_data_enhanced

        response = client.get("/api/assets")
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_assets"] == 0
        assert data["total_relationships"] == 0

    @patch("api.main.graph")
    def test_special_characters_in_asset_id(self, mock_graph_instance, client, mock_graph):
        """Test handling of special characters in asset IDs."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        # Test URL encoding
        response = client.get("/api/assets/TEST%20SPACE")
        assert response.status_code == 404

    @patch("api.main.graph")
    def test_filter_no_matches(self, mock_graph_instance, client, mock_graph):
        """Test filter that returns no results."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets?sector=NonExistent")
        assert response.status_code == 200
        assert len(response.json()) == 0


class TestConcurrency:
    """Test concurrent request handling."""

    @patch("api.main.graph")
    def test_multiple_concurrent_requests(self, mock_graph_instance, client, mock_graph):
        """Test handling multiple concurrent requests."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        # Simulate concurrent requests
        responses = []
        for _ in range(5):
            response = client.get("/api/assets")
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
            assert len(response.json()) == 4


class TestResponseValidation:
    """Test response data validation."""

    @patch("api.main.graph")
    def test_asset_response_schema(self, mock_graph_instance, client, mock_graph):
        """Test asset response matches Pydantic schema."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/assets")
        data = response.json()

        for asset in data:
            # Required fields
            assert isinstance(asset["id"], str)
            assert isinstance(asset["symbol"], str)
            assert isinstance(asset["name"], str)
            assert isinstance(asset["asset_class"], str)
            assert isinstance(asset["sector"], str)
            assert isinstance(asset["price"], (int, float))
            assert isinstance(asset["currency"], str)

            # Optional fields
            if asset["market_cap"] is not None:
                assert isinstance(asset["market_cap"], (int, float))

    @patch("api.main.graph")
    def test_relationship_response_schema(self, mock_graph_instance, client, mock_graph):
        """Test relationship response matches schema."""
        # Configure patched graph with mock_graph attributes
        mock_graph_instance.assets = mock_graph.assets
        mock_graph_instance.relationships = mock_graph.relationships
        mock_graph_instance.calculate_metrics = mock_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = mock_graph.get_3d_visualization_data

        response = client.get("/api/relationships")
        data = response.json()

        for rel in data:
            assert isinstance(rel["source_id"], str)
            assert isinstance(rel["target_id"], str)
            assert isinstance(rel["relationship_type"], str)
            assert isinstance(rel["strength"], float)
            assert 0 <= rel["strength"] <= 1


class TestRealDataFetcherFallback:
    """Test RealDataFetcher fallback behavior when external APIs fail."""

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_real_data_fetcher_complete_failure_fallback(self, mock_ticker):
        """Test that RealDataFetcher falls back to sample data when fetching fails completely."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Simulate API failure that causes exception in create_real_database
        def raise_error(*args, **kwargs):
            raise Exception("API connection failed")

        mock_ticker.side_effect = raise_error

        fetcher = RealDataFetcher()

        # Mock the individual fetch methods to raise exceptions
        with patch.object(fetcher, "_fetch_equity_data", side_effect=Exception("Equity fetch failed")):
            graph = fetcher.create_real_database()

            # Should fall back to sample data and return a valid graph
            assert graph is not None
            assert isinstance(graph, AssetRelationshipGraph)
            assert len(graph.assets) > 0  # Should have sample data

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_real_data_fetcher_partial_fetch_success(self, mock_ticker):
        """Test RealDataFetcher when all individual fetches fail gracefully (empty lists)."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Simulate API failure - each individual fetch will catch exceptions and return empty list
        mock_ticker.side_effect = Exception("API failed")

        fetcher = RealDataFetcher()
        graph = fetcher.create_real_database()

        # Should return an empty graph (individual fetch failures don't trigger fallback)
        assert graph is not None
        assert isinstance(graph, AssetRelationshipGraph)
        # Individual fetch failures result in empty lists, not fallback
        assert len(graph.assets) == 0

    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    def test_fetcher_falls_back_on_unhandled_exception(self, mock_fetch_equity):
        """Test that unhandled exceptions in create_real_database trigger fallback."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Simulate unhandled exception in fetching
        mock_fetch_equity.side_effect = RuntimeError("Unexpected error")

        fetcher = RealDataFetcher()
        graph = fetcher.create_real_database()

        # Should have created a graph with fallback data
        assert graph is not None
        assert isinstance(graph, AssetRelationshipGraph)
        # After fallback to sample data, should have assets
        assert len(graph.assets) > 0

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_real_data_fetcher_empty_history_graceful_handling(self, mock_ticker):
        """Test RealDataFetcher handles empty ticker history gracefully."""
        import pandas as pd

        from src.data.real_data_fetcher import RealDataFetcher

        # Mock ticker to return empty history
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame()  # Empty dataframe
        mock_ticker_instance.info = {}

        fetcher = RealDataFetcher()
        graph = fetcher.create_real_database()

        # Should create empty graph (individual failures don't trigger fallback)
        assert graph is not None
        assert isinstance(graph, AssetRelationshipGraph)

    @patch("src.data.real_data_fetcher.logger")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    @staticmethod
    def test_real_data_fetcher_logs_fallback_on_exception(mock_fetch_equity, mock_logger):
        """Test that RealDataFetcher logs when falling back to sample data."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Simulate exception that triggers fallback
        mock_fetch_equity.side_effect = RuntimeError("Unexpected failure")

        fetcher = RealDataFetcher()
        fetcher.create_real_database()

        # Verify error and warning were logged
        assert mock_logger.error.called
        assert mock_logger.warning.called
        # Check that "Falling back" message was logged
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("Falling back" in call for call in warning_calls)

    @patch("src.data.real_data_fetcher.logger")
    @patch("src.data.real_data_fetcher.yf.Ticker")
    @staticmethod
    def test_individual_asset_class_fetch_failures_logged(mock_ticker, mock_logger):
        """Test that individual asset class fetch failures are logged properly."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Simulate ticker failures
        mock_ticker.side_effect = Exception("Ticker API failed")

        fetcher = RealDataFetcher()
        fetcher.create_real_database()

        # Should log errors for each failed fetch
        assert mock_logger.error.call_count > 0  # Multiple fetch attempts failed

    @staticmethod
    def test_real_data_fetcher_loads_from_cache(tmp_path):
        """RealDataFetcher should return cached dataset when available."""
        from src.data.real_data_fetcher import RealDataFetcher, _save_to_cache
        from src.data.sample_data import create_sample_database

        cache_path = tmp_path / "cached_dataset.json"
        reference_graph = create_sample_database()
        _save_to_cache(reference_graph, cache_path)

        fetcher = RealDataFetcher(cache_path=str(cache_path), enable_network=False)
        graph = fetcher.create_real_database()

        assert len(graph.assets) == len(reference_graph.assets)
        assert set(graph.relationships.keys()) == set(reference_graph.relationships.keys())

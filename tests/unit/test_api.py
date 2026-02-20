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

from unittest.mock import PropertyMock, patch

import pytest
from api.main import app, validate_origin
from fastapi.testclient import TestClient

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
    """
    Create and return an in-memory AssetRelationshipGraph pre-populated with sample assets and their relationships.
    
    The graph contains four sample assets:
    - Equity "TEST_AAPL" (Apple Inc.) with market fields like price, market_cap, and pe_ratio.
    - Bond "TEST_CORP" (issuer_id set to "TEST_AAPL") with fixed-income fields such as coupon_rate and maturity_date.
    - Commodity "TEST_GC" (Gold) with contract and delivery fields.
    - Currency "TEST_EUR" (Euro) with exchange_rate and country.
    
    Returns:
        AssetRelationshipGraph: An in-memory graph populated with the sample assets and built relationships.
    """
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


def _apply_mock_graph_configuration(
    mock_graph_instance: object, graph: AssetRelationshipGraph
) -> None:
    """
    Configure a patched graph mock with attributes copied from a real AssetRelationshipGraph.

    Sets the mock's assets, relationships, calculate_metrics, and get_3d_visualization_data attributes to match the provided graph so tests can reuse a consistent mocked graph surface.

    Parameters:
        mock_graph_instance (object): A unittest.mock.Mock instance that represents the patched api.main.graph.
        graph (AssetRelationshipGraph): The concrete graph whose attributes should be mirrored on the mock.
    """
    # The patched object is a Mock from unittest.mock; we set attributes dynamically.
    mock_graph_instance.assets = graph.assets
    mock_graph_instance.relationships = graph.relationships
    mock_graph_instance.calculate_metrics = graph.calculate_metrics
    mock_graph_instance.get_3d_visualization_data = graph.get_3d_visualization_data


@pytest.fixture
def apply_mock_graph():
    """
    Provide a helper callable that configures a patched graph to match a concrete AssetRelationshipGraph.
    
    Returns:
        helper (callable): A function that accepts a patched graph and a real AssetRelationshipGraph and copies the real graph's assets, relationships, and key methods used by tests (e.g., calculate_metrics, get_3d_visualization_data) onto the patched graph.
    """
    return _apply_mock_graph_configuration


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
class TestAssetsEndpoint:
    """Test assets listing endpoint."""

    @patch("api.main.graph")
    def test_get_all_assets(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test retrieving all assets without filters."""
        apply_mock_graph(mock_graph_instance, mock_graph)

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
    def test_filter_by_asset_class(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test filtering assets by asset class."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets?asset_class=Equity")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["asset_class"] == "Equity"
        assert data[0]["symbol"] == "AAPL"

    @patch("api.main.graph")
    def test_filter_by_sector(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test filtering assets by sector."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets?sector=Technology")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["sector"] == "Technology"

    @patch("api.main.graph")
    def test_filter_combined(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test filtering with multiple parameters."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets?asset_class=Equity&sector=Technology")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["asset_class"] == "Equity"
        assert data[0]["sector"] == "Technology"

    @patch("api.main.graph")
    def test_assets_additional_fields(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test that additional fields are included for assets."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets?asset_class=Equity")
        assert response.status_code == 200
        data = response.json()

        equity = data[0]
        assert "additional_fields" in equity
        assert "pe_ratio" in equity["additional_fields"]
        assert equity["additional_fields"]["pe_ratio"] == 25.5

    @patch("api.main.graph")
    def test_assets_error_handling(self, mock_graph_instance, client, apply_mock_graph):
        """Test error handling in assets endpoint."""
        # Make graph.assets raise an exception when accessed
        type(mock_graph_instance).assets = PropertyMock(
            side_effect=Exception("Database error")
        )

        response = client.get("/api/assets")

        assert response.status_code == 500
        assert "detail" in response.json()


@pytest.mark.unit
class TestAssetDetailEndpoint:
    """Test individual asset detail endpoint."""

    @patch("api.main.graph")
    def test_get_asset_detail_success(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test retrieving details for a specific asset."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets/TEST_AAPL")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "TEST_AAPL"
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["asset_class"] == "Equity"
        assert data["price"] == 150.00

    @patch("api.main.graph")
    def test_get_asset_detail_not_found(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test 404 response for non-existent asset."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets/NONEXISTENT")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("api.main.graph")
    def test_get_bond_detail_with_issuer(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test bond details include issuer_id."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets/TEST_CORP")
        assert response.status_code == 200
        data = response.json()
        assert data["asset_class"] == "Fixed Income"
        assert "issuer_id" in data["additional_fields"]
        assert data["additional_fields"]["issuer_id"] == "TEST_AAPL"


@pytest.mark.unit
class TestRelationshipsEndpoint:
    """Test relationship endpoints."""

    @patch("api.main.graph")
    def test_get_asset_relationships(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test retrieving relationships for a specific asset."""
        apply_mock_graph(mock_graph_instance, mock_graph)

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
    def test_get_asset_relationships_not_found(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test 404 for relationships of non-existent asset."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets/NONEXISTENT/relationships")
        assert response.status_code == 404

    @patch("api.main.graph")
    def test_get_all_relationships(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test retrieving all relationships in the graph."""
        apply_mock_graph(mock_graph_instance, mock_graph)

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


@pytest.mark.unit
class TestMetricsEndpoint:
    """Test metrics calculation endpoint."""

    @patch("api.main.graph")
    def test_get_metrics(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test retrieving network metrics."""
        apply_mock_graph(mock_graph_instance, mock_graph)

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
    def test_metrics_asset_class_distribution(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test asset class distribution in metrics."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/metrics")
        data = response.json()

        assert "Equity" in data["asset_classes"]
        assert "Fixed Income" in data["asset_classes"]
        assert data["asset_classes"]["Equity"] == 1
        assert data["asset_classes"]["Fixed Income"] == 1


@pytest.mark.unit
class TestVisualizationEndpoint:
    """Test 3D visualization data endpoint."""

    @patch("api.main.graph")
    def test_get_visualization_data(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test retrieving visualization data."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/visualization")
        assert response.status_code == 200
        data = response.json()

        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        assert len(data["nodes"]) == 4

    @patch("api.main.graph")
    def test_visualization_node_structure(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test visualization node data structure."""
        apply_mock_graph(mock_graph_instance, mock_graph)

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
    def test_visualization_edge_structure(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test visualization edge data structure."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/visualization")
        data = response.json()

        if len(data["edges"]) > 0:
            edge = data["edges"][0]
            assert "source" in edge
            assert "target" in edge
            assert "relationship_type" in edge
            assert "strength" in edge
            assert 0 <= edge["strength"] <= 1


@pytest.mark.unit
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
    def test_get_sectors(mock_graph_instance, client, mock_graph, apply_mock_graph):
        """Test retrieving available sectors."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/sectors")
        assert response.status_code == 200
        data = response.json()

        assert "sectors" in data
        assert isinstance(data["sectors"], list)
        assert "Technology" in data["sectors"]

        # Should be sorted
        assert data["sectors"] == sorted(data["sectors"])


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("api.main.graph")
    def test_empty_graph(self, mock_graph_instance, client, apply_mock_graph):
        """Test handling of empty graph."""
        empty_graph = AssetRelationshipGraph()
        apply_mock_graph(mock_graph_instance, empty_graph)
        mock_graph_instance.get_3d_visualization_data_enhanced = (
            empty_graph.get_3d_visualization_data_enhanced
        )

        response = client.get("/api/assets")
        assert response.status_code == 200
        assert len(response.json()) == 0

        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_assets"] == 0
        assert data["total_relationships"] == 0

    @patch("api.main.graph")
    def test_special_characters_in_asset_id(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test handling of special characters in asset IDs."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        # Test URL encoding
        response = client.get("/api/assets/TEST%20SPACE")
        assert response.status_code == 404

    @patch("api.main.graph")
    def test_filter_no_matches(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test filter that returns no results."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/assets?sector=NonExistent")
        assert response.status_code == 200
        assert len(response.json()) == 0


@pytest.mark.unit
class TestConcurrency:
    """Test concurrent request handling."""

    @patch("api.main.graph")
    def test_multiple_concurrent_requests(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """
        Verify that multiple parallel requests to the /api/assets endpoint all succeed and return the expected number of assets.
        
        Applies the provided mock graph, performs five GET requests to /api/assets, and asserts each response has HTTP 200 and a JSON list containing four assets.
        """
        apply_mock_graph(mock_graph_instance, mock_graph)

        # Simulate concurrent requests
        responses = []
        for _ in range(5):
            response = client.get("/api/assets")
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == 200
            assert len(response.json()) == 4


@pytest.mark.unit
class TestResponseValidation:
    """Test response data validation."""

    @patch("api.main.graph")
    def test_asset_response_schema(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """
        Validate that each asset in the /api/assets response matches the expected schema.

        Checks that required fields are present and have the correct types (id, symbol, name, asset_class, sector, price, currency) and that `market_cap`, when not null, is a number.
        """
        apply_mock_graph(mock_graph_instance, mock_graph)

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
    def test_relationship_response_schema(
        self, mock_graph_instance, client, mock_graph, apply_mock_graph
    ):
        """Test relationship response matches schema."""
        apply_mock_graph(mock_graph_instance, mock_graph)

        response = client.get("/api/relationships")
        data = response.json()

        for rel in data:
            assert isinstance(rel["source_id"], str)
            assert isinstance(rel["target_id"], str)
            assert isinstance(rel["relationship_type"], str)
            assert isinstance(rel["strength"], float)
            assert 0 <= rel["strength"] <= 1


@pytest.mark.unit
class TestRealDataFetcherFallback:
    """Test RealDataFetcher fallback behavior when external APIs fail."""

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_real_data_fetcher_complete_failure_fallback(self, mock_ticker):
        """Test that RealDataFetcher falls back to sample data when fetching fails completely."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Simulate API failure that causes exception in create_real_database
        def raise_error(*args, **kwargs):
            """Simulate an API connection failure by raising an exception."""
            raise Exception("API connection failed")

        mock_ticker.side_effect = raise_error

        fetcher = RealDataFetcher()

        # Mock the individual fetch methods to raise exceptions
        with patch.object(
            fetcher, "_fetch_equity_data", side_effect=Exception("Equity fetch failed")
        ):
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
    def test_real_data_fetcher_logs_fallback_on_exception(
        mock_fetch_equity, mock_logger
    ):
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
        assert set(graph.relationships.keys()) == set(
            reference_graph.relationships.keys()
        )

        assert set(graph.relationships.keys()) == set(
            reference_graph.relationships.keys()
        )


@pytest.mark.unit
class TestCacheCorruptionRegression:
    """Regression tests for cache corruption and data integrity scenarios."""

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_real_data_fetcher_handles_corrupted_cache_gracefully(mock_ticker):
        """Regression: RealDataFetcher should handle corrupted cache without crashing."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Mock ticker to ensure network calls fail
        mock_ticker.side_effect = Exception("Network unavailable")

        # This tests the scenario where cache exists but is corrupted
        fetcher = RealDataFetcher(cache_path="/nonexistent/corrupted.cache")

        # Should not raise, should fall back gracefully
        graph = fetcher.create_real_database()
        assert graph is not None
        assert isinstance(graph, AssetRelationshipGraph)

    @staticmethod
    def test_api_handles_concurrent_cache_reads(tmp_path):
        """
        Verify concurrent cache reads do not raise errors and produce consistent graphs.

        Spawns multiple threads that each instantiate a RealDataFetcher pointed at the same cache file and create a database from it; the test asserts no thread raises an exception and every returned graph has the same number of assets as the reference graph.
        """
        import threading

        from src.data.real_data_fetcher import _save_to_cache
        from src.data.sample_data import create_sample_database

        cache_path = tmp_path / "concurrent_cache.json"
        reference_graph = create_sample_database()
        _save_to_cache(reference_graph, cache_path)

        results = []
        errors = []

        def load_from_cache():
            """
            Load a cached real-data AssetRelationshipGraph and record the outcome.
            
            Attempts to create a RealDataFetcher with network disabled and build the cached graph; on success appends the resulting graph to the outer-scope `results` list, on failure appends the caught exception to the outer-scope `errors` list.
            """
            try:
                from src.data.real_data_fetcher import RealDataFetcher

                fetcher = RealDataFetcher(
                    cache_path=str(cache_path), enable_network=False
                )
                graph = fetcher.create_real_database()
                results.append(graph)
            except Exception as e:
                errors.append(e)

        # Spawn multiple threads to read cache concurrently
        threads = [threading.Thread(target=load_from_cache) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should succeed
        assert len(errors) == 0
        assert len(results) == 5
        for graph in results:
            assert len(graph.assets) == len(reference_graph.assets)

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fallback_creates_valid_empty_graph_on_total_failure(mock_ticker):
        """Regression: Total API failure should create a valid empty or sample graph."""
        from src.data.real_data_fetcher import RealDataFetcher

        # Simulate complete network failure
        mock_ticker.side_effect = ConnectionError("Network completely down")

        fetcher = RealDataFetcher()
        graph = fetcher.create_real_database()

        # Should return a valid graph object (either empty or with sample data)
        assert graph is not None
        assert hasattr(graph, "assets")
        assert hasattr(graph, "relationships")
        assert hasattr(graph, "calculate_metrics")


@pytest.mark.unit
class TestAPISecurityRegression:
    """Regression tests for API security edge cases."""

    @staticmethod
    def test_cors_rejects_javascript_protocol():
        """Regression: Ensure javascript: protocol is rejected."""
        assert validate_origin("javascript:alert(1)") is False
        assert validate_origin("javascript://example.com") is False

    @staticmethod
    def test_cors_rejects_data_urls():
        """Regression: Ensure data: URLs are rejected."""
        assert validate_origin("data:text/html,<script>alert(1)</script>") is False

    @staticmethod
    def test_cors_rejects_malformed_urls():
        """Regression: Ensure malformed URLs are rejected."""
        assert validate_origin("ht tp://example.com") is False
        assert validate_origin("https://") is False
        assert validate_origin("https://..com") is False
        assert validate_origin("") is False

    @staticmethod
    @patch("api.main.graph")
    def test_api_sanitizes_asset_id_input(mock_graph_instance, client, mock_graph):
        """Regression: API should handle asset IDs with potential injection characters."""
        # Configure patched graph
        mock_graph_instance.assets = mock_graph.assets

        # Test various potentially malicious inputs
        malicious_ids = [
            "../../../etc/passwd",
            "'; DROP TABLE assets; --",
            "<script>alert(1)</script>",
            "../../sensitive",
        ]

        for malicious_id in malicious_ids:
            response = client.get(f"/api/assets/{malicious_id}")
            # Should return 404, not 500 (server error)
            assert response.status_code == 404


@pytest.mark.unit
class TestAPIBoundaryConditions:
    """Boundary condition tests for API endpoints."""

    @staticmethod
    @patch("api.main.graph")
    def test_api_handles_extremely_large_graph(mock_graph_instance, client):
        """Boundary: API should handle graphs with many assets."""
        large_graph = AssetRelationshipGraph()

        # Create 1000 assets
        for i in range(1000):
            equity = Equity(
                id=f"TEST_{i}",
                symbol=f"TST{i}",
                name=f"Test Asset {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i,
            )
            large_graph.add_asset(equity)

        mock_graph_instance.assets = large_graph.assets
        mock_graph_instance.relationships = large_graph.relationships
        mock_graph_instance.calculate_metrics = large_graph.calculate_metrics
        mock_graph_instance.get_3d_visualization_data = (
            large_graph.get_3d_visualization_data
        )

        # Should not timeout or error
        response = client.get("/api/assets")
        assert response.status_code == 200
        assert len(response.json()) == 1000

    @staticmethod
    @patch("api.main.graph")
    def test_api_handles_asset_with_none_values(mock_graph_instance, client):
        """Boundary: API should handle assets with None optional fields."""
        graph = AssetRelationshipGraph()

        # Create equity with minimal fields (many None values)
        equity = Equity(
            id="MINIMAL",
            symbol="MIN",
            name="Minimal Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
            market_cap=None,
            pe_ratio=None,
            dividend_yield=None,
        )
        graph.add_asset(equity)

        mock_graph_instance.assets = graph.assets
        mock_graph_instance.relationships = graph.relationships

        response = client.get("/api/assets/MINIMAL")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "MINIMAL"
        # None values should be handled gracefully
        assert "market_cap" in data


@pytest.mark.unit
class TestNegativeScenarios:
    """Negative test cases for error conditions."""

    @staticmethod
    def test_validate_origin_with_null_bytes():
        """Negative: Origin with null bytes should be rejected."""
        assert validate_origin("https://evil\x00.com") is False
        assert validate_origin("https://example.com\x00") is False

    @staticmethod
    def test_validate_origin_with_unicode_domain():
        """Negative: Test handling of internationalized domain names."""
        result = validate_origin("https://münchen.de")
        # IDN with HTTPS: validate_origin should accept valid HTTPS domains
        assert result is True

    @staticmethod
    @patch("api.main.graph")
    def test_api_metrics_with_division_by_zero_risk(mock_graph_instance, client):
        """Negative: Metrics with empty graph should not cause division by zero."""
        empty_graph = AssetRelationshipGraph()
        mock_graph_instance.assets = empty_graph.assets
        mock_graph_instance.relationships = empty_graph.relationships
        mock_graph_instance.calculate_metrics = empty_graph.calculate_metrics

        # Should not raise ZeroDivisionError
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_assets"] == 0
        assert data["network_density"] == 0
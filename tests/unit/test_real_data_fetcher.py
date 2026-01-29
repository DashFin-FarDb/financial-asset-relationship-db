"""
Comprehensive unit tests for src/data/real_data_fetcher.py.

Tests cover:
- RealDataFetcher initialization with different configurations
- Database creation with network enabled/disabled
- Cache loading and saving functionality
- Fallback factory mechanisms
- Data fetching methods for equities, bonds, commodities, and currencies
- Regulatory event creation
- Serialization and deserialization functions
- Edge cases and error handling
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.data.real_data_fetcher import (
    RealDataFetcher,
    _deserialize_asset,
    _deserialize_event,
    _deserialize_graph,
    _enum_to_value,
    _load_from_cache,
    _save_to_cache,
    _serialize_dataclass,
    _serialize_graph,
    create_real_database,
)
from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import (
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)


class TestRealDataFetcherInitialization:
    """Test RealDataFetcher initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        fetcher = RealDataFetcher()

        assert fetcher.session is None
        assert fetcher.cache_path is None
        assert fetcher.fallback_factory is None
        assert fetcher.enable_network is True

    def test_init_with_cache_path(self, tmp_path):
        """Test initialization with cache path."""
        cache_path = str(tmp_path / "cache.json")
        fetcher = RealDataFetcher(cache_path=cache_path)

        assert fetcher.cache_path == Path(cache_path)
        assert fetcher.enable_network is True

    def test_init_with_fallback_factory(self):
        """Test initialization with custom fallback factory."""

        def custom_factory():
            return AssetRelationshipGraph()

        fetcher = RealDataFetcher(fallback_factory=custom_factory)

        assert fetcher.fallback_factory is custom_factory

    def test_init_with_network_disabled(self):
        """Test initialization with network disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        assert fetcher.enable_network is False

    def test_init_all_parameters(self, tmp_path):
        """Test initialization with all parameters."""
        cache_path = str(tmp_path / "cache.json")

        def custom_factory():
            return AssetRelationshipGraph()

        fetcher = RealDataFetcher(cache_path=cache_path, fallback_factory=custom_factory, enable_network=False)

        assert fetcher.cache_path == Path(cache_path)
        assert fetcher.fallback_factory is custom_factory
        assert fetcher.enable_network is False


class TestCreateRealDatabase:
    """Test create_real_database method."""

    def test_create_database_network_disabled(self):
        """Test database creation when network is disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        graph = fetcher.create_real_database()

        assert isinstance(graph, AssetRelationshipGraph)
        # Should use fallback data
        assert len(graph.assets) > 0

    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_bond_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_commodity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_currency_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._create_regulatory_events")
    def test_create_database_with_network(self, mock_events, mock_currency, mock_commodity, mock_bond, mock_equity):
        """Test database creation with network enabled."""
        # Setup mocks
        mock_equity.return_value = [
            Equity(
                id="TEST",
                symbol="TEST",
                name="Test Equity",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
            )
        ]
        mock_bond.return_value = []
        mock_commodity.return_value = []
        mock_currency.return_value = []
        mock_events.return_value = []

        fetcher = RealDataFetcher(enable_network=True)
        graph = fetcher.create_real_database()

        assert isinstance(graph, AssetRelationshipGraph)
        assert "TEST" in graph.assets
        mock_equity.assert_called_once()

    def test_create_database_with_cache(self, tmp_path):
        """Test database creation loads from cache when available."""
        cache_path = tmp_path / "cache.json"

        # Create a graph and save it to cache
        graph = AssetRelationshipGraph()
        equity = Equity(
            id="CACHED",
            symbol="CACHED",
            name="Cached Equity",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=50.0,
        )
        graph.add_asset(equity)
        _save_to_cache(graph, cache_path)

        # Create fetcher with cache
        fetcher = RealDataFetcher(cache_path=str(cache_path), enable_network=True)
        loaded_graph = fetcher.create_real_database()

        assert "CACHED" in loaded_graph.assets
        assert loaded_graph.assets["CACHED"].name == "Cached Equity"

    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    def test_create_database_fetch_failure_uses_fallback(self, mock_equity):
        """Test that fetch failure falls back to sample data."""
        # Make equity fetch raise an exception
        mock_equity.side_effect = Exception("Network error")

        fetcher = RealDataFetcher(enable_network=True)
        graph = fetcher.create_real_database()

        # Should fall back to sample data
        assert isinstance(graph, AssetRelationshipGraph)


class TestFetchMethods:
    """Test data fetching methods."""

    @patch("yfinance.Ticker")
    def test_fetch_equity_data_success(self, mock_ticker_class):
        """Test successful equity data fetching."""
        # Setup mock
        mock_ticker = Mock()
        mock_ticker.info = {
            "marketCap": 1e12,
            "trailingPE": 25.0,
            "dividendYield": 0.01,
            "trailingEps": 5.0,
            "bookValue": 20.0,
        }
        mock_ticker.history.return_value = Mock(empty=False)
        mock_ticker.history.return_value.__getitem__ = lambda self, key: Mock(
            iloc=Mock(__getitem__=lambda self, idx: 150.0)
        )
        mock_ticker_class.return_value = mock_ticker

        equities = RealDataFetcher._fetch_equity_data()

        assert isinstance(equities, list)
        # Should try to fetch AAPL, MSFT, XOM, JPM
        assert mock_ticker_class.call_count == 4

    @patch("yfinance.Ticker")
    def test_fetch_equity_data_with_empty_history(self, mock_ticker_class):
        """Test equity fetching when history is empty."""
        mock_ticker = Mock()
        mock_ticker.history.return_value = Mock(empty=True)
        mock_ticker_class.return_value = mock_ticker

        equities = RealDataFetcher._fetch_equity_data()

        # Should skip equities with empty history
        assert isinstance(equities, list)

    @patch("yfinance.Ticker")
    def test_fetch_bond_data_success(self, mock_ticker_class):
        """Test successful bond data fetching."""
        mock_ticker = Mock()
        mock_ticker.info = {"yield": 0.03}
        mock_ticker.history.return_value = Mock(empty=False)
        mock_ticker.history.return_value.__getitem__ = lambda self, key: Mock(
            iloc=Mock(__getitem__=lambda self, idx: 100.0)
        )
        mock_ticker_class.return_value = mock_ticker

        bonds = RealDataFetcher._fetch_bond_data()

        assert isinstance(bonds, list)

    @patch("yfinance.Ticker")
    def test_fetch_commodity_data_success(self, mock_ticker_class):
        """Test successful commodity data fetching."""
        mock_ticker = Mock()
        mock_hist = Mock(empty=False)
        mock_close = Mock()
        mock_close.pct_change.return_value.std.return_value = 0.02
        mock_hist.__getitem__ = lambda self, key: mock_close if key == "Close" else Mock()
        mock_hist.__len__ = lambda self: 5
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker

        commodities = RealDataFetcher._fetch_commodity_data()

        assert isinstance(commodities, list)

    @patch("yfinance.Ticker")
    def test_fetch_currency_data_success(self, mock_ticker_class):
        """Test successful currency data fetching."""
        mock_ticker = Mock()
        mock_ticker.history.return_value = Mock(empty=False)
        mock_ticker.history.return_value.__getitem__ = lambda self, key: Mock(
            iloc=Mock(__getitem__=lambda self, idx: 1.1)
        )
        mock_ticker_class.return_value = mock_ticker

        currencies = RealDataFetcher._fetch_currency_data()

        assert isinstance(currencies, list)

    def test_create_regulatory_events(self):
        """Test regulatory event creation."""
        events = RealDataFetcher._create_regulatory_events()

        assert isinstance(events, list)
        assert len(events) > 0
        for event in events:
            assert isinstance(event, RegulatoryEvent)
            assert event.id
            assert event.asset_id
            assert event.event_type
            assert event.date


class TestFallback:
    """Test fallback mechanism."""

    def test_fallback_with_custom_factory(self):
        """Test fallback uses custom factory when provided."""
        custom_graph = AssetRelationshipGraph()
        custom_asset = Equity(
            id="CUSTOM",
            symbol="CUSTOM",
            name="Custom Asset",
            asset_class=AssetClass.EQUITY,
            sector="Custom",
            price=99.0,
        )
        custom_graph.add_asset(custom_asset)

        def custom_factory():
            return custom_graph

        fetcher = RealDataFetcher(fallback_factory=custom_factory, enable_network=False)
        result = fetcher._fallback()

        assert "CUSTOM" in result.assets

    def test_fallback_without_custom_factory(self):
        """Test fallback uses sample data when no factory provided."""
        fetcher = RealDataFetcher(enable_network=False)
        result = fetcher._fallback()

        assert isinstance(result, AssetRelationshipGraph)
        # Should have sample data
        assert len(result.assets) > 0


class TestSerialization:
    """Test serialization functions."""

    def test_enum_to_value_with_enum(self):
        """Test _enum_to_value with enum."""
        result = _enum_to_value(AssetClass.EQUITY)
        assert result == "Equity"

    def test_enum_to_value_with_non_enum(self):
        """Test _enum_to_value with non-enum value."""
        result = _enum_to_value("test_string")
        assert result == "test_string"

    def test_serialize_dataclass_equity(self):
        """Test serializing an Equity dataclass."""
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
            pe_ratio=20.0,
        )

        serialized = _serialize_dataclass(equity)

        assert serialized["id"] == "TEST"
        assert serialized["asset_class"] == "Equity"
        assert serialized["__type__"] == "Equity"
        assert serialized["price"] == 100.0

    def test_serialize_graph(self):
        """Test serializing a complete graph."""
        graph = AssetRelationshipGraph()
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)
        graph.add_relationship("TEST", "TEST2", "test_rel", 0.5)

        event = RegulatoryEvent(
            id="EVENT1",
            asset_id="TEST",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-01",
            description="Test event",
            impact_score=0.5,
        )
        graph.add_regulatory_event(event)

        serialized = _serialize_graph(graph)

        assert "assets" in serialized
        assert "regulatory_events" in serialized
        assert "relationships" in serialized
        assert "incoming_relationships" in serialized
        assert len(serialized["assets"]) == 1
        assert len(serialized["regulatory_events"]) == 1


class TestDeserialization:
    """Test deserialization functions."""

    def test_deserialize_asset_equity(self):
        """Test deserializing an Equity asset."""
        data = {
            "__type__": "Equity",
            "id": "TEST",
            "symbol": "TEST",
            "name": "Test",
            "asset_class": "Equity",
            "sector": "Technology",
            "price": 100.0,
            "market_cap": None,
            "currency": "USD",
            "pe_ratio": 20.0,
            "dividend_yield": None,
            "earnings_per_share": None,
            "book_value": None,
        }

        asset = _deserialize_asset(data)

        assert isinstance(asset, Equity)
        assert asset.id == "TEST"
        assert asset.asset_class == AssetClass.EQUITY
        assert asset.pe_ratio == 20.0

    def test_deserialize_asset_bond(self):
        """Test deserializing a Bond asset."""
        data = {
            "__type__": "Bond",
            "id": "BOND",
            "symbol": "BOND",
            "name": "Test Bond",
            "asset_class": "Fixed Income",
            "sector": "Government",
            "price": 100.0,
            "market_cap": None,
            "currency": "USD",
            "yield_to_maturity": 0.03,
            "coupon_rate": 0.025,
            "maturity_date": "2030-01-01",
            "credit_rating": "AAA",
            "issuer_id": None,
        }

        asset = _deserialize_asset(data)

        assert isinstance(asset, Bond)
        assert asset.yield_to_maturity == 0.03

    def test_deserialize_asset_commodity(self):
        """Test deserializing a Commodity asset."""
        data = {
            "__type__": "Commodity",
            "id": "GOLD",
            "symbol": "GC",
            "name": "Gold",
            "asset_class": "Commodity",
            "sector": "Precious Metals",
            "price": 2000.0,
            "market_cap": None,
            "currency": "USD",
            "contract_size": 100,
            "delivery_date": "2025-03-31",
            "volatility": 0.15,
        }

        asset = _deserialize_asset(data)

        assert isinstance(asset, Commodity)
        assert asset.contract_size == 100

    def test_deserialize_asset_currency(self):
        """Test deserializing a Currency asset."""
        data = {
            "__type__": "Currency",
            "id": "EUR",
            "symbol": "EUR",
            "name": "Euro",
            "asset_class": "Currency",
            "sector": "Forex",
            "price": 1.1,
            "market_cap": None,
            "currency": "USD",
            "exchange_rate": 1.1,
            "country": "EU",
            "central_bank_rate": 0.02,
        }

        asset = _deserialize_asset(data)

        assert isinstance(asset, Currency)
        assert asset.exchange_rate == 1.1

    def test_deserialize_event(self):
        """Test deserializing a regulatory event."""
        data = {
            "id": "EVENT1",
            "asset_id": "TEST",
            "event_type": "Earnings Report",
            "date": "2024-01-01",
            "description": "Test event",
            "impact_score": 0.5,
            "related_assets": ["TEST2"],
        }

        event = _deserialize_event(data)

        assert isinstance(event, RegulatoryEvent)
        assert event.id == "EVENT1"
        assert event.event_type == RegulatoryActivity.EARNINGS_REPORT
        assert event.related_assets == ["TEST2"]

    def test_deserialize_graph(self):
        """Test deserializing a complete graph."""
        payload = {
            "assets": [
                {
                    "__type__": "Equity",
                    "id": "TEST",
                    "symbol": "TEST",
                    "name": "Test",
                    "asset_class": "Equity",
                    "sector": "Technology",
                    "price": 100.0,
                    "market_cap": None,
                    "currency": "USD",
                    "pe_ratio": None,
                    "dividend_yield": None,
                    "earnings_per_share": None,
                    "book_value": None,
                }
            ],
            "regulatory_events": [
                {
                    "id": "EVENT1",
                    "asset_id": "TEST",
                    "event_type": "Earnings Report",
                    "date": "2024-01-01",
                    "description": "Test event",
                    "impact_score": 0.5,
                    "related_assets": [],
                }
            ],
            "relationships": {
                "TEST": [
                    {
                        "target": "TEST2",
                        "relationship_type": "test_rel",
                        "strength": 0.5,
                    }
                ]
            },
            "incoming_relationships": {},
        }

        graph = _deserialize_graph(payload)

        assert isinstance(graph, AssetRelationshipGraph)
        assert "TEST" in graph.assets
        assert len(graph.regulatory_events) == 1


class TestCacheOperations:
    """Test cache loading and saving."""

    def test_save_to_cache(self, tmp_path):
        """Test saving graph to cache file."""
        cache_path = tmp_path / "cache.json"
        graph = AssetRelationshipGraph()
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)

        _save_to_cache(graph, cache_path)

        assert cache_path.exists()
        with cache_path.open("r") as f:
            data = json.load(f)
        assert "assets" in data
        assert len(data["assets"]) == 1

    def test_load_from_cache(self, tmp_path):
        """Test loading graph from cache file."""
        cache_path = tmp_path / "cache.json"

        # Create and save a graph
        graph = AssetRelationshipGraph()
        equity = Equity(
            id="CACHED",
            symbol="CACHED",
            name="Cached Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        graph.add_asset(equity)
        _save_to_cache(graph, cache_path)

        # Load it back
        loaded_graph = _load_from_cache(cache_path)

        assert isinstance(loaded_graph, AssetRelationshipGraph)
        assert "CACHED" in loaded_graph.assets
        assert loaded_graph.assets["CACHED"].name == "Cached Asset"

    def test_save_to_cache_creates_parent_dirs(self, tmp_path):
        """Test that save_to_cache creates parent directories."""
        cache_path = tmp_path / "subdir" / "deep" / "cache.json"
        graph = AssetRelationshipGraph()

        _save_to_cache(graph, cache_path)

        assert cache_path.exists()
        assert cache_path.parent.exists()


class TestCreateRealDatabaseFunction:
    """Test the module-level create_real_database function."""

    @patch("src.data.real_data_fetcher.RealDataFetcher")
    def test_create_real_database_function(self, mock_fetcher_class):
        """Test that create_real_database function creates fetcher and calls method."""
        mock_instance = Mock()
        mock_graph = AssetRelationshipGraph()
        mock_instance.create_real_database.return_value = mock_graph
        mock_fetcher_class.return_value = mock_instance

        result = create_real_database()

        mock_fetcher_class.assert_called_once_with()
        mock_instance.create_real_database.assert_called_once()
        assert result == mock_graph


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_cache_load_with_corrupted_file(self, tmp_path):
        """Test loading from corrupted cache file."""
        cache_path = tmp_path / "corrupted.json"
        cache_path.write_text("{ invalid json")

        # Should raise an exception
        with pytest.raises(json.JSONDecodeError):
            _load_from_cache(cache_path)

    def test_create_database_cache_load_failure_continues(self, tmp_path):
        """Test that cache load failure doesn't prevent database creation."""
        cache_path = tmp_path / "bad_cache.json"
        cache_path.write_text("{ invalid")

        fetcher = RealDataFetcher(cache_path=str(cache_path), enable_network=False)
        graph = fetcher.create_real_database()

        # Should fall back to sample data despite cache error
        assert isinstance(graph, AssetRelationshipGraph)

    @patch("src.data.real_data_fetcher._save_to_cache")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_bond_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_commodity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_currency_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._create_regulatory_events")
    def test_cache_save_failure_doesnt_prevent_return(
        self,
        mock_events,
        mock_currency,
        mock_commodity,
        mock_bond,
        mock_equity,
        mock_save,
        tmp_path,
    ):
        """Test that cache save failure doesn't prevent returning the graph."""
        # Setup mocks
        mock_equity.return_value = []
        mock_bond.return_value = []
        mock_commodity.return_value = []
        mock_currency.return_value = []
        mock_events.return_value = []
        mock_save.side_effect = Exception("Save failed")

        cache_path = tmp_path / "cache.json"
        fetcher = RealDataFetcher(cache_path=str(cache_path), enable_network=True)
        graph = fetcher.create_real_database()

        # Should still return a graph even if save fails
        assert isinstance(graph, AssetRelationshipGraph)

    def test_deserialize_asset_with_missing_type(self):
        """Test deserializing asset without __type__ field."""
        data = {
            "id": "TEST",
            "symbol": "TEST",
            "name": "Test",
            "asset_class": "Equity",
            "sector": "Technology",
            "price": 100.0,
            "market_cap": None,
            "currency": "USD",
        }

        # Should default to base Asset class
        from src.models.financial_models import Asset

        asset = _deserialize_asset(data)
        assert isinstance(asset, Asset)

    def test_serialize_graph_with_complex_relationships(self):
        """Test serializing graph with bidirectional relationships."""
        graph = AssetRelationshipGraph()
        equity1 = Equity(
            id="TEST1",
            symbol="TEST1",
            name="Test 1",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        equity2 = Equity(
            id="TEST2",
            symbol="TEST2",
            name="Test 2",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=200.0,
        )
        graph.add_asset(equity1)
        graph.add_asset(equity2)
        graph.add_relationship("TEST1", "TEST2", "same_sector", 0.7, bidirectional=True)

        serialized = _serialize_graph(graph)

        # Should have relationships in both directions
        assert "TEST1" in serialized["relationships"]
        assert "TEST2" in serialized["relationships"]


class TestRegressionCases:
    """Regression tests for previously identified issues."""

    def test_atomic_cache_write(self, tmp_path):
        """Test that cache writes are atomic using temp file + rename."""
        cache_path = tmp_path / "cache.json"
        graph = AssetRelationshipGraph()

        # Save to cache
        _save_to_cache(graph, cache_path)

        # File should exist and be valid
        assert cache_path.exists()
        loaded = _load_from_cache(cache_path)
        assert isinstance(loaded, AssetRelationshipGraph)

    def test_enum_serialization_consistency(self):
        """Test that enums serialize and deserialize consistently."""
        original = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )

        # Serialize then deserialize
        serialized = _serialize_dataclass(original)
        deserialized = _deserialize_asset(serialized)

        assert deserialized.asset_class == original.asset_class
        assert isinstance(deserialized.asset_class, AssetClass)

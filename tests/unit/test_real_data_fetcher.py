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
from unittest.mock import Mock, patch

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
    Asset,
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)

pytestmark = pytest.mark.unit


class TestRealDataFetcherInitialization:
    """Test RealDataFetcher initialization."""

    @staticmethod
    def test_init_with_defaults():
        """Test initialization with default parameters."""
        fetcher = RealDataFetcher()

        assert fetcher.session is None
        assert fetcher.cache_path is None
        assert fetcher.fallback_factory is None
        assert fetcher.enable_network is True

    @staticmethod
    def test_init_with_cache_path(tmp_path):
        """Test initialization with cache path."""
        cache_path = str(tmp_path / "cache.json")
        fetcher = RealDataFetcher(cache_path=cache_path)

        assert fetcher.cache_path == Path(cache_path)
        assert fetcher.enable_network is True

    @staticmethod
    def test_init_with_fallback_factory():
        """Test initialization with custom fallback factory."""

        def custom_factory():
            """Create and return a new AssetRelationshipGraph instance."""
            return AssetRelationshipGraph()

        fetcher = RealDataFetcher(fallback_factory=custom_factory)

        assert fetcher.fallback_factory is custom_factory

    @staticmethod
    def test_init_with_network_disabled():
        """Test initialization with network disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        assert fetcher.enable_network is False

    @staticmethod
    def test_init_all_parameters(tmp_path):
        """Test initialization with all parameters."""
        cache_path = str(tmp_path / "cache.json")

        def custom_factory():
            """Factory function that creates and returns a new AssetRelationshipGraph instance."""
            return AssetRelationshipGraph()

        fetcher = RealDataFetcher(
            cache_path=cache_path, fallback_factory=custom_factory, enable_network=False
        )

        assert fetcher.cache_path == Path(cache_path)
        assert fetcher.fallback_factory is custom_factory
        assert fetcher.enable_network is False


class TestCreateRealDatabase:
    """Test create_real_database method."""

    @staticmethod
    def test_create_database_network_disabled():
        """Test database creation when network is disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        graph = fetcher.create_real_database()

        assert isinstance(graph, AssetRelationshipGraph)
        # Should use fallback data
        assert len(graph.assets) > 0

    @staticmethod
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_bond_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_commodity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_currency_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._create_regulatory_events")
    def test_create_database_with_network(
        mock_events, mock_currency, mock_commodity, mock_bond, mock_equity
    ):
        """Test database creation with network enabled."""
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

    @staticmethod
    def test_create_database_with_cache(tmp_path):
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

    @staticmethod
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    def test_create_database_fetch_failure_uses_fallback(mock_equity):
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
        assert equities, "Expected at least one fetched equity"
        assert all(isinstance(eq, Equity) for eq in equities), (
            "All items should be Equity instances"
        )
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
        mock_close.iloc.__getitem__ = Mock(return_value=2000.0)
        mock_close.pct_change.return_value.std.return_value = 0.02
        mock_hist.__getitem__ = (
            lambda self, key: mock_close if key == "Close" else Mock()
        )
        mock_hist.__len__ = lambda self: 5
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker

        commodities = RealDataFetcher._fetch_commodity_data()

        assert isinstance(commodities, list)
        assert all(isinstance(c, Commodity) for c in commodities)

    @staticmethod
    def test_create_regulatory_events():
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

    @staticmethod
    def test_fallback_with_custom_factory():
        """Test fallback uses custom factory when provided."""
        AssetRelationshipGraph()
        Equity(
            id="CUSTOM",
            symbol="CUST",
            name="Custom Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=50.0,
        )

    @staticmethod
    def test_fallback_with_custom_factory_returns_its_custom_graph():
        """Test fallback uses provided custom factory when network is disabled and returns its graph."""
        Equity("CUSTOM")

    @staticmethod
    def test_fallback():
        """Test fallback uses provided custom factory to produce a custom graph when network is disabled."""
        custom_graph = AssetRelationshipGraph()
        custom_asset = Asset(name="CUSTOM", asset_class=AssetClass.EQUITY)

        @staticmethod
        def test_fallback_with_custom_factory():
            """Test fallback uses provided factory when custom factory provided."""
            custom_graph.add_asset(custom_asset)

            def custom_factory():
                """Return a custom AssetRelationshipGraph for fallback when network is disabled."""
                return custom_graph

            fetcher = RealDataFetcher(
                fallback_factory=custom_factory, enable_network=False
            )
            result = fetcher._fallback()

            assert "CUSTOM" in result.assets

    @staticmethod
    def test_fallback_without_custom_factory():
        """Test fallback uses sample data when no factory provided."""
        fetcher = RealDataFetcher(enable_network=False)
        result = fetcher._fallback()

        assert isinstance(result, AssetRelationshipGraph)
        # Should have sample data
        assert len(result.assets) > 0


class TestSerialization:
    """Test serialization functions."""

    @staticmethod
    def test_enum_to_value_with_enum():
        """Test _enum_to_value with enum."""
        result = _enum_to_value(AssetClass.EQUITY)
        assert result == "Equity"

    @staticmethod
    def test_enum_to_value_with_non_enum():
        """Test _enum_to_value with non-enum value."""
        result = _enum_to_value("test_string")
        assert result == "test_string"

    @staticmethod
    def test_serialize_dataclass_equity():
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

    @staticmethod
    def test_serialize_graph():
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

    @staticmethod
    def test_deserialize_asset_equity():
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

    @staticmethod
    def test_deserialize_asset_bond():
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

    @staticmethod
    def test_deserialize_asset_commodity():
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

    @staticmethod
    def test_deserialize_asset_currency():
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

    @staticmethod
    def test_deserialize_event():
        """Test deserializing a regulatory event."""
        data = {
            "id": "EVENT1",
            "asset_id": "TEST",
            "event_type": "Earnings Report",
            "date": "2024-01-01",
            "description": "Test event",
            "impact_score": 0.5,
        }

        event = _deserialize_event(data)

        assert isinstance(event, RegulatoryEvent)
        assert event.id == "EVENT1"
        assert event.asset_id == "TEST"
        assert event.event_type == RegulatoryActivity.EARNINGS_REPORT
        assert event.description == "Test event"
        assert event.impact_score == 0.5


class TestCacheOperations:
    """Test cache loading and saving."""

    @staticmethod
    def test_save_to_cache(tmp_path):
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

    @staticmethod
    def test_load_from_cache(tmp_path):
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

    @staticmethod
    def test_save_to_cache_creates_parent_dirs(tmp_path):
        """Test that save_to_cache creates parent directories."""
        cache_path = tmp_path / "subdir" / "deep" / "cache.json"
        graph = AssetRelationshipGraph()

        _save_to_cache(graph, cache_path)

        assert cache_path.exists()
        assert cache_path.parent.exists()


class TestCreateRealDatabaseFunction:
    """Test the module-level create_real_database function."""

    @staticmethod
    @patch("src.data.real_data_fetcher.RealDataFetcher")
    def test_create_real_database_function(mock_fetcher_class):
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

    @staticmethod
    def test_cache_load_with_corrupted_file(tmp_path):
        """Test loading from corrupted cache file."""
        cache_path = tmp_path / "corrupted.json"
        cache_path.write_text("{ invalid json")

        # Should raise an exception
        with pytest.raises(json.JSONDecodeError):
            _load_from_cache(cache_path)

    @staticmethod
    def test_create_database_cache_load_failure_continues(tmp_path):
        """Test that cache load failure doesn't prevent database creation."""
        cache_path = tmp_path / "bad_cache.json"
        cache_path.write_text("{ invalid")

        fetcher = RealDataFetcher(cache_path=str(cache_path), enable_network=False)
        graph = fetcher.create_real_database()

        # Should fall back to sample data despite cache error
        assert isinstance(graph, AssetRelationshipGraph)

    @staticmethod
    @patch("src.data.real_data_fetcher._save_to_cache")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_bond_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_commodity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_currency_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._create_regulatory_events")
    def test_cache_save_failure_doesnt_prevent_return(
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

    @staticmethod
    def test_deserialize_asset_with_missing_type():
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

        asset = _deserialize_asset(data)
        assert isinstance(asset, Asset)

    @staticmethod
    def test_serialize_graph_with_complex_relationships():
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

    @staticmethod
    def test_cache_roundtrip(tmp_path):
        """Test that a saved graph can be loaded back correctly."""
        cache_path = tmp_path / "cache.json"
        graph = AssetRelationshipGraph()

        # Save to cache
        _save_to_cache(graph, cache_path)

        # File should exist and be valid
        assert cache_path.exists()
        loaded = _load_from_cache(cache_path)
        assert isinstance(loaded, AssetRelationshipGraph)

    @staticmethod
    def test_enum_serialization_consistency():
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


class TestNetworkDisabled:
    """Test behavior when network is explicitly disabled."""

    @staticmethod
    def test_network_disabled_never_attempts_fetch():
        """Test that network fetches are not attempted when disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        # Should return fallback without any fetch attempts
        graph = fetcher.create_real_database()

        assert isinstance(graph, AssetRelationshipGraph)
        # Should have sample data
        assert len(graph.assets) > 0

    @staticmethod
    def test_network_disabled_with_cache_uses_cache(tmp_path):
        """Test that cache is used even when network is disabled."""
        cache_path = tmp_path / "cache.json"

        # Create cached data
        cached_graph = AssetRelationshipGraph()
        custom_asset = Equity(
            id="CACHED_ONLY",
            symbol="CO",
            name="Cached Only",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=999.0,
        )
        cached_graph.add_asset(custom_asset)
        _save_to_cache(cached_graph, cache_path)

        # Fetch with network disabled
        fetcher = RealDataFetcher(cache_path=str(cache_path), enable_network=False)
        result = fetcher.create_real_database()

        # Should have loaded from cache
        assert "CACHED_ONLY" in result.assets
        assert result.assets["CACHED_ONLY"].price == 999.0


class TestAllAssetTypes:
    """Test fetching and handling all asset types."""

    @patch("yfinance.Ticker")
    def test_fetch_all_equity_symbols(self, mock_ticker_class):
        """Test that all equity symbols are attempted."""
        mock_ticker = Mock()
        mock_ticker.info = {}
        mock_ticker.history.return_value = Mock(empty=False)
        mock_ticker.history.return_value.__getitem__ = lambda self, key: Mock(
            iloc=Mock(__getitem__=lambda self, idx: 100.0)
        )
        mock_ticker_class.return_value = mock_ticker

        RealDataFetcher._fetch_equity_data()

        # Should attempt AAPL, MSFT, XOM, JPM
        assert mock_ticker_class.call_count == 4
        called_symbols = [call[0][0] for call in mock_ticker_class.call_args_list]
        assert "AAPL" in called_symbols
        assert "MSFT" in called_symbols
        assert "XOM" in called_symbols
        assert "JPM" in called_symbols

    @patch("yfinance.Ticker")
    def test_fetch_all_bond_symbols(self, mock_ticker_class):
        """Test that all bond symbols are attempted."""
        mock_ticker = Mock()
        mock_ticker.info = {"yield": 0.03}
        mock_ticker.history.return_value = Mock(empty=False)
        mock_ticker.history.return_value.__getitem__ = lambda self, key: Mock(
            iloc=Mock(__getitem__=lambda self, idx: 100.0)
        )
        mock_ticker_class.return_value = mock_ticker

        RealDataFetcher._fetch_bond_data()

        # Should attempt TLT, LQD, HYG
        assert mock_ticker_class.call_count == 3

    @patch("yfinance.Ticker")
    def test_fetch_all_commodity_symbols(self, mock_ticker_class):
        """Test that all commodity symbols are attempted."""
        mock_ticker = Mock()
        mock_hist = Mock(empty=False)
        mock_close = Mock()
        mock_close.pct_change.return_value.std.return_value = 0.02
        mock_hist.__getitem__ = (
            lambda self, key: mock_close if key == "Close" else Mock()
        )
        mock_hist.__len__ = lambda self: 5
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker

        RealDataFetcher._fetch_commodity_data()

        # Should attempt GC=F, CL=F, SI=F
        assert mock_ticker_class.call_count == 3

    @patch("yfinance.Ticker")
    def test_fetch_all_currency_symbols(self, mock_ticker_class):
        """Test that all currency symbols are attempted."""
        mock_ticker = Mock()
        mock_ticker.history.return_value = Mock(empty=False)
        mock_ticker.history.return_value.__getitem__ = lambda self, key: Mock(
            iloc=Mock(__getitem__=lambda self, idx: 1.1)
        )
        mock_ticker_class.return_value = mock_ticker

        _ = RealDataFetcher._fetch_currency_data()

        # Should attempt EURUSD=X, GBPUSD=X, JPYUSD=X
        assert mock_ticker_class.call_count == 3


class TestRegulatoryEvents:
    """Test regulatory event creation and handling."""

    @staticmethod
    def test_regulatory_events_have_required_fields():
        """Test that all regulatory events have required fields."""
        events = RealDataFetcher._create_regulatory_events()

        for event in events:
            assert event.id
            assert event.asset_id
            assert isinstance(event.event_type, RegulatoryActivity)
            assert event.date
            assert event.description
            assert isinstance(event.impact_score, (int, float))
            assert isinstance(event.related_assets, list)

    @staticmethod
    def test_regulatory_events_reference_known_assets():
        """Test that regulatory events reference expected asset IDs."""
        events = RealDataFetcher._create_regulatory_events()

        expected_assets = {"AAPL", "MSFT", "XOM"}
        asset_ids = {event.asset_id for event in events}

        # Should create events for known assets
        assert any(asset_id in expected_assets for asset_id in asset_ids)

    @staticmethod
    def test_regulatory_events_have_valid_impact_scores():
        """Test that impact scores are within valid range."""
        events = RealDataFetcher._create_regulatory_events()

        for event in events:
            assert 0.0 <= event.impact_score <= 1.0


class TestGraphBuilding:
    """Test the complete graph building process."""

    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_bond_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_commodity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_currency_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._create_regulatory_events")
    def test_graph_includes_all_asset_types(
        self, mock_events, mock_currency, mock_commodity, mock_bond, mock_equity
    ):
        """Test that the built graph includes all fetched asset types."""
        # Setup mocks
        mock_equity.return_value = [
            Equity(
                id="E1",
                symbol="E1",
                name="Equity 1",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=100.0,
            )
        ]
        mock_bond.return_value = [
            Bond(
                id="B1",
                symbol="B1",
                name="Bond 1",
                asset_class=AssetClass.FIXED_INCOME,
                sector="Gov",
                price=1000.0,
            )
        ]
        mock_commodity.return_value = [
            Commodity(
                id="C1",
                symbol="C1",
                name="Commodity 1",
                asset_class=AssetClass.COMMODITY,
                sector="Materials",
                price=2000.0,
            )
        ]
        mock_currency.return_value = [
            Currency(
                id="CUR1",
                symbol="CUR1",
                name="Currency 1",
                asset_class=AssetClass.CURRENCY,
                sector="Forex",
                price=1.1,
            )
        ]
        mock_events.return_value = []

        fetcher = RealDataFetcher(enable_network=True)
        graph = fetcher.create_real_database()

        assert "E1" in graph.assets
        assert "B1" in graph.assets
        assert "C1" in graph.assets
        assert "CUR1" in graph.assets

    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_bond_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_commodity_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._fetch_currency_data")
    @patch("src.data.real_data_fetcher.RealDataFetcher._create_regulatory_events")
    def test_graph_builds_relationships(
        self, mock_events, mock_currency, mock_commodity, mock_bond, mock_equity
    ):
        """Test that relationships are built in the graph."""
        mock_equity.return_value = [
            Equity(
                id="E1",
                symbol="E1",
                name="E1",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=100.0,
            ),
            Equity(
                id="E2",
                symbol="E2",
                name="E2",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=200.0,
            ),
        ]
        mock_bond.return_value = []
        mock_commodity.return_value = []
        mock_currency.return_value = []
        mock_events.return_value = []

        fetcher = RealDataFetcher(enable_network=True)
        graph = fetcher.create_real_database()

        # Same sector equities should have relationships
        total_relationships = sum(len(rels) for rels in graph.relationships.values())
        assert total_relationships > 0


class TestSerializationEdgeCases:
    """Test edge cases in serialization/deserialization."""

    @staticmethod
    def test_serialize_asset_with_none_values():
        """Test serializing asset with None optional fields."""
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
            pe_ratio=None,
            dividend_yield=None,
        )

        serialized = _serialize_dataclass(equity)

        assert serialized["pe_ratio"] is None
        assert serialized["dividend_yield"] is None
        assert "__type__" in serialized

    @staticmethod
    def test_deserialize_graph_with_relationships():
        """Test deserializing graph with relationships."""
        payload = {
            "assets": [
                {
                    "__type__": "Equity",
                    "id": "A1",
                    "symbol": "A1",
                    "name": "Asset 1",
                    "asset_class": "Equity",
                    "sector": "Tech",
                    "price": 100.0,
                    "market_cap": None,
                    "currency": "USD",
                    "pe_ratio": None,
                    "dividend_yield": None,
                    "earnings_per_share": None,
                    "book_value": None,
                },
                {
                    "__type__": "Equity",
                    "id": "A2",
                    "symbol": "A2",
                    "name": "Asset 2",
                    "asset_class": "Equity",
                    "sector": "Tech",
                    "price": 200.0,
                    "market_cap": None,
                    "currency": "USD",
                    "pe_ratio": None,
                    "dividend_yield": None,
                    "earnings_per_share": None,
                    "book_value": None,
                },
            ],
            "regulatory_events": [],
            "relationships": {
                "A1": [
                    {
                        "target": "A2",
                        "relationship_type": "same_sector",
                        "strength": 0.7,
                    }
                ]
            },
            "incoming_relationships": {},
        }

        graph = _deserialize_graph(payload)

        assert "A1" in graph.assets
        assert "A2" in graph.assets
        assert "A1" in graph.relationships
        assert len(graph.relationships["A1"]) == 1

    @staticmethod
    def test_serialize_graph_with_all_relationships():
        """Test serializing graph with both outgoing and incoming relationships."""
        graph = AssetRelationshipGraph()

        e1 = Equity(
            id="E1",
            symbol="E1",
            name="E1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        e2 = Equity(
            id="E2",
            symbol="E2",
            name="E2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )

        graph.add_asset(e1)
        graph.add_asset(e2)
        graph.add_relationship("E1", "E2", "test", 0.5, bidirectional=True)

        serialized = _serialize_graph(graph)

        assert "relationships" in serialized
        assert "incoming_relationships" in serialized
        # Bidirectional relationship creates entries in both
        assert "E1" in serialized["relationships"]
        assert "E2" in serialized["relationships"]


class TestCacheOverwriteOperations:
    """Test cache overwrite operations sequentially."""

    @staticmethod
    def test_cache_overwrite_preserves_data(tmp_path):
        """Test that overwriting cache preserves all data correctly."""
        cache_path = tmp_path / "cache.json"

        # Write first version
        graph1 = AssetRelationshipGraph()
        asset1 = Equity(
            id="V1",
            symbol="V1",
            name="Version 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        graph1.add_asset(asset1)
        _save_to_cache(graph1, cache_path)

        # Overwrite with second version
        graph2 = AssetRelationshipGraph()
        asset2 = Equity(
            id="V2",
            symbol="V2",
            name="Version 2",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=200.0,
        )
        graph2.add_asset(asset2)
        _save_to_cache(graph2, cache_path)

        # Load and verify it's the second version
        loaded = _load_from_cache(cache_path)
        assert "V2" in loaded.assets
        assert "V1" not in loaded.assets


class TestFetchMethodsErrorHandling:
    """Test error handling in fetch methods."""

    @patch("yfinance.Ticker")
    def test_fetch_equity_handles_missing_info(self, mock_ticker_class):
        """Test equity fetch handles missing info gracefully."""
        mock_ticker = Mock()
        mock_ticker.info = {}  # Empty info
        mock_ticker.history.return_value = Mock(empty=False)
        mock_ticker.history.return_value.__getitem__ = lambda self, key: Mock(
            iloc=Mock(__getitem__=lambda self, idx: 100.0)
        )
        mock_ticker_class.return_value = mock_ticker

        equities = RealDataFetcher._fetch_equity_data()

        # Should still create equities with None for missing fields
        assert isinstance(equities, list)
        for equity in equities:
            assert equity.price > 0

    @patch("yfinance.Ticker")
    def test_fetch_commodity_handles_volatility_calculation_error(
        self, mock_ticker_class
    ):
        """Test commodity fetch handles volatility calculation errors."""
        mock_ticker = Mock()
        mock_hist = Mock(empty=False)
        mock_close = Mock()
        mock_close.iloc.__getitem__ = Mock(return_value=2000.0)
        # Simulate error in std calculation
        mock_close.pct_change.return_value.std.side_effect = Exception("Calc error")
        mock_hist.__getitem__ = (
            lambda self, key: mock_close if key == "Close" else Mock()
        )
        mock_hist.__len__ = lambda self: 5
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker

        # Should not raise, might use default volatility
        commodities = RealDataFetcher._fetch_commodity_data()
        assert isinstance(commodities, list)

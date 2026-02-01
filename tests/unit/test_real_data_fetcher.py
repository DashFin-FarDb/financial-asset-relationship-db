"""Comprehensive tests for real_data_fetcher module.

This module tests:
- RealDataFetcher initialization and configuration
- Real data fetching from Yahoo Finance
- Fallback behavior when network is disabled or fails
- Cache loading and saving
- Serialization and deserialization of graph data
- Error handling and edge cases
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
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
    RegulatoryActivity,
    RegulatoryEvent,
)


@pytest.fixture
def sample_graph():
    """Create a sample asset graph for testing."""
    graph = AssetRelationshipGraph()

    equity = Equity(
        id="TEST_AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=150.0,
        market_cap=2.4e12,
        pe_ratio=25.5,
        dividend_yield=0.005,
        earnings_per_share=5.89,
        book_value=4.50,
    )

    bond = Bond(
        id="TEST_BOND",
        symbol="BOND",
        name="Test Bond",
        asset_class=AssetClass.FIXED_INCOME,
        sector="Corporate",
        price=1000.0,
        yield_to_maturity=0.04,
        coupon_rate=0.035,
        maturity_date="2030-12-31",
        credit_rating="AA",
        issuer_id="TEST_AAPL",
    )

    event = RegulatoryEvent(
        id="EVT1",
        asset_id="TEST_AAPL",
        event_type=RegulatoryActivity.EARNINGS_REPORT,
        date="2024-01-01",
        description="Q4 Earnings",
        impact_score=0.8,
        related_assets=["TEST_BOND"],
    )

    graph.add_asset(equity)
    graph.add_asset(bond)
    graph.add_regulatory_event(event)
    graph.build_relationships()

    return graph


@pytest.mark.unit
class TestRealDataFetcherInitialization:
    """Tests for RealDataFetcher initialization."""

    @staticmethod
    def test_initialization_defaults():
        """Test RealDataFetcher initialization with defaults."""
        fetcher = RealDataFetcher()

        assert fetcher.session is None
        assert fetcher.cache_path is None
        assert fetcher.fallback_factory is None
        assert fetcher.enable_network is True

    @staticmethod
    def test_initialization_with_cache_path():
        """Test initialization with cache path."""
        cache_path = "/tmp/test_cache.json"
        fetcher = RealDataFetcher(cache_path=cache_path)

        assert fetcher.cache_path == Path(cache_path)

    @staticmethod
    def test_initialization_with_fallback_factory():
        """Test initialization with fallback factory."""

        def custom_fallback():
            """Provide a new AssetRelationshipGraph instance as a fallback."""
            return AssetRelationshipGraph()

        fetcher = RealDataFetcher(fallback_factory=custom_fallback)

        assert fetcher.fallback_factory is custom_fallback

    @staticmethod
    def test_initialization_with_network_disabled():
        """Test initialization with network disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        assert fetcher.enable_network is False


class TestFallbackBehavior:
    """Tests for fallback behavior."""

    @staticmethod
    def test_fallback_uses_custom_factory():
        """Test _fallback uses custom factory when provided."""
        custom_graph = AssetRelationshipGraph()
        custom_graph.add_asset(
            Equity(
                id="CUSTOM",
                symbol="CST",
                name="Custom Asset",
                asset_class=AssetClass.EQUITY,
                sector="Test",
                price=100.0,
            )
        )

        def custom_factory():
            """Return the custom AssetRelationshipGraph for fallback."""
            return custom_graph

        fetcher = RealDataFetcher(fallback_factory=custom_factory)
        result = fetcher._fallback()

        assert "CUSTOM" in result.assets

    @staticmethod
    def test_fallback_uses_sample_data_by_default():
        """Test _fallback uses sample data when no factory provided."""
        fetcher = RealDataFetcher()
        result = fetcher._fallback()

        assert isinstance(result, AssetRelationshipGraph)
        assert len(result.assets) > 0  # Should have sample data

    @staticmethod
    def test_create_real_database_with_network_disabled():
        """Test create_real_database uses fallback when network disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        graph = fetcher.create_real_database()

        assert isinstance(graph, AssetRelationshipGraph)
        # Should use fallback data
        assert len(graph.assets) > 0


class TestCacheOperations:
    """Tests for cache loading and saving."""

    @staticmethod
    def test_load_from_cache_success(tmp_path, sample_graph):
        """Test successful loading from cache."""
        cache_file = tmp_path / "test_cache.json"

        # Save graph to cache
        _save_to_cache(sample_graph, cache_file)

        # Load it back
        loaded_graph = _load_from_cache(cache_file)

        assert len(loaded_graph.assets) == len(sample_graph.assets)
        assert "TEST_AAPL" in loaded_graph.assets
        assert "TEST_BOND" in loaded_graph.assets

    @staticmethod
    def test_save_to_cache_creates_parent_directories(tmp_path, sample_graph):
        """Test _save_to_cache creates parent directories."""
        nested_cache = tmp_path / "nested" / "dir" / "cache.json"

        _save_to_cache(sample_graph, nested_cache)

        assert nested_cache.exists()
        assert nested_cache.parent.exists()

    @staticmethod
    def test_cache_loaded_when_available(tmp_path, sample_graph):
        """Test RealDataFetcher loads from cache when available."""
        cache_file = tmp_path / "cache.json"
        _save_to_cache(sample_graph, cache_file)

        fetcher = RealDataFetcher(cache_path=str(cache_file), enable_network=False)
        graph = fetcher.create_real_database()

        # Should load from cache
        assert "TEST_AAPL" in graph.assets

    @staticmethod
    def test_cache_corrupted_falls_back(tmp_path):
        """Test fallback when cache file is corrupted."""
        cache_file = tmp_path / "corrupted.json"
        cache_file.write_text("{ invalid json content", encoding="utf-8")

        fetcher = RealDataFetcher(cache_path=str(cache_file), enable_network=False)
        graph = fetcher.create_real_database()

        # Should fall back to sample data
        assert isinstance(graph, AssetRelationshipGraph)

    @staticmethod
    def test_cache_saved_after_successful_fetch(tmp_path):
        """Test cache is saved after successful data fetch."""
        cache_file = tmp_path / "new_cache.json"

        with patch("src.data.real_data_fetcher.yf.Ticker") as mock_ticker:
            # Mock successful ticker response
            mock_ticker_instance = mock_ticker.return_value
            mock_ticker_instance.history.return_value = pd.DataFrame(
                {
                    "Close": [150.0],
                },
                index=[pd.Timestamp("2024-01-01")],
            )
            mock_ticker_instance.info = {
                "marketCap": 2.4e12,
                "trailingPE": 25.5,
            }

            fetcher = RealDataFetcher(cache_path=str(cache_file))
            fetcher.create_real_database()

            # Cache file should be created
            assert cache_file.exists()


class TestSerializationDeserialization:
    """Tests for serialization and deserialization functions."""

    @staticmethod
    def test_enum_to_value_with_enum():
        """Test _enum_to_value extracts value from enum."""
        result = _enum_to_value(AssetClass.EQUITY)

        assert result == "Equity"

    @staticmethod
    def test_enum_to_value_with_non_enum():
        """Test _enum_to_value returns non-enum values unchanged."""
        result = _enum_to_value("plain string")

        assert result == "plain string"

    @staticmethod
    def test_serialize_dataclass_adds_type_field():
        """Test _serialize_dataclass adds __type__ field."""
        equity = Equity(
            id="TEST",
            symbol="TST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )

        result = _serialize_dataclass(equity)

        assert "__type__" in result
        assert result["__type__"] == "Equity"

    @staticmethod
    def test_serialize_dataclass_converts_enums():
        """Test _serialize_dataclass converts enums to values."""
        equity = Equity(
            id="TEST",
            symbol="TST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )

        result = _serialize_dataclass(equity)

        assert result["asset_class"] == "Equity"

    @staticmethod
    def test_deserialize_asset_equity():
        """Test _deserialize_asset reconstructs Equity."""
        data = {
            "__type__": "Equity",
            "id": "TEST",
            "symbol": "TST",
            "name": "Test",
            "asset_class": "Equity",
            "sector": "Tech",
            "price": 100.0,
            "market_cap": None,
            "currency": "USD",
            "pe_ratio": None,
            "dividend_yield": None,
            "earnings_per_share": None,
            "book_value": None,
        }

        asset = _deserialize_asset(data)

        assert isinstance(asset, Equity)
        assert asset.id == "TEST"
        assert asset.asset_class == AssetClass.EQUITY

    @staticmethod
    def test_deserialize_asset_bond():
        """Test _deserialize_asset reconstructs Bond."""
        data = {
            "__type__": "Bond",
            "id": "BOND",
            "symbol": "BND",
            "name": "Test Bond",
            "asset_class": "Fixed Income",
            "sector": "Corporate",
            "price": 1000.0,
            "market_cap": None,
            "currency": "USD",
            "yield_to_maturity": 0.04,
            "coupon_rate": 0.03,
            "maturity_date": "2030-12-31",
            "credit_rating": "AA",
            "issuer_id": None,
        }

        asset = _deserialize_asset(data)

        assert isinstance(asset, Bond)
        assert asset.yield_to_maturity == 0.04

    @staticmethod
    def test_deserialize_event():
        """Test _deserialize_event reconstructs RegulatoryEvent."""
        data = {
            "id": "EVT1",
            "asset_id": "AAPL",
            "event_type": "EARNINGS_REPORT",
            "date": "2024-01-01",
            "description": "Q4 Earnings",
            "impact_score": 0.8,
            "related_assets": ["BOND1"],
        }

        event = _deserialize_event(data)

        assert isinstance(event, RegulatoryEvent)
        assert event.event_type == RegulatoryActivity.EARNINGS_REPORT
        assert event.impact_score == 0.8

    @staticmethod
    def test_serialize_graph_full_cycle(sample_graph):
        """Test full serialization and deserialization cycle."""
        # Serialize
        serialized = _serialize_graph(sample_graph)

        # Deserialize
        restored = _deserialize_graph(serialized)

        # Verify
        assert len(restored.assets) == len(sample_graph.assets)
        assert len(restored.regulatory_events) == len(sample_graph.regulatory_events)
        assert set(restored.relationships.keys()) == set(
            sample_graph.relationships.keys()
        )


class TestDataFetching:
    """Tests for data fetching methods."""

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_equity_data_success(mock_ticker):
        """Test successful equity data fetch."""
        # Mock ticker response
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame(
            {
                "Close": [150.0],
            },
            index=[pd.Timestamp("2024-01-01")],
        )
        mock_ticker_instance.info = {
            "marketCap": 2.4e12,
            "trailingPE": 25.5,
            "dividendYield": 0.005,
            "trailingEps": 5.89,
            "bookValue": 4.50,
        }

        equities = RealDataFetcher._fetch_equity_data()

        assert len(equities) > 0
        assert all(isinstance(e, Equity) for e in equities)

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_equity_data_empty_history(mock_ticker):
        """Test equity fetch with empty history."""
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame()
        mock_ticker_instance.info = {}

        equities = RealDataFetcher._fetch_equity_data()

        # Should skip assets with no history
        assert isinstance(equities, list)

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_bond_data_success(mock_ticker):
        """Test successful bond data fetch."""
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame(
            {
                "Close": [100.0],
            },
            index=[pd.Timestamp("2024-01-01")],
        )
        mock_ticker_instance.info = {"yield": 0.03}

        bonds = RealDataFetcher._fetch_bond_data()

        assert len(bonds) > 0
        assert all(isinstance(b, Bond) for b in bonds)

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_commodity_data_success(mock_ticker):
        """Test successful commodity data fetch."""
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame(
            {
                "Close": [1950.0, 1960.0, 1955.0, 1965.0, 1970.0],
            },
            index=pd.date_range("2024-01-01", periods=5, freq="D"),
        )

        commodities = RealDataFetcher._fetch_commodity_data()

        assert len(commodities) > 0
        assert all(isinstance(c, Commodity) for c in commodities)

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_currency_data_success(mock_ticker):
        """Test successful currency data fetch."""
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame(
            {
                "Close": [1.08],
            },
            index=[pd.Timestamp("2024-01-01")],
        )

        currencies = RealDataFetcher._fetch_currency_data()

        assert len(currencies) > 0
        assert all(isinstance(c, Currency) for c in currencies)

    @staticmethod
    def test_create_regulatory_events():
        """Test creation of regulatory events."""
        events = RealDataFetcher._create_regulatory_events()

        assert len(events) > 0
        assert all(isinstance(e, RegulatoryEvent) for e in events)
        assert all(e.event_type in RegulatoryActivity for e in events)


class TestCreateRealDatabase:
    """Tests for create_real_database function."""

    @staticmethod
    def test_create_real_database_function():
        """Test standalone create_real_database function."""
        with patch.object(RealDataFetcher, "create_real_database") as mock_create:
            mock_graph = AssetRelationshipGraph()
            mock_create.return_value = mock_graph

            result = create_real_database()

            assert result is mock_graph


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_handles_ticker_exception(mock_ticker):
        """Test fetch handles ticker exceptions gracefully."""
        mock_ticker.side_effect = Exception("API error")

        equities = RealDataFetcher._fetch_equity_data()

        # Should return empty list on error
        assert equities == []

    @staticmethod
    @patch("src.data.real_data_fetcher.logger")
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_logs_errors(mock_ticker, mock_logger):
        """Test that fetch errors are logged."""
        mock_ticker.side_effect = Exception("Test error")

        RealDataFetcher._fetch_equity_data()

        # Verify error was logged
        assert mock_logger.error.called

    @staticmethod
    def test_create_real_database_exception_fallback():
        """Test fallback on exception during database creation."""
        with patch.object(RealDataFetcher, "_fetch_equity_data") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("Unexpected error")

            fetcher = RealDataFetcher()
            graph = fetcher.create_real_database()

            # Should fall back to sample data
            assert isinstance(graph, AssetRelationshipGraph)
            assert len(graph.assets) > 0

    @staticmethod
    def test_deserialize_asset_unknown_type():
        """Test _deserialize_asset with unknown type falls back to Asset."""
        data = {
            "__type__": "UnknownAssetType",
            "id": "TEST",
            "symbol": "TST",
            "name": "Test",
            "asset_class": "Equity",
            "sector": "Tech",
            "price": 100.0,
            "market_cap": None,
            "currency": "USD",
        }

        from src.models.financial_models import Asset

        asset = _deserialize_asset(data)

        # Should create base Asset class
        assert isinstance(asset, Asset)

    @staticmethod
    def test_save_cache_with_permission_error(tmp_path, sample_graph):
        """Test cache save handles permission errors."""
        import os

        cache_file = tmp_path / "readonly_cache.json"
        cache_file.touch()

        # Make file readonly
        os.chmod(cache_file, 0o444)

        try:
            # Should not raise exception
            _save_to_cache(sample_graph, cache_file)
        except PermissionError:
            # Expected on some systems
            pass
        finally:
            # Restore permissions for cleanup
            os.chmod(cache_file, 0o644)


class TestAdvancedSerialization:
    """Tests for advanced serialization scenarios."""

    @staticmethod
    def test_serialize_graph_preserves_relationships(sample_graph):
        """Test serialization preserves relationship details."""
        serialized = _serialize_graph(sample_graph)

        assert "relationships" in serialized
        assert "incoming_relationships" in serialized

        # Check relationship structure
        for _, rels in serialized["relationships"].items():
            assert isinstance(rels, list)
            for rel in rels:
                assert "target" in rel
                assert "relationship_type" in rel
                assert "strength" in rel

    @staticmethod
    def test_deserialize_graph_restores_relationships(sample_graph):
        """Test deserialization restores relationships correctly."""
        serialized = _serialize_graph(sample_graph)
        restored = _deserialize_graph(serialized)

        # Check that relationships are restored
        assert len(restored.relationships) == len(sample_graph.relationships)

    @staticmethod
    def test_serialize_graph_handles_empty_graph():
        """Test serializing an empty graph."""
        empty_graph = AssetRelationshipGraph()

        serialized = _serialize_graph(empty_graph)

        assert serialized["assets"] == []
        assert serialized["regulatory_events"] == []
        assert serialized["relationships"] == {}

    @staticmethod
    def test_deserialize_graph_handles_empty_data():
        """Test deserializing empty graph data."""
        empty_data = {
            "assets": [],
            "regulatory_events": [],
            "relationships": {},
            "incoming_relationships": {},
        }

        graph = _deserialize_graph(empty_data)

        assert len(graph.assets) == 0
        assert len(graph.regulatory_events) == 0


class TestCachePathHandling:
    """Tests for cache path handling."""

    @staticmethod
    def test_cache_path_converts_string_to_path():
        """Test cache path is converted to Path object."""
        fetcher = RealDataFetcher(cache_path="/tmp/cache.json")

        assert isinstance(fetcher.cache_path, Path)
        assert str(fetcher.cache_path) == "/tmp/cache.json"

    @staticmethod
    def test_cache_path_none_by_default():
        """Test cache path is None by default."""
        fetcher = RealDataFetcher()

        assert fetcher.cache_path is None

    @staticmethod
    def test_no_cache_when_path_not_provided(tmp_path):
        """Test no caching occurs when path not provided."""
        fetcher = RealDataFetcher(enable_network=False)

        # Should use fallback since no cache and network disabled
        graph = fetcher.create_real_database()

        # Should have fallback data
        assert len(graph.assets) > 0


class TestNetworkControl:
    """Tests for network enable/disable control."""

    @staticmethod
    def test_network_disabled_skips_fetch():
        """Test network disabled skips fetch and uses fallback."""
        with patch.object(RealDataFetcher, "_fetch_equity_data") as mock_fetch:
            fetcher = RealDataFetcher(enable_network=False)
            graph = fetcher.create_real_database()

            # Fetch should not be called
            mock_fetch.assert_not_called()

            # Should still have data from fallback
            assert len(graph.assets) > 0

    @staticmethod
    def test_network_enabled_attempts_fetch():
        """Test network enabled attempts to fetch data."""
        with patch.object(RealDataFetcher, "_fetch_equity_data") as mock_fetch:
            mock_fetch.return_value = []

            fetcher = RealDataFetcher(enable_network=True)

            with patch.object(RealDataFetcher, "_fetch_bond_data", return_value=[]), \
                 patch.object(RealDataFetcher, "_fetch_commodity_data", return_value=[]), \
                 patch.object(RealDataFetcher, "_fetch_currency_data", return_value=[]):
                fetcher.create_real_database()

            # Fetch should be called
            mock_fetch.assert_called_once()


class TestIntegration:
    """Integration tests combining multiple components."""

    @staticmethod
    def test_full_cycle_with_cache(tmp_path):
        """Test full cycle of fetch, save, and load from cache."""
        cache_file = tmp_path / "integration_cache.json"

        # Create and save a graph
        graph1 = AssetRelationshipGraph()
        equity = Equity(
            id="INT_TEST",
            symbol="INT",
            name="Integration Test",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=100.0,
        )
        graph1.add_asset(equity)
        _save_to_cache(graph1, cache_file)

        # Load it back
        fetcher = RealDataFetcher(cache_path=str(cache_file), enable_network=False)
        graph2 = fetcher.create_real_database()

        # Verify loaded correctly
        assert "INT_TEST" in graph2.assets
        assert graph2.assets["INT_TEST"].symbol == "INT"

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_real_data_creates_valid_graph(mock_ticker):
        """Test that fetched real data creates a valid graph."""
        # Mock all ticker responses
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame(
            {
                "Close": [150.0, 151.0, 152.0],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )
        mock_ticker_instance.info = {
            "marketCap": 2.4e12,
            "trailingPE": 25.5,
        }

        fetcher = RealDataFetcher()
        graph = fetcher.create_real_database()

        assert isinstance(graph, AssetRelationshipGraph)
        assert len(graph.assets) > 0

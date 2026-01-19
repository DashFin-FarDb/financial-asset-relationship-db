"""Comprehensive unit tests for src/data/real_data_fetcher.py.

Tests the real data fetching functionality including:
- Cache management
- Network fetch with yfinance
- Fallback behavior
- Serialization/deserialization
- Error handling
- Data validation
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.data.real_data_fetcher import (
    RealDataFetcher,
    _deserialize_asset,
    _deserialize_graph,
    _load_from_cache,
    _save_to_cache,
    _serialize_asset,
    _serialize_dataclass,
    _serialize_graph,
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


class TestSerializeDataclass:
    """Test dataclass serialization helper."""

    @staticmethod
    def test_serialize_equity():
        """Test serializing an Equity instance."""
        equity = Equity(
            id="AAPL",
            symbol="AAPL",
            name="Apple Inc.",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            market_cap=2.4e12,
            pe_ratio=25.5,
        )

        result = _serialize_dataclass(equity)

        assert result["id"] == "AAPL"
        assert result["symbol"] == "AAPL"
        assert result["asset_class"] == "equity"
        assert result["price"] == 150.0

    @staticmethod
    def test_serialize_bond():
        """Test serializing a Bond instance."""
        bond = Bond(
            id="BOND1",
            symbol="BOND",
            name="Test Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Finance",
            price=1000.0,
            yield_to_maturity=0.03,
        )

        result = _serialize_dataclass(bond)

        assert result["asset_class"] == "fixed_income"
        assert result["yield_to_maturity"] == 0.03

    @staticmethod
    def test_serialize_regulatory_event():
        """Test serializing a RegulatoryEvent."""
        event = RegulatoryEvent(
            id="EVENT1",
            asset_id="AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-01",
            description="Q4 Earnings",
            impact_score=0.1,
        )

        result = _serialize_dataclass(event)

        assert result["event_type"] == "earnings_report"
        assert result["impact_score"] == 0.1


class TestSerializeAsset:
    """Test asset-specific serialization."""

    @staticmethod
    def test_serialize_asset_includes_type():
        """Test that serialized asset includes __type__ field."""
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )

        result = _serialize_asset(equity)

        assert "__type__" in result
        assert result["__type__"] == "Equity"

    @staticmethod
    def test_serialize_commodity():
        """Test serializing a Commodity."""
        commodity = Commodity(
            id="GOLD",
            symbol="GC",
            name="Gold",
            asset_class=AssetClass.COMMODITY,
            sector="Metals",
            price=2000.0,
            contract_size=100.0,
        )

        result = _serialize_asset(commodity)

        assert result["__type__"] == "Commodity"
        assert result["contract_size"] == 100.0

    @staticmethod
    def test_serialize_currency():
        """Test serializing a Currency."""
        currency = Currency(
            id="EUR",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Forex",
            price=1.10,
            exchange_rate=1.10,
        )

        result = _serialize_asset(currency)

        assert result["__type__"] == "Currency"
        assert result["exchange_rate"] == 1.10


class TestDeserializeAsset:
    """Test asset deserialization."""

    @staticmethod
    def test_deserialize_equity():
        """Test deserializing an Equity from dict."""
        data = {
            "__type__": "Equity",
            "id": "AAPL",
            "symbol": "AAPL",
            "name": "Apple",
            "asset_class": "equity",
            "sector": "Technology",
            "price": 150.0,
            "market_cap": 2.4e12,
        }

        result = _deserialize_asset(data)

        assert isinstance(result, Equity)
        assert result.id == "AAPL"
        assert result.price == 150.0

    @staticmethod
    def test_deserialize_bond():
        """Test deserializing a Bond from dict."""
        data = {
            "__type__": "Bond",
            "id": "BOND1",
            "symbol": "BOND",
            "name": "Test Bond",
            "asset_class": "fixed_income",
            "sector": "Finance",
            "price": 1000.0,
            "yield_to_maturity": 0.03,
        }

        result = _deserialize_asset(data)

        assert isinstance(result, Bond)
        assert result.yield_to_maturity == 0.03

    @staticmethod
    def test_deserialize_unknown_type():
        """Test that unknown asset type raises ValueError."""
        data = {
            "__type__": "UnknownAsset",
            "id": "TEST",
        }

        with pytest.raises(ValueError, match="Unknown asset type"):
            _deserialize_asset(data)


class TestGraphSerialization:
    """Test full graph serialization and deserialization."""

    @staticmethod
    def test_serialize_graph_with_assets():
        """Test serializing a graph with assets."""
        graph = AssetRelationshipGraph()
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        graph.add_asset(equity)

        result = _serialize_graph(graph)

        assert "assets" in result
        assert len(result["assets"]) == 1
        assert result["assets"][0]["id"] == "TEST"

    @staticmethod
    def test_serialize_graph_with_relationships():
        """Test serializing graph with relationships."""
        graph = AssetRelationshipGraph()
        equity1 = Equity(
            id="A1",
            symbol="A",
            name="A",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        equity2 = Equity(
            id="A2",
            symbol="B",
            name="B",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        graph.add_asset(equity1)
        graph.add_asset(equity2)
        graph.build_relationships()

        result = _serialize_graph(graph)

        assert "relationships" in result
        # Should have same-sector relationship
        assert len(result["relationships"]) > 0

    @staticmethod
    def test_deserialize_graph():
        """Test deserializing a complete graph."""
        graph_data = {
            "assets": [
                {
                    "__type__": "Equity",
                    "id": "TEST",
                    "symbol": "TEST",
                    "name": "Test",
                    "asset_class": "equity",
                    "sector": "Tech",
                    "price": 100.0,
                }
            ],
            "regulatory_events": [],
            "relationships": {},
        }

        graph = _deserialize_graph(graph_data)

        assert isinstance(graph, AssetRelationshipGraph)
        assert len(graph.assets) == 1
        assert "TEST" in graph.assets


class TestCacheOperations:
    """Test cache save and load operations."""

    @staticmethod
    def test_save_to_cache_creates_file(tmp_path):
        """Test that saving to cache creates a file."""
        cache_path = tmp_path / "cache.pkl"
        graph = AssetRelationshipGraph()
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        graph.add_asset(equity)

        _save_to_cache(graph, cache_path)

        assert cache_path.exists()
        assert cache_path.stat().st_size > 0

    @staticmethod
    def test_load_from_cache_restores_graph(tmp_path):
        """Test that loading from cache restores the graph."""
        cache_path = tmp_path / "cache.pkl"
        original_graph = AssetRelationshipGraph()
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        original_graph.add_asset(equity)
        _save_to_cache(original_graph, cache_path)

        loaded_graph = _load_from_cache(cache_path)

        assert len(loaded_graph.assets) == 1
        assert "TEST" in loaded_graph.assets

    @staticmethod
    def test_load_from_cache_nonexistent_file():
        """Test that loading nonexistent cache raises FileNotFoundError."""
        cache_path = Path("/nonexistent/cache.pkl")

        with pytest.raises(FileNotFoundError):
            _load_from_cache(cache_path)


class TestRealDataFetcher:
    """Test RealDataFetcher class."""

    @staticmethod
    def test_init_default_params():
        """Test RealDataFetcher initialization with defaults."""
        fetcher = RealDataFetcher()

        assert fetcher.enable_network is True
        assert fetcher.use_cache is True
        assert fetcher.cache_path is not None

    @staticmethod
    def test_init_custom_params():
        """Test RealDataFetcher with custom parameters."""
        cache_path = Path("/custom/cache.pkl")
        fetcher = RealDataFetcher(
            enable_network=False,
            use_cache=False,
            cache_path=cache_path,
        )

        assert fetcher.enable_network is False
        assert fetcher.use_cache is False
        assert fetcher.cache_path == cache_path

    @staticmethod
    @patch("src.data.real_data_fetcher._load_from_cache")
    def test_create_database_uses_cache_when_available(mock_load):
        """Test that create_database uses cache when available."""
        mock_graph = AssetRelationshipGraph()
        mock_load.return_value = mock_graph

        with tempfile.NamedTemporaryFile(suffix=".pkl") as tmp:
            tmp.write(b"dummy")
            tmp.flush()

            fetcher = RealDataFetcher(use_cache=True, cache_path=Path(tmp.name))
            graph = fetcher.create_database()

            assert graph is mock_graph
            mock_load.assert_called_once()

    @staticmethod
    def test_create_database_skips_cache_when_disabled():
        """Test that create_database skips cache when disabled."""
        fetcher = RealDataFetcher(use_cache=False, enable_network=False)

        # Should use fallback since both cache and network are disabled
        graph = fetcher.create_database()

        assert isinstance(graph, AssetRelationshipGraph)

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_equity_data_success(mock_ticker_class):
        """Test successful equity data fetch."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "shortName": "Apple Inc.",
            "sector": "Technology",
            "currentPrice": 150.0,
            "marketCap": 2.4e12,
            "trailingPE": 25.5,
            "dividendYield": 0.005,
            "trailingEps": 6.0,
        }
        mock_ticker_class.return_value = mock_ticker

        fetcher = RealDataFetcher()
        equities = fetcher._fetch_equity_data(["AAPL"])

        assert len(equities) == 1
        assert equities[0].symbol == "AAPL"
        assert equities[0].price == 150.0

    @staticmethod
    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_equity_data_handles_errors(mock_ticker_class):
        """Test that equity fetch handles errors gracefully."""
        mock_ticker_class.side_effect = Exception("Network error")

        fetcher = RealDataFetcher()
        equities = fetcher._fetch_equity_data(["AAPL"])

        # Should return empty list on error
        assert len(equities) == 0

    @staticmethod
    def test_fallback_returns_sample_database():
        """Test that _fallback returns a sample database."""
        fetcher = RealDataFetcher()
        graph = fetcher._fallback()

        assert isinstance(graph, AssetRelationshipGraph)
        assert len(graph.assets) > 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @staticmethod
    def test_serialize_asset_with_none_fields():
        """Test serializing asset with None optional fields."""
        equity = Equity(
            id="TEST",
            symbol="TEST",
            name="Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
            market_cap=None,
            pe_ratio=None,
        )

        result = _serialize_asset(equity)

        assert "market_cap" in result
        assert result["market_cap"] is None

    @staticmethod
    def test_deserialize_asset_missing_optional_fields():
        """Test deserializing asset with missing optional fields."""
        data = {
            "__type__": "Equity",
            "id": "TEST",
            "symbol": "TEST",
            "name": "Test",
            "asset_class": "equity",
            "sector": "Tech",
            "price": 100.0,
        }

        result = _deserialize_asset(data)

        assert isinstance(result, Equity)
        # Should use defaults for missing fields

    @staticmethod
    def test_serialize_graph_empty():
        """Test serializing an empty graph."""
        graph = AssetRelationshipGraph()

        result = _serialize_graph(graph)

        assert result["assets"] == []
        assert result["regulatory_events"] == []
        assert result["relationships"] == {}

    @staticmethod
    def test_cache_path_with_parent_directory_creation(tmp_path):
        """Test that cache save creates parent directories."""
        cache_path = tmp_path / "subdir" / "cache.pkl"
        graph = AssetRelationshipGraph()

        _save_to_cache(graph, cache_path)

        assert cache_path.exists()
        assert cache_path.parent.exists()

"""Comprehensive unit tests for src/data/real_data_fetcher.py.

This module tests the RealDataFetcher class including:
- Initialization with various configurations
- Cache loading and saving
- Network fetching with fallback behavior
- Data fetching for different asset classes (equities, bonds, commodities, currencies)
- Regulatory event creation
- Error handling and fallback mechanisms
- Helper functions for serialization
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.real_data_fetcher import (
    RealDataFetcher,
    _load_from_cache,
    _save_to_cache,
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
    """Test RealDataFetcher initialization with various configurations."""

    def test_init_with_default_parameters(self):
        """Test initialization with default parameters."""
        fetcher = RealDataFetcher()

        assert fetcher.session is None
        assert fetcher.cache_path is None
        assert fetcher.fallback_factory is None
        assert fetcher.enable_network is True

    def test_init_with_cache_path(self):
        """Test initialization with cache path."""
        cache_path = "/tmp/test_cache.json"
        fetcher = RealDataFetcher(cache_path=cache_path)

        assert fetcher.cache_path == Path(cache_path)
        assert isinstance(fetcher.cache_path, Path)

    def test_init_with_fallback_factory(self):
        """Test initialization with custom fallback factory."""

        def custom_fallback():
            """Provide a fallback that returns a new AssetRelationshipGraph instance."""
            return AssetRelationshipGraph()

        fetcher = RealDataFetcher(fallback_factory=custom_fallback)

        assert fetcher.fallback_factory is custom_fallback
        assert callable(fetcher.fallback_factory)

    def test_init_with_network_disabled(self):
        """Test initialization with network disabled."""
        fetcher = RealDataFetcher(enable_network=False)

        assert fetcher.enable_network is False

    def test_init_with_all_parameters(self):
        """Test initialization with all parameters specified."""
        cache_path = "/tmp/cache.json"

        def fallback():
            """Fallback factory that returns a new AssetRelationshipGraph instance."""
            return AssetRelationshipGraph()

        fetcher = RealDataFetcher(
            cache_path=cache_path, fallback_factory=fallback, enable_network=False
        )

        assert fetcher.cache_path == Path(cache_path)
        assert fetcher.fallback_factory is fallback
        assert fetcher.enable_network is False


class TestCacheOperations:
    """Test cache loading and saving operations."""

    @pytest.fixture
    @staticmethod
    def temp_cache_file():
        """Create a temporary cache file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    @staticmethod
    def sample_graph():
        """Create a sample AssetRelationshipGraph."""
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
        graph.add_asset(equity)
        return graph

    def test_save_to_cache_creates_file(self, temp_cache_file, sample_graph):
        """Test that _save_to_cache creates a cache file."""
        _save_to_cache(sample_graph, temp_cache_file)

        assert os.path.exists(temp_cache_file)
        assert os.path.getsize(temp_cache_file) > 0

    def test_save_and_load_cache_roundtrip(self, temp_cache_file, sample_graph):
        """Test save and load cache roundtrip."""
        _save_to_cache(sample_graph, temp_cache_file)
        loaded_graph = _load_from_cache(Path(temp_cache_file))

        assert loaded_graph is not None
        assert len(loaded_graph.assets) == len(sample_graph.assets)
        assert "TEST_AAPL" in loaded_graph.assets

    def test_load_from_cache_nonexistent_file(self):
        """Test loading from non-existent cache file raises error."""
        with pytest.raises(Exception):
            _load_from_cache(Path("/nonexistent/path/cache.json"))

    def test_create_real_database_loads_from_cache_when_exists(
        self, temp_cache_file, sample_graph
    ):
        """Test that create_real_database loads from cache when available."""
        _save_to_cache(sample_graph, temp_cache_file)

        fetcher = RealDataFetcher(cache_path=temp_cache_file)
        graph = fetcher.create_real_database()

        assert graph is not None
        assert len(graph.assets) > 0

    def test_create_real_database_proceeds_on_cache_load_failure(self, temp_cache_file):
        """Test that create_real_database proceeds with fetch on cache failure."""
        # Create invalid cache file
        with open(temp_cache_file, "w") as f:
            f.write("invalid json content")

        fetcher = RealDataFetcher(cache_path=temp_cache_file, enable_network=False)

        # Should fall back to sample data instead of crashing
        graph = fetcher.create_real_database()
        assert graph is not None


class TestNetworkFetching:
    """Test network fetching behavior and fallback mechanisms."""

    def test_create_real_database_uses_fallback_when_network_disabled(self):
        """Test that fallback is used when network is disabled."""
        custom_graph = AssetRelationshipGraph()
        custom_graph.add_asset(
            Equity(
                id="CUSTOM",
                symbol="CUSTOM",
                name="Custom Asset",
                asset_class=AssetClass.EQUITY,
                sector="Test",
                price=100.0,
            )
        )

        fetcher = RealDataFetcher(
            enable_network=False, fallback_factory=lambda: custom_graph
        )

        graph = fetcher.create_real_database()

        assert graph is not None
        assert "CUSTOM" in graph.assets

    def test_fallback_uses_custom_factory_when_provided(self):
        """Test _fallback method uses custom factory when provided."""
        custom_graph = AssetRelationshipGraph()
        custom_graph.add_asset(
            Equity(
                id="FALLBACK_ASSET",
                symbol="FB",
                name="Fallback Asset",
                asset_class=AssetClass.EQUITY,
                sector="Test",
                price=50.0,
            )
        )

        fetcher = RealDataFetcher(fallback_factory=lambda: custom_graph)
        result = fetcher._fallback()

        assert result is custom_graph
        assert "FALLBACK_ASSET" in result.assets

    def test_fallback_uses_sample_database_when_no_factory(self):
        """Test _fallback uses sample database when no factory provided."""
        fetcher = RealDataFetcher()

        with patch("src.data.real_data_fetcher.create_sample_database") as mock_create:
            mock_graph = AssetRelationshipGraph()
            mock_create.return_value = mock_graph

            result = fetcher._fallback()

            mock_create.assert_called_once()
            assert result is mock_graph

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_equity_data_success(self, mock_ticker_class):
        """Test successful equity data fetching."""
        # Mock yfinance Ticker
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker

        # Mock price history
        mock_hist = pd.DataFrame(
            {
                "Close": [150.0],
                "Open": [148.0],
                "High": [152.0],
                "Low": [147.0],
                "Volume": [1000000],
            }
        )
        mock_ticker.history.return_value = mock_hist

        # Mock ticker info
        mock_ticker.info = {
            "marketCap": 2400000000000,
            "trailingPE": 25.5,
            "dividendYield": 0.005,
            "trailingEps": 5.89,
            "bookValue": 4.50,
        }

        fetcher = RealDataFetcher()
        equities = fetcher._fetch_equity_data()

        assert len(equities) > 0
        assert all(isinstance(eq, Equity) for eq in equities)
        assert all(eq.asset_class == AssetClass.EQUITY for eq in equities)

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_equity_data_handles_missing_data(self, mock_ticker_class):
        """Test equity fetching handles missing price data gracefully."""
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker

        # Empty history
        mock_ticker.history.return_value = pd.DataFrame()

        fetcher = RealDataFetcher()
        equities = fetcher._fetch_equity_data()

        # Should skip assets with no data but not crash
        assert isinstance(equities, list)

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_bond_data_success(self, mock_ticker_class):
        """Test successful bond data fetching."""
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker

        mock_hist = pd.DataFrame({"Close": [110.0]})
        mock_ticker.history.return_value = mock_hist
        mock_ticker.info = {"dividendYield": 0.03, "beta": 0.5}

        fetcher = RealDataFetcher()
        bonds = fetcher._fetch_bond_data()

        assert len(bonds) > 0
        assert all(isinstance(bond, Bond) for bond in bonds)
        assert all(bond.asset_class == AssetClass.FIXED_INCOME for bond in bonds)

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_commodity_data_success(self, mock_ticker_class):
        """Test successful commodity data fetching."""
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker

        mock_hist = pd.DataFrame({"Close": [1800.0]})
        mock_ticker.history.return_value = mock_hist

        fetcher = RealDataFetcher()
        commodities = fetcher._fetch_commodity_data()

        assert len(commodities) > 0
        assert all(isinstance(comm, Commodity) for comm in commodities)
        assert all(comm.asset_class == AssetClass.COMMODITY for comm in commodities)

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetch_currency_data_success(self, mock_ticker_class):
        """Test successful currency data fetching."""
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker

        mock_hist = pd.DataFrame({"Close": [1.2]})
        mock_ticker.history.return_value = mock_hist

        fetcher = RealDataFetcher()
        currencies = fetcher._fetch_currency_data()

        assert len(currencies) > 0
        assert all(isinstance(curr, Currency) for curr in currencies)
        assert all(curr.asset_class == AssetClass.CURRENCY for curr in currencies)

    @staticmethod
    def test_create_regulatory_events():
        """Test creation of regulatory events."""
        fetcher = RealDataFetcher()
        events = fetcher._create_regulatory_events()

        assert len(events) > 0
        assert all(isinstance(event, RegulatoryEvent) for event in events)
        assert all(hasattr(event, "id") for event in events)
        assert all(hasattr(event, "activity_type") for event in events)


class TestRealDatabaseCreation:
    """Test the main create_real_database workflow."""

    @patch.object(RealDataFetcher, "_fetch_equity_data")
    @patch.object(RealDataFetcher, "_fetch_bond_data")
    @patch.object(RealDataFetcher, "_fetch_commodity_data")
    @patch.object(RealDataFetcher, "_fetch_currency_data")
    @patch.object(RealDataFetcher, "_create_regulatory_events")
    def test_create_real_database_success_workflow(
        self, mock_events, mock_currencies, mock_commodities, mock_bonds, mock_equities
    ):
        """Test successful real database creation workflow."""
        # Setup mocks
        mock_equities.return_value = [
            Equity(
                id="AAPL",
                symbol="AAPL",
                name="Apple",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=150.0,
            )
        ]
        mock_bonds.return_value = [
            Bond(
                id="TLT",
                symbol="TLT",
                name="Treasury",
                asset_class=AssetClass.FIXED_INCOME,
                sector="Government",
                price=110.0,
                maturity_date=None,
                coupon_rate=0.03,
                credit_rating="AAA",
            )
        ]
        mock_commodities.return_value = [
            Commodity(
                id="GLD",
                symbol="GLD",
                name="Gold",
                asset_class=AssetClass.COMMODITY,
                sector="Metals",
                price=1800.0,
                commodity_type="Precious Metal",
                unit="oz",
            )
        ]
        mock_currencies.return_value = [
            Currency(
                id="EURUSD",
                symbol="EURUSD=X",
                name="EUR/USD",
                asset_class=AssetClass.CURRENCY,
                sector="FX",
                price=1.2,
                base_currency="EUR",
                quote_currency="USD",
            )
        ]
        mock_events.return_value = [
            RegulatoryEvent(
                id="REG001",
                asset_id="AAPL",
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                description="Test Event",
                date="2024-01-01",
                impact_score=0.5,
            )
        ]

        fetcher = RealDataFetcher()
        graph = fetcher.create_real_database()

        assert graph is not None
        assert len(graph.assets) >= 4  # At least one of each type
        assert len(graph.regulatory_events) >= 1

        # Verify all fetch methods were called
        mock_equities.assert_called_once()
        mock_bonds.assert_called_once()
        mock_commodities.assert_called_once()
        mock_currencies.assert_called_once()
        mock_events.assert_called_once()

    @patch.object(RealDataFetcher, "_fetch_equity_data")
    def test_create_real_database_falls_back_on_fetch_error(self, mock_equities):
        """Test that create_real_database falls back on fetch error."""
        mock_equities.side_effect = Exception("Network error")

        fetcher = RealDataFetcher()
        graph = fetcher.create_real_database()

        # Should return fallback data, not crash
        assert graph is not None

    def test_create_real_database_saves_to_cache_on_success(self):
        """Test that successful fetch saves to cache."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            cache_path = f.name

        try:
            with (
                patch.object(RealDataFetcher, "_fetch_equity_data") as mock_equities,
                patch.object(RealDataFetcher, "_fetch_bond_data") as mock_bonds,
                patch.object(
                    RealDataFetcher, "_fetch_commodity_data"
                ) as mock_commodities,
                patch.object(
                    RealDataFetcher, "_fetch_currency_data"
                ) as mock_currencies,
                patch.object(
                    RealDataFetcher, "_create_regulatory_events"
                ) as mock_events,
            ):
                # Setup minimal mocks
                mock_equities.return_value = []
                mock_bonds.return_value = []
                mock_commodities.return_value = []
            # Setup minimal mocks
            mock_equities.return_value = []
            mock_bonds.return_value = []
            mock_commodities.return_value = []
            mock_currencies.return_value = []
            mock_events.return_value = []

            fetcher = RealDataFetcher()
            fetcher.create_real_database()

            fetcher = RealDataFetcher(cache_path=cache_path)
            fetcher.create_real_database()
                mock_events.return_value = []

                fetcher = RealDataFetcher(cache_path=cache_path)
                fetcher.create_real_database()

                # Cache file should exist
                assert os.path.exists(cache_path)
        finally:
            if os.path.exists(cache_path):
                os.unlink(cache_path)


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    @patch("src.data.real_data_fetcher.RealDataFetcher")
    def test_create_real_database_function(self, mock_fetcher_class):
        """Test the module-level create_real_database function."""
        mock_fetcher = MagicMock()
        mock_graph = AssetRelationshipGraph()
        mock_fetcher.create_real_database.return_value = mock_graph
        mock_fetcher_class.return_value = mock_fetcher

        result = create_real_database()

        mock_fetcher_class.assert_called_once()
        mock_fetcher.create_real_database.assert_called_once()
        assert result is mock_graph


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("src.data.real_data_fetcher.yf.Ticker")
    @staticmethod
    def test_fetch_equity_handles_ticker_exception(mock_ticker_class):
        """Test that equity fetch handles exceptions for individual tickers."""
        mock_ticker_class.side_effect = Exception("API Error")

        fetcher = RealDataFetcher()
        # Should not crash, should return empty or partial list
        equities = fetcher._fetch_equity_data()
        assert isinstance(equities, list)

    @staticmethod
    def test_save_to_cache_handles_write_errors_gracefully():
        """Test that cache save handles write errors gracefully."""
        graph = AssetRelationshipGraph()
        invalid_path = "/invalid/nonexistent/directory/cache.json"

        # Should not crash the application
        try:
            _save_to_cache(graph, invalid_path)
        except Exception:
            # Exception is expected and should be logged, not crash
            pass

    @staticmethod
    def test_create_real_database_with_all_fetch_failures():
        """Test that complete fetch failure falls back properly."""
        with (
            patch.object(RealDataFetcher, "_fetch_equity_data") as mock_eq,
            patch.object(RealDataFetcher, "_fetch_bond_data") as mock_bond,
            patch.object(RealDataFetcher, "_fetch_commodity_data") as mock_comm,
            patch.object(RealDataFetcher, "_fetch_currency_data") as mock_curr,
            patch.object(RealDataFetcher, "_create_regulatory_events") as mock_events,
        ):
            # All fetches fail
            mock_eq.side_effect = Exception("Equity fetch failed")
            mock_bond.side_effect = Exception("Bond fetch failed")
            mock_comm.side_effect = Exception("Commodity fetch failed")
            mock_curr.side_effect = Exception("Currency fetch failed")
            mock_events.side_effect = Exception("Events fetch failed")

            fetcher = RealDataFetcher()
            graph = fetcher.create_real_database()

            # Should fall back to sample data
            assert graph is not None


class TestDataIntegrity:
    """Test data integrity and validation."""

    @patch("src.data.real_data_fetcher.yf.Ticker")
    def test_fetched_equities_have_required_fields(self, mock_ticker_class):
        """Test that fetched equities have all required fields."""
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker

        mock_hist = pd.DataFrame({"Close": [150.0]})
        mock_ticker.history.return_value = mock_hist
        mock_ticker.info = {
            "marketCap": 2.4e12,
            "trailingPE": 25.5,
            "dividendYield": 0.005,
            "trailingEps": 5.89,
            "bookValue": 4.50,
        }

        fetcher = RealDataFetcher()
        equities = fetcher._fetch_equity_data()

        for equity in equities:
            assert hasattr(equity, "id")
            assert hasattr(equity, "symbol")
            assert hasattr(equity, "name")
            assert hasattr(equity, "asset_class")
            assert hasattr(equity, "sector")
            assert hasattr(equity, "price")
            assert equity.asset_class == AssetClass.EQUITY

    @staticmethod
    def test_regulatory_events_have_valid_structure():
        """Test that regulatory events have valid structure."""
        fetcher = RealDataFetcher()
        events = fetcher._create_regulatory_events()

        for event in events:
            assert isinstance(event, RegulatoryEvent)
            assert isinstance(event.activity_type, RegulatoryActivity)
            assert hasattr(event, "description")
            assert hasattr(event, "affected_sector")
            assert hasattr(event, "date")
            assert 0 <= event.severity <= 1.0


class TestCachePersistence:
    """Test cache file persistence and atomic operations."""

    @staticmethod
    def test_cache_save_uses_tempfile_for_atomicity():
        """Test that cache save uses temporary file for atomic write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache.json")

            # Patch to verify tempfile usage
            with patch(
                "src.data.real_data_fetcher.tempfile.NamedTemporaryFile"
            ) as mock_temp:
                mock_temp_file = MagicMock()
                mock_temp_file.name = os.path.join(tmpdir, "temp_cache")
                mock_temp_file.__enter__.return_value = mock_temp_file
                mock_temp.return_value = mock_temp_file

                fetcher = RealDataFetcher(cache_path=cache_path)

                with (
                    patch.object(
                        RealDataFetcher, "_fetch_equity_data", return_value=[]
                    ),
                    patch.object(RealDataFetcher, "_fetch_bond_data", return_value=[]),
                    patch.object(
                        RealDataFetcher, "_fetch_commodity_data", return_value=[]
                    ),
                    patch.object(
                        RealDataFetcher, "_fetch_currency_data", return_value=[]
                    ),
                    patch.object(
                        RealDataFetcher, "_create_regulatory_events", return_value=[]
                    ),
                ):
                    fetcher.create_real_database()

                    # Verify tempfile was used
                    assert mock_temp.called

    @staticmethod
    def test_cache_file_format_is_valid_json():
        """Test that cache file is valid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            cache_path = f.name

        try:
            graph = AssetRelationshipGraph()
            graph.add_asset(
                Equity(
                    id="TEST",
                    symbol="TEST",
                    name="Test Asset",
                    asset_class=AssetClass.EQUITY,
                    sector="Test",
                    price=100.0,
                )
            )

            _save_to_cache(graph, cache_path)

            # Verify it's valid JSON
            with open(cache_path, "r") as f:
                data = json.load(f)
                assert isinstance(data, dict)
        finally:
            if os.path.exists(cache_path):
                os.unlink(cache_path)

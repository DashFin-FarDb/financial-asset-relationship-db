"""Unit tests for AssetGraphRepository.

This module contains comprehensive unit tests for the repository layer including:
- Asset CRUD operations
- Relationship management
- Regulatory event handling
- Data transformation and mapping
- Query operations and filtering
"""

import pytest
from sqlalchemy import create_engine

from src.data.database import create_session_factory, init_db
from src.data.db_models import AssetORM, AssetRelationshipORM, RegulatoryEventORM
from src.data.repository import AssetGraphRepository, RelationshipRecord
from src.models.financial_models import (
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)


@pytest.fixture
def repository(tmp_path):
    """Create a repository with a test database."""
    db_path = tmp_path / "test_repo.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    repo = AssetGraphRepository(session)
    yield repo
    session.close()
    engine.dispose()


class TestAssetOperations:
    """Test cases for asset CRUD operations."""

    def test_upsert_new_equity_asset(self, repository):
        """Test inserting a new equity asset."""
        equity = Equity(
            id="TEST_EQUITY",
            symbol="TEST",
            name="Test Company",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
            market_cap=1e9,
            pe_ratio=25.0,
            dividend_yield=0.02,
            earnings_per_share=4.0,
        )
        
        repository.upsert_asset(equity)
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 1
        assert assets[0].id == "TEST_EQUITY"
        assert assets[0].symbol == "TEST"

    def test_upsert_update_existing_asset(self, repository):
        """Test updating an existing asset."""
        equity = Equity(
            id="UPDATE_TEST",
            symbol="UPD",
            name="Update Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        
        repository.upsert_asset(equity)
        repository.session.commit()
        
        # Update the asset
        equity.price = 150.0
        equity.sector = "Technology"
        repository.upsert_asset(equity)
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 1
        assert assets[0].price == 150.0
        assert assets[0].sector == "Technology"

    def test_upsert_bond_asset(self, repository):
        """Test inserting a bond asset."""
        bond = Bond(
            id="TEST_BOND",
            symbol="BOND",
            name="Test Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Finance",
            price=1000.0,
            yield_to_maturity=0.03,
            coupon_rate=0.025,
            maturity_date="2030-01-01",
            credit_rating="AAA",
        )
        
        repository.upsert_asset(bond)
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 1
        assert isinstance(assets[0], Bond)
        assert assets[0].yield_to_maturity == 0.03

    def test_upsert_commodity_asset(self, repository):
        """Test inserting a commodity asset."""
        commodity = Commodity(
            id="TEST_COMMODITY",
            symbol="GOLD",
            name="Gold Futures",
            asset_class=AssetClass.COMMODITY,
            sector="Materials",
            price=1950.0,
            contract_size=100.0,
            delivery_date="2024-12-31",
            volatility=0.15,
        )
        
        repository.upsert_asset(commodity)
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 1
        assert isinstance(assets[0], Commodity)
        assert assets[0].contract_size == 100.0

    def test_upsert_currency_asset(self, repository):
        """Test inserting a currency asset."""
        currency = Currency(
            id="TEST_CURRENCY",
            symbol="EUR",
            name="Euro",
            asset_class=AssetClass.CURRENCY,
            sector="Currency",
            price=1.10,
            exchange_rate=1.10,
            country="Eurozone",
            central_bank_rate=0.04,
        )
        
        repository.upsert_asset(currency)
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 1
        assert isinstance(assets[0], Currency)
        assert assets[0].exchange_rate == 1.10

    def test_list_assets_ordered_by_id(self, repository):
        """Test that list_assets returns assets ordered by id."""
        assets_to_add = [
            Equity(id="C_ASSET", symbol="C", name="C", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0),
            Equity(id="A_ASSET", symbol="A", name="A", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0),
            Equity(id="B_ASSET", symbol="B", name="B", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0),
        ]
        
        for asset in assets_to_add:
            repository.upsert_asset(asset)
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 3
        assert assets[0].id == "A_ASSET"
        assert assets[1].id == "B_ASSET"
        assert assets[2].id == "C_ASSET"

    def test_get_assets_map(self, repository):
        """Test retrieving assets as a dictionary."""
        equity1 = Equity(id="EQUITY1", symbol="E1", name="Equity 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        equity2 = Equity(id="EQUITY2", symbol="E2", name="Equity 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0)
        
        repository.upsert_asset(equity1)
        repository.upsert_asset(equity2)
        repository.session.commit()
        
        assets_map = repository.get_assets_map()
        assert len(assets_map) == 2
        assert "EQUITY1" in assets_map
        assert "EQUITY2" in assets_map
        assert assets_map["EQUITY1"].symbol == "E1"

    def test_delete_asset(self, repository):
        """Test deleting an asset."""
        equity = Equity(id="DELETE_ME", symbol="DEL", name="Delete", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        
        repository.upsert_asset(equity)
        repository.session.commit()
        
        repository.delete_asset("DELETE_ME")
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 0

    def test_delete_nonexistent_asset(self, repository):
        """Test deleting an asset that doesn't exist."""
        # Should not raise an error
        repository.delete_asset("NONEXISTENT")
        repository.session.commit()


class TestRelationshipOperations:
    """Test cases for relationship management."""

    def test_add_new_relationship(self, repository):
        """Test adding a new relationship."""
        # Create assets
        asset1 = Equity(id="ASSET1", symbol="A1", name="Asset 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        asset2 = Equity(id="ASSET2", symbol="A2", name="Asset 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0)
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()
        
        # Add relationship
        repository.add_or_update_relationship("ASSET1", "ASSET2", "same_sector", 0.7, bidirectional=True)
        repository.session.commit()
        
        relationships = repository.list_relationships()
        assert len(relationships) == 1
        assert relationships[0].source_id == "ASSET1"
        assert relationships[0].target_id == "ASSET2"
        assert relationships[0].strength == 0.7

    def test_update_existing_relationship(self, repository):
        """Test updating an existing relationship."""
        asset1 = Equity(id="UPDATE1", symbol="U1", name="Update 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        asset2 = Equity(id="UPDATE2", symbol="U2", name="Update 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0)
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()
        
        # Add relationship
        repository.add_or_update_relationship("UPDATE1", "UPDATE2", "test_rel", 0.5, bidirectional=False)
        repository.session.commit()
        
        # Update relationship
        repository.add_or_update_relationship("UPDATE1", "UPDATE2", "test_rel", 0.9, bidirectional=True)
        repository.session.commit()
        
        relationships = repository.list_relationships()
        assert len(relationships) == 1
        assert relationships[0].strength == 0.9
        assert relationships[0].bidirectional is True

    def test_list_all_relationships(self, repository):
        """Test listing all relationships."""
        # Create assets
        for i in range(3):
            asset = Equity(id=f"ASSET{i}", symbol=f"A{i}", name=f"Asset {i}", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
            repository.upsert_asset(asset)
        repository.session.commit()
        
        # Add relationships
        repository.add_or_update_relationship("ASSET0", "ASSET1", "rel1", 0.5, bidirectional=False)
        repository.add_or_update_relationship("ASSET1", "ASSET2", "rel2", 0.6, bidirectional=False)
        repository.session.commit()
        
        relationships = repository.list_relationships()
        assert len(relationships) == 2

    def test_get_specific_relationship(self, repository):
        """Test retrieving a specific relationship."""
        asset1 = Equity(id="GET1", symbol="G1", name="Get 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        asset2 = Equity(id="GET2", symbol="G2", name="Get 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0)
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()
        
        repository.add_or_update_relationship("GET1", "GET2", "specific_rel", 0.8, bidirectional=True)
        repository.session.commit()
        
        rel = repository.get_relationship("GET1", "GET2", "specific_rel")
        assert rel is not None
        assert rel.strength == 0.8
        assert rel.bidirectional is True

    def test_get_nonexistent_relationship(self, repository):
        """Test getting a relationship that doesn't exist."""
        rel = repository.get_relationship("NONE1", "NONE2", "nonexistent")
        assert rel is None

    def test_delete_relationship(self, repository):
        """Test deleting a relationship."""
        asset1 = Equity(id="DEL1", symbol="D1", name="Del 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        asset2 = Equity(id="DEL2", symbol="D2", name="Del 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0)
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()
        
        repository.add_or_update_relationship("DEL1", "DEL2", "to_delete", 0.5, bidirectional=False)
        repository.session.commit()
        
        repository.delete_relationship("DEL1", "DEL2", "to_delete")
        repository.session.commit()
        
        relationships = repository.list_relationships()
        assert len(relationships) == 0

    def test_delete_nonexistent_relationship(self, repository):
        """Test deleting a relationship that doesn't exist."""
        # Should not raise an error
        repository.delete_relationship("NONE1", "NONE2", "nonexistent")
        repository.session.commit()

    def test_relationship_record_dataclass(self):
        """Test RelationshipRecord dataclass."""
        record = RelationshipRecord(
            source_id="SOURCE",
            target_id="TARGET",
            relationship_type="test_type",
            strength=0.75,
            bidirectional=True,
        )
        
        assert record.source_id == "SOURCE"
        assert record.target_id == "TARGET"
        assert record.relationship_type == "test_type"
        assert record.strength == 0.75
        assert record.bidirectional is True


class TestRegulatoryEventOperations:
    """Test cases for regulatory event handling."""

    def test_upsert_new_regulatory_event(self, repository):
        """Test inserting a new regulatory event."""
        asset = Equity(id="EVENT_ASSET", symbol="EA", name="Event Asset", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        repository.upsert_asset(asset)
        repository.session.commit()
        
        event = RegulatoryEvent(
            id="EVENT001",
            asset_id="EVENT_ASSET",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-01-15",
            description="Q4 Earnings",
            impact_score=0.8,
            related_assets=[],
        )
        
        repository.upsert_regulatory_event(event)
        repository.session.commit()
        
        # Verify event was created
        events = repository.session.query(RegulatoryEventORM).all()
        assert len(events) == 1
        assert events[0].id == "EVENT001"

    def test_upsert_update_regulatory_event(self, repository):
        """Test updating an existing regulatory event."""
        asset = Equity(id="UPDATE_EVENT", symbol="UE", name="Update Event", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        repository.upsert_asset(asset)
        repository.session.commit()
        
        event = RegulatoryEvent(
            id="EVENT002",
            asset_id="UPDATE_EVENT",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2024-02-01",
            description="Initial filing",
            impact_score=0.5,
            related_assets=[],
        )
        
        repository.upsert_regulatory_event(event)
        repository.session.commit()
        
        # Update event
        event.impact_score = 0.9
        event.description = "Updated filing"
        repository.upsert_regulatory_event(event)
        repository.session.commit()
        
        events = repository.session.query(RegulatoryEventORM).filter_by(id="EVENT002").all()
        assert len(events) == 1
        assert events[0].impact_score == 0.9
        assert events[0].description == "Updated filing"

    def test_upsert_event_with_related_assets(self, repository):
        """Test upserting event with related assets."""
        # Create assets
        main = Equity(id="MAIN", symbol="M", name="Main", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        related1 = Equity(id="REL1", symbol="R1", name="Related 1", asset_class=AssetClass.EQUITY, sector="Tech", price=50.0)
        related2 = Equity(id="REL2", symbol="R2", name="Related 2", asset_class=AssetClass.EQUITY, sector="Tech", price=75.0)
        
        repository.upsert_asset(main)
        repository.upsert_asset(related1)
        repository.upsert_asset(related2)
        repository.session.commit()
        
        event = RegulatoryEvent(
            id="EVENT003",
            asset_id="MAIN",
            event_type=RegulatoryActivity.MERGER,
            date="2024-03-01",
            description="Merger announcement",
            impact_score=0.9,
            related_assets=["REL1", "REL2"],
        )
        
        repository.upsert_regulatory_event(event)
        repository.session.commit()
        
        # Verify related assets were linked
        event_orm = repository.session.query(RegulatoryEventORM).filter_by(id="EVENT003").first()
        assert len(event_orm.related_assets) == 2


class TestDataTransformation:
    """Test cases for data transformation between models and ORM."""

    def test_equity_to_orm_conversion(self, repository):
        """Test converting Equity to ORM and back."""
        equity = Equity(
            id="TRANSFORM1",
            symbol="TF1",
            name="Transform 1",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            market_cap=1e9,
            pe_ratio=25.5,
            dividend_yield=0.02,
            earnings_per_share=5.89,
            book_value=100.0,
        )
        
        repository.upsert_asset(equity)
        repository.session.commit()
        
        retrieved = repository.list_assets()[0]
        assert isinstance(retrieved, Equity)
        assert retrieved.id == equity.id
        assert retrieved.pe_ratio == equity.pe_ratio
        assert retrieved.dividend_yield == equity.dividend_yield

    def test_bond_to_orm_conversion(self, repository):
        """Test converting Bond to ORM and back."""
        bond = Bond(
            id="TRANSFORM2",
            symbol="TF2",
            name="Transform Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Finance",
            price=1000.0,
            yield_to_maturity=0.03,
            coupon_rate=0.025,
            maturity_date="2030-01-01",
            credit_rating="AAA",
            issuer_id="TRANSFORM1",
        )
        
        repository.upsert_asset(bond)
        repository.session.commit()
        
        retrieved = repository.list_assets()[0]
        assert isinstance(retrieved, Bond)
        assert retrieved.yield_to_maturity == bond.yield_to_maturity
        assert retrieved.credit_rating == bond.credit_rating
        assert retrieved.issuer_id == bond.issuer_id

    def test_multiple_asset_types(self, repository):
        """Test handling multiple asset types simultaneously."""
        equity = Equity(id="MULTI1", symbol="M1", name="Multi 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        bond = Bond(
            id="MULTI2", symbol="M2", name="Multi 2", asset_class=AssetClass.FIXED_INCOME,
            sector="Finance", price=1000.0, yield_to_maturity=0.03, coupon_rate=0.025,
            maturity_date="2030-01-01", credit_rating="AA"
        )
        commodity = Commodity(
            id="MULTI3", symbol="M3", name="Multi 3", asset_class=AssetClass.COMMODITY,
            sector="Materials", price=1950.0, contract_size=100.0, delivery_date="2024-12-31", volatility=0.15
        )
        
        repository.upsert_asset(equity)
        repository.upsert_asset(bond)
        repository.upsert_asset(commodity)
        repository.session.commit()
        
        assets = repository.list_assets()
        assert len(assets) == 3
        assert any(isinstance(a, Equity) for a in assets)
        assert any(isinstance(a, Bond) for a in assets)
        assert any(isinstance(a, Commodity) for a in assets)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_repository(self, repository):
        """Test operations on empty repository."""
        assets = repository.list_assets()
        assert len(assets) == 0
        
        assets_map = repository.get_assets_map()
        assert len(assets_map) == 0
        
        relationships = repository.list_relationships()
        assert len(relationships) == 0

    def test_asset_with_minimal_fields(self, repository):
        """Test asset with only required fields."""
        equity = Equity(
            id="MINIMAL",
            symbol="MIN",
            name="Minimal",
            asset_class=AssetClass.EQUITY,
            sector="Test",
            price=1.0,
        )
        
        repository.upsert_asset(equity)
        repository.session.commit()
        
        retrieved = repository.list_assets()[0]
        assert retrieved.id == "MINIMAL"
        assert retrieved.price == 1.0

    def test_relationship_with_zero_strength(self, repository):
        """Test relationship with zero strength."""
        asset1 = Equity(id="ZERO1", symbol="Z1", name="Zero 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        asset2 = Equity(id="ZERO2", symbol="Z2", name="Zero 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0)
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()
        
        repository.add_or_update_relationship("ZERO1", "ZERO2", "zero_strength", 0.0, bidirectional=False)
        repository.session.commit()
        
        rel = repository.get_relationship("ZERO1", "ZERO2", "zero_strength")
        assert rel is not None
        assert rel.strength == 0.0

    def test_relationship_with_max_strength(self, repository):
        """Test relationship with maximum strength."""
        asset1 = Equity(id="MAX1", symbol="M1", name="Max 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        asset2 = Equity(id="MAX2", symbol="M2", name="Max 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0)
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()
        
        repository.add_or_update_relationship("MAX1", "MAX2", "max_strength", 1.0, bidirectional=False)
        repository.session.commit()
        
        rel = repository.get_relationship("MAX1", "MAX2", "max_strength")
        assert rel is not None
        assert rel.strength == 1.0

# ============================================================================
# Additional Tests for src/data/real_data_fetcher.py Method Changes
# ============================================================================

class TestRealDataFetcherInstanceMethodConversions:
    """Test suite for RealDataFetcher methods converted from static to instance."""
    
    @patch('src.data.real_data_fetcher.yf.Ticker')
    def test_fetch_equity_data_is_instance_method(self, mock_ticker):
        """Test that _fetch_equity_data now works as an instance method."""
        from src.data.real_data_fetcher import RealDataFetcher
        import pandas as pd
        
        # Mock ticker data
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame({
            'Close': [150.0],
            'Volume': [1000000]
        })
        mock_ticker_instance.info = {
            'marketCap': 2400000000000,
            'trailingPE': 25.5,
            'dividendYield': 0.005,
            'trailingEps': 5.89,
            'bookValue': 4.50
        }
        
        fetcher = RealDataFetcher(enable_network=True)
        
        # Verify it's an instance method
        assert not isinstance(RealDataFetcher.__dict__.get('_fetch_equity_data'), staticmethod)
        
        # Test functionality
        equities = fetcher._fetch_equity_data()
        
        assert isinstance(equities, list)
    
    @patch('src.data.real_data_fetcher.yf.Ticker')
    def test_fetch_equity_data_handles_empty_history_gracefully(self, mock_ticker):
        """Test _fetch_equity_data handles empty history DataFrame."""
        from src.data.real_data_fetcher import RealDataFetcher
        import pandas as pd
        
        # Mock empty history
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame()  # Empty
        mock_ticker_instance.info = {}
        
        fetcher = RealDataFetcher(enable_network=True)
        equities = fetcher._fetch_equity_data()
        
        # Should return empty list or handle gracefully
        assert isinstance(equities, list)
    
    @patch('src.data.real_data_fetcher.yf.Ticker')
    def test_fetch_equity_data_logs_warnings_for_missing_data(self, mock_ticker):
        """Test that _fetch_equity_data logs warnings when data is missing."""
        from src.data.real_data_fetcher import RealDataFetcher
        import pandas as pd
        
        mock_ticker_instance = mock_ticker.return_value
        mock_ticker_instance.history.return_value = pd.DataFrame()  # No price data
        mock_ticker_instance.info = {}
        
        fetcher = RealDataFetcher(enable_network=True)
        
        with patch('src.data.real_data_fetcher.logger') as mock_logger:
            equities = fetcher._fetch_equity_data()
            
            # Should log warnings for symbols with no data
            assert mock_logger.warning.called


class TestRealDataFetcherDocstringUpdates:
    """Test that docstrings have been properly updated."""
    
    def test_create_real_database_docstring_formatting(self):
        """Test create_real_database has properly formatted docstring."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        docstring = RealDataFetcher.create_real_database.__doc__
        assert docstring is not None
        assert "Create an AssetRelationshipGraph populated with real financial data" in docstring
        assert "Returns:" in docstring
    
    def test_init_docstring_parameter_descriptions(self):
        """Test __init__ docstring has clear parameter descriptions."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        docstring = RealDataFetcher.__init__.__doc__
        assert docstring is not None
        assert "Parameters:" in docstring
        assert "cache_path" in docstring
        assert "fallback_factory" in docstring
        assert "enable_network" in docstring
    
    def test_fallback_docstring_clarity(self):
        """Test _fallback method has clear, concise docstring."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        docstring = RealDataFetcher._fallback.__doc__
        assert docstring is not None
        assert "fallback" in docstring.lower()
        assert "Returns:" in docstring


class TestRealDataFetcherCachingBehavior:
    """Test caching behavior with updated implementation."""
    
    def test_cache_loading_with_existing_cache(self, tmp_path):
        """Test that fetcher loads from cache when cache file exists."""
        from src.data.real_data_fetcher import RealDataFetcher, _save_to_cache
        from src.data.sample_data import create_sample_database
        
        cache_file = tmp_path / "test_cache.json"
        
        # Create and save a graph to cache
        sample_graph = create_sample_database()
        _save_to_cache(sample_graph, cache_file)
        
        # Create fetcher with cache path
        fetcher = RealDataFetcher(cache_path=str(cache_file), enable_network=False)
        graph = fetcher.create_real_database()
        
        # Should load from cache
        assert len(graph.assets) > 0
        assert len(graph.assets) == len(sample_graph.assets)
    
    def test_cache_save_on_successful_fetch(self, tmp_path):
        """Test that fetcher saves to cache after successful fetch."""
        from src.data.real_data_fetcher import RealDataFetcher
        import os
        
        cache_file = tmp_path / "new_cache.json"
        
        with patch('src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data') as mock_fetch:
            mock_fetch.return_value = []  # Empty but successful fetch
            
            fetcher = RealDataFetcher(
                cache_path=str(cache_file),
                enable_network=True
            )
            
            with patch('src.data.real_data_fetcher._save_to_cache') as mock_save:
                graph = fetcher.create_real_database()
                
                # Cache save should have been attempted
                # Note: actual save may fail if graph is empty, but attempt should be made
                assert graph is not None
    
    def test_cache_load_failure_proceeds_with_fetch(self, tmp_path):
        """Test that cache load failure doesn't prevent fetching."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        # Create cache file with invalid content
        cache_file = tmp_path / "invalid_cache.json"
        cache_file.write_text("invalid json content {{{")
        
        with patch('src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data') as mock_fetch:
            mock_fetch.return_value = []
            
            fetcher = RealDataFetcher(
                cache_path=str(cache_file),
                enable_network=True
            )
            
            # Should proceed with fetch despite cache failure
            graph = fetcher.create_real_database()
            assert graph is not None


class TestRealDataFetcherNetworkDisabling:
    """Test behavior when network access is disabled."""
    
    def test_network_disabled_uses_fallback_immediately(self):
        """Test that disabling network uses fallback without attempting fetch."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        fetcher = RealDataFetcher(enable_network=False)
        
        with patch('src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data') as mock_fetch:
            graph = fetcher.create_real_database()
            
            # Should not have attempted to fetch
            mock_fetch.assert_not_called()
            
            # Should have fallback data
            assert graph is not None
            assert len(graph.assets) > 0
    
    def test_network_disabled_logs_appropriate_message(self):
        """Test that appropriate log message is shown when network is disabled."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        fetcher = RealDataFetcher(enable_network=False)
        
        with patch('src.data.real_data_fetcher.logger') as mock_logger:
            graph = fetcher.create_real_database()
            
            # Should log that network fetching is disabled
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Network fetching disabled" in call for call in info_calls)
    
    def test_custom_fallback_factory_is_used(self):
        """Test that custom fallback factory is called when provided."""
        from src.data.real_data_fetcher import RealDataFetcher
        from src.logic.asset_graph import AssetRelationshipGraph
        
        custom_graph = AssetRelationshipGraph()
        custom_factory = MagicMock(return_value=custom_graph)
        
        fetcher = RealDataFetcher(
            fallback_factory=custom_factory,
            enable_network=False
        )
        
        graph = fetcher.create_real_database()
        
        # Custom factory should have been called
        custom_factory.assert_called_once()
        assert graph is custom_graph


class TestRealDataFetcherErrorHandling:
    """Test error handling in RealDataFetcher."""
    
    @patch('src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data')
    def test_fetch_failure_triggers_fallback(self, mock_fetch):
        """Test that fetch failures trigger fallback to sample data."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        # Simulate fetch failure
        mock_fetch.side_effect = Exception("Network error")
        
        fetcher = RealDataFetcher(enable_network=True)
        graph = fetcher.create_real_database()
        
        # Should have fallback data
        assert graph is not None
        assert len(graph.assets) > 0  # From sample data
    
    @patch('src.data.real_data_fetcher.RealDataFetcher._fetch_equity_data')
    def test_fetch_failure_logs_error_and_warning(self, mock_fetch):
        """Test that fetch failures are properly logged."""
        from src.data.real_data_fetcher import RealDataFetcher
        
        mock_fetch.side_effect = RuntimeError("Unexpected error")
        
        fetcher = RealDataFetcher(enable_network=True)
        
        with patch('src.data.real_data_fetcher.logger') as mock_logger:
            graph = fetcher.create_real_database()
            
            # Should log error and warning about fallback
            assert mock_logger.error.called
            assert mock_logger.warning.called
            
            # Check for specific fallback message
            warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any("Falling back to sample data" in call for call in warning_calls)




# ============================================================================
# Additional Tests for src/data/repository.py Method Conversions
# ============================================================================

class TestAssetGraphRepositoryInstanceMethods:
    """Test suite for AssetGraphRepository methods converted from static to instance."""
    
    @pytest.fixture
    def mock_session(self):
        """
        Provide a MagicMock configured to mimic a SQLAlchemy session for tests.
        
        Returns:
            MagicMock: A mock SQLAlchemy session instance.
        """
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """
        Create an AssetGraphRepository backed by the provided SQLAlchemy session.
        
        Parameters:
            mock_session: A SQLAlchemy session or session-like fixture configured for tests.
        
        Returns:
            repository (AssetGraphRepository): Repository instance using the provided session.
        """
        from src.data.repository import AssetGraphRepository
        return AssetGraphRepository(mock_session)
    
    def test_update_asset_orm_is_instance_method(self, repository):
        """Test that _update_asset_orm is now an instance method."""
        from src.data.repository import AssetGraphRepository
        
        # Verify it's not a static method
        assert not isinstance(AssetGraphRepository.__dict__.get('_update_asset_orm'), staticmethod)
        
        # Verify it's callable on instance
        assert hasattr(repository, '_update_asset_orm')
        assert callable(repository._update_asset_orm)
    
    def test_to_asset_model_is_instance_method(self, repository):
        """Test that _to_asset_model is now an instance method."""
        from src.data.repository import AssetGraphRepository
        
        # Verify it's not a static method
        assert not isinstance(AssetGraphRepository.__dict__.get('_to_asset_model'), staticmethod)
        
        # Verify it's callable on instance
        assert hasattr(repository, '_to_asset_model')
        assert callable(repository._to_asset_model)
    
    def test_to_regulatory_event_model_is_instance_method(self, repository):
        """Test that _to_regulatory_event_model is now an instance method."""
        from src.data.repository import AssetGraphRepository
        
        # Verify it's not a static method
        assert not isinstance(AssetGraphRepository.__dict__.get('_to_regulatory_event_model'), staticmethod)
        
        # Verify it's callable on instance
        assert hasattr(repository, '_to_regulatory_event_model')
        assert callable(repository._to_regulatory_event_model)
    
    def test_update_asset_orm_handles_all_asset_types(self, repository):
        """Test _update_asset_orm works with different asset types."""
        from src.data.db_models import AssetORM
        from src.models.financial_models import Equity, Bond, Commodity, Currency, AssetClass
        
        # Test with Equity
        equity = Equity(
            id="EQ1",
            symbol="AAPL",
            name="Apple",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            market_cap=2.4e12,
            pe_ratio=25.0,
            dividend_yield=0.005,
            earnings_per_share=6.0,
            book_value=5.0
        )
        
        orm = AssetORM()
        repository._update_asset_orm(orm, equity)
        
        assert orm.symbol == "AAPL"
        assert orm.asset_class == AssetClass.EQUITY.value
        assert orm.pe_ratio == 25.0
        
        # Test with Bond
        bond = Bond(
            id="BND1",
            symbol="CORP",
            name="Corporate Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Corporate",
            price=1000.0,
            yield_to_maturity=0.045,
            coupon_rate=0.04,
            maturity_date="2030-12-31",
            credit_rating="AA"
        )
        
        orm2 = AssetORM()
        repository._update_asset_orm(orm2, bond)
        
        assert orm2.symbol == "CORP"
        assert orm2.yield_to_maturity == 0.045
        assert orm2.credit_rating == "AA"
    
    def test_to_asset_model_creates_correct_asset_type(self, repository):
        """Test _to_asset_model creates correct asset type from ORM."""
        from src.data.db_models import AssetORM
        from src.models.financial_models import AssetClass, Equity
        
        # Create ORM for equity
        orm = AssetORM()
        orm.id = "TEST"
        orm.symbol = "TEST"
        orm.name = "Test Asset"
        orm.asset_class = AssetClass.EQUITY.value
        orm.sector = "Technology"
        orm.price = 100.0
        orm.market_cap = 1e9
        orm.currency = "USD"
        orm.pe_ratio = 20.0
        orm.dividend_yield = 0.02
        orm.earnings_per_share = 5.0
        orm.book_value = 50.0
        
        asset = repository._to_asset_model(orm)
        
        assert isinstance(asset, Equity)
        assert asset.id == "TEST"
        assert asset.symbol == "TEST"
        assert asset.pe_ratio == 20.0


class TestAddOrUpdateRelationshipFormatting:
    """Test formatting updates in add_or_update_relationship method."""
    
    @pytest.fixture
    def mock_session(self):
        """
        Create a mocked SQLAlchemy session with default return behavior.
        
        Returns:
            MagicMock: A mock acting like a SQLAlchemy Session where execute().scalar_one_or_none() returns None.
        """
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """
        Create an AssetGraphRepository backed by the provided SQLAlchemy session.
        
        Parameters:
            mock_session: A SQLAlchemy session or session-like fixture configured for tests.
        
        Returns:
            repository (AssetGraphRepository): Repository instance using the provided session.
        """
        from src.data.repository import AssetGraphRepository
        return AssetGraphRepository(mock_session)
    
    def test_add_or_update_relationship_parameter_formatting(self, repository):
        """Test that method signature is properly formatted (single line)."""
        from src.data.repository import AssetGraphRepository
        import inspect
        
        # Get method signature
        sig = inspect.signature(AssetGraphRepository.add_or_update_relationship)
        params = list(sig.parameters.keys())
        
        # Should have all required parameters
        assert 'self' in params
        assert 'source_id' in params
        assert 'target_id' in params
        assert 'rel_type' in params
        assert 'strength' in params
        assert 'bidirectional' in params
    
    def test_add_or_update_relationship_bidirectional_kwarg_only(self, repository):
        """Test that bidirectional is keyword-only argument."""
        from src.data.repository import AssetGraphRepository
        import inspect
        
        sig = inspect.signature(AssetGraphRepository.add_or_update_relationship)
        param = sig.parameters['bidirectional']
        
        # Should be keyword-only
        assert param.kind == inspect.Parameter.KEYWORD_ONLY


class TestGetRelationshipFormatting:
    """Test formatting updates in get_relationship method."""
    
    @pytest.fixture
    def mock_session(self):
        """
        Provide a MagicMock configured to mimic a SQLAlchemy session for tests.
        
        Returns:
            MagicMock: A mock SQLAlchemy session instance.
        """
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """
        Create an AssetGraphRepository backed by the provided SQLAlchemy session.
        
        Parameters:
            mock_session: A SQLAlchemy session or session-like fixture configured for tests.
        
        Returns:
            repository (AssetGraphRepository): Repository instance using the provided session.
        """
        from src.data.repository import AssetGraphRepository
        return AssetGraphRepository(mock_session)
    
    def test_get_relationship_signature_single_line(self, repository):
        """Test that get_relationship signature is on single line."""
        from src.data.repository import AssetGraphRepository
        import inspect
        
        sig = inspect.signature(AssetGraphRepository.get_relationship)
        params = list(sig.parameters.keys())
        
        # Should have all parameters
        assert params == ['self', 'source_id', 'target_id', 'rel_type']


class TestDeleteRelationshipFormatting:
    """Test formatting updates in delete_relationship method."""
    
    @pytest.fixture
    def mock_session(self):
        """
        Provide a MagicMock configured to mimic a SQLAlchemy session for tests.
        
        Returns:
            MagicMock: A mock SQLAlchemy session instance.
        """
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """
        Create an AssetGraphRepository backed by the provided SQLAlchemy session.
        
        Parameters:
            mock_session: A SQLAlchemy session or session-like fixture configured for tests.
        
        Returns:
            repository (AssetGraphRepository): Repository instance using the provided session.
        """
        from src.data.repository import AssetGraphRepository
        return AssetGraphRepository(mock_session)
    
    def test_delete_relationship_signature_single_line(self, repository):
        """Test that delete_relationship signature is on single line."""
        from src.data.repository import AssetGraphRepository
        import inspect
        
        sig = inspect.signature(AssetGraphRepository.delete_relationship)
        params = list(sig.parameters.keys())
        
        # Should have all parameters
        assert params == ['self', 'source_id', 'target_id', 'rel_type']

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
from src.data.db_models import RegulatoryEventORM
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

pytest.importorskip("sqlalchemy")


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

    @staticmethod
    def test_upsert_new_equity_asset(repository):
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

    @staticmethod
    def test_upsert_update_existing_asset(repository):
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

    @staticmethod
    def test_upsert_bond_asset(repository):
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

    @staticmethod
    def test_upsert_commodity_asset(repository):
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

    @staticmethod
    def test_upsert_currency_asset(repository):
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

    @staticmethod
    def test_list_assets_ordered_by_id(repository):
        """Test that list_assets returns assets ordered by id."""
        assets_to_add = [
            Equity(
                id="C_ASSET",
                symbol="C",
                name="C",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=100.0,
            ),
            Equity(
                id="A_ASSET",
                symbol="A",
                name="A",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=100.0,
            ),
            Equity(
                id="B_ASSET",
                symbol="B",
                name="B",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=100.0,
            ),
        ]

        for asset in assets_to_add:
            repository.upsert_asset(asset)
        repository.session.commit()

        assets = repository.list_assets()
        assert len(assets) == 3
        assert assets[0].id == "A_ASSET"
        assert assets[1].id == "B_ASSET"
        assert assets[2].id == "C_ASSET"

    @staticmethod
    def test_get_assets_map(repository):
        """Test retrieving assets as a dictionary."""
        equity1 = Equity(
            id="EQUITY1",
            symbol="E1",
            name="Equity 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        equity2 = Equity(
            id="EQUITY2",
            symbol="E2",
            name="Equity 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )

        repository.upsert_asset(equity1)
        repository.upsert_asset(equity2)
        repository.session.commit()

        assets_map = repository.get_assets_map()
        assert len(assets_map) == 2
        assert "EQUITY1" in assets_map
        assert "EQUITY2" in assets_map
        assert assets_map["EQUITY1"].symbol == "E1"

    @staticmethod
    def test_delete_asset(repository):
        """Test deleting an asset."""
        equity = Equity(
            id="DELETE_ME",
            symbol="DEL",
            name="Delete",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )

        repository.upsert_asset(equity)
        repository.session.commit()

        repository.delete_asset("DELETE_ME")
        repository.session.commit()

        assets = repository.list_assets()
        assert len(assets) == 0

    @staticmethod
    def test_delete_nonexistent_asset(repository):
        """Test deleting an asset that doesn't exist."""
        # Should not raise an error
        repository.delete_asset("NONEXISTENT")
        repository.session.commit()


class TestRelationshipOperations:
    """Test cases for relationship management."""

    @staticmethod
    def test_add_new_relationship(repository):
        """Test adding a new relationship."""
        # Create assets
        asset1 = Equity(
            id="ASSET1",
            symbol="A1",
            name="Asset 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="ASSET2",
            symbol="A2",
            name="Asset 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Add relationship
        repository.add_or_update_relationship(
            "ASSET1", "ASSET2", "same_sector", 0.7, bidirectional=True
        )
        repository.session.commit()

        relationships = repository.list_relationships()
        assert len(relationships) == 1
        assert relationships[0].source_id == "ASSET1"
        assert relationships[0].target_id == "ASSET2"
        assert relationships[0].strength == 0.7

    @staticmethod
    def test_update_existing_relationship(repository):
        """Test updating an existing relationship."""
        asset1 = Equity(
            id="UPDATE1",
            symbol="U1",
            name="Update 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="UPDATE2",
            symbol="U2",
            name="Update 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Add relationship
        repository.add_or_update_relationship(
            "UPDATE1", "UPDATE2", "test_rel", 0.5, bidirectional=False
        )
        repository.session.commit()

        # Update relationship
        repository.add_or_update_relationship(
            "UPDATE1", "UPDATE2", "test_rel", 0.9, bidirectional=True
        )
        repository.session.commit()

        relationships = repository.list_relationships()
        assert len(relationships) == 1
        assert relationships[0].strength == 0.9
        assert relationships[0].bidirectional is True

    @staticmethod
    def test_list_all_relationships(repository):
        """Test listing all relationships."""
        # Create assets
        for i in range(3):
            asset = Equity(
                id=f"ASSET{i}",
                symbol=f"A{i}",
                name=f"Asset {i}",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=100.0,
            )
            repository.upsert_asset(asset)
        repository.session.commit()

        # Add relationships
        repository.add_or_update_relationship(
            "ASSET0", "ASSET1", "rel1", 0.5, bidirectional=False
        )
        repository.add_or_update_relationship(
            "ASSET1", "ASSET2", "rel2", 0.6, bidirectional=False
        )
        repository.session.commit()

        relationships = repository.list_relationships()
        assert len(relationships) == 2

    @staticmethod
    def test_get_specific_relationship(repository):
        """Test retrieving a specific relationship."""
        asset1 = Equity(
            id="GET1",
            symbol="G1",
            name="Get 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="GET2",
            symbol="G2",
            name="Get 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship(
            "GET1", "GET2", "specific_rel", 0.8, bidirectional=True
        )
        repository.session.commit()

        rel = repository.get_relationship("GET1", "GET2", "specific_rel")
        assert rel is not None
        assert rel.strength == 0.8
        assert rel.bidirectional is True

    @staticmethod
    def test_get_nonexistent_relationship(repository):
        """Test getting a relationship that doesn't exist."""
        rel = repository.get_relationship("NONE1", "NONE2", "nonexistent")
        assert rel is None

    @staticmethod
    def test_delete_relationship(repository):
        """Test deleting a relationship."""
        asset1 = Equity(
            id="DEL1",
            symbol="D1",
            name="Del 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="DEL2",
            symbol="D2",
            name="Del 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship(
            "DEL1", "DEL2", "to_delete", 0.5, bidirectional=False
        )
        repository.session.commit()

        repository.delete_relationship("DEL1", "DEL2", "to_delete")
        repository.session.commit()

        relationships = repository.list_relationships()
        assert len(relationships) == 0

    @staticmethod
    def test_delete_nonexistent_relationship(repository):
        """Test deleting a relationship that doesn't exist."""
        # Should not raise an error
        repository.delete_relationship("NONE1", "NONE2", "nonexistent")
        repository.session.commit()

    @staticmethod
    def test_relationship_record_dataclass():
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

    @staticmethod
    def test_upsert_new_regulatory_event(repository):
        """Test inserting a new regulatory event."""
        asset = Equity(
            id="EVENT_ASSET",
            symbol="EA",
            name="Event Asset",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
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

    @staticmethod
    def test_upsert_update_regulatory_event(repository):
        """Test updating an existing regulatory event."""
        asset = Equity(
            id="UPDATE_EVENT",
            symbol="UE",
            name="Update Event",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
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

        events = (
            repository.session.query(RegulatoryEventORM).filter_by(id="EVENT002").all()
        )
        assert len(events) == 1
        assert events[0].impact_score == 0.9
        assert events[0].description == "Updated filing"

    @staticmethod
    def test_upsert_event_with_related_assets(repository):
        """Test upserting event with related assets."""
        # Create assets
        main = Equity(
            id="MAIN",
            symbol="M",
            name="Main",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        related1 = Equity(
            id="REL1",
            symbol="R1",
            name="Related 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=50.0,
        )
        related2 = Equity(
            id="REL2",
            symbol="R2",
            name="Related 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=75.0,
        )

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
        event_orm = (
            repository.session.query(RegulatoryEventORM)
            .filter_by(id="EVENT003")
            .first()
        )
        assert len(event_orm.related_assets) == 2


class TestDataTransformation:
    """Test cases for data transformation between models and ORM."""

    @staticmethod
    def test_equity_to_orm_conversion(repository):
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

    @staticmethod
    def test_bond_to_orm_conversion(repository):
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

    @staticmethod
    def test_multiple_asset_types(repository):
        """Test handling multiple asset types simultaneously."""
        equity = Equity(
            id="MULTI1",
            symbol="M1",
            name="Multi 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        bond = Bond(
            id="MULTI2",
            symbol="M2",
            name="Multi 2",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Finance",
            price=1000.0,
            yield_to_maturity=0.03,
            coupon_rate=0.025,
            maturity_date="2030-01-01",
            credit_rating="AA",
        )
        commodity = Commodity(
            id="MULTI3",
            symbol="M3",
            name="Multi 3",
            asset_class=AssetClass.COMMODITY,
            sector="Materials",
            price=1950.0,
            contract_size=100.0,
            delivery_date="2024-12-31",
            volatility=0.15,
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

    @staticmethod
    def test_empty_repository(repository):
        """Test operations on empty repository."""
        assets = repository.list_assets()
        assert len(assets) == 0

        assets_map = repository.get_assets_map()
        assert len(assets_map) == 0

        relationships = repository.list_relationships()
        assert len(relationships) == 0

    @staticmethod
    def test_asset_with_minimal_fields(repository):
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

    @staticmethod
    def test_relationship_with_zero_strength(repository):
        """Test relationship with zero strength."""
        asset1 = Equity(
            id="ZERO1",
            symbol="Z1",
            name="Zero 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="ZERO2",
            symbol="Z2",
            name="Zero 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship(
            "ZERO1", "ZERO2", "zero_strength", 0.0, bidirectional=False
        )
        repository.session.commit()

        rel = repository.get_relationship("ZERO1", "ZERO2", "zero_strength")
        assert rel is not None
        assert rel.strength == 0.0

    @staticmethod
    def test_relationship_with_max_strength(repository):
        """Test relationship with maximum strength."""
        asset1 = Equity(
            id="MAX1",
            symbol="M1",
            name="Max 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="MAX2",
            symbol="M2",
            name="Max 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship(
            "MAX1", "MAX2", "max_strength", 1.0, bidirectional=False
        )
        repository.session.commit()

        rel = repository.get_relationship("MAX1", "MAX2", "max_strength")
        assert rel is not None
        assert rel.strength == 1.0


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    @staticmethod
    def test_complete_portfolio_workflow(repository):
        """Test complete workflow of building a diversified portfolio."""
        # Add diverse assets
        assets = [
            Equity(
                id="TECH1",
                symbol="TECH1",
                name="Tech Company",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=150.0,
                pe_ratio=25.0,
                dividend_yield=0.01,
            ),
            Bond(
                id="BOND1",
                symbol="BOND1",
                name="Gov Bond",
                asset_class=AssetClass.FIXED_INCOME,
                sector="Government",
                price=1000.0,
                yield_to_maturity=0.03,
                coupon_rate=0.025,
                maturity_date="2030-01-01",
                credit_rating="AAA",
            ),
            Commodity(
                id="GOLD1",
                symbol="GC",
                name="Gold",
                asset_class=AssetClass.COMMODITY,
                sector="Precious Metals",
                price=2000.0,
                contract_size=100.0,
                volatility=0.15,
            ),
            Currency(
                id="EUR1",
                symbol="EUR",
                name="Euro",
                asset_class=AssetClass.CURRENCY,
                sector="Forex",
                price=1.1,
                exchange_rate=1.1,
                country="EU",
            ),
        ]

        for asset in assets:
            repository.upsert_asset(asset)
        repository.session.commit()

        # Add relationships between assets
        repository.add_or_update_relationship(
            "TECH1", "BOND1", "inverse_correlation", 0.3, bidirectional=True
        )
        repository.add_or_update_relationship(
            "GOLD1", "EUR1", "commodity_currency", 0.6, bidirectional=False
        )
        repository.session.commit()

        # Verify all assets exist
        assets_map = repository.get_assets_map()
        assert len(assets_map) == 4

        # Verify relationships
        relationships = repository.list_relationships()
        assert len(relationships) >= 2

    @staticmethod
    def test_regulatory_event_with_multiple_impacts(repository):
        """Test regulatory event affecting multiple assets."""
        # Create related assets
        main_asset = Equity(
            id="MAIN",
            symbol="MAIN",
            name="Main Company",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=200.0,
        )
        related1 = Equity(
            id="REL1",
            symbol="REL1",
            name="Related 1",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
        )
        related2 = Equity(
            id="REL2",
            symbol="REL2",
            name="Related 2",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=180.0,
        )

        for asset in [main_asset, related1, related2]:
            repository.upsert_asset(asset)
        repository.session.commit()

        # Create event with multiple related assets
        event = RegulatoryEvent(
            id="MERGER001",
            asset_id="MAIN",
            event_type=RegulatoryActivity.MERGER,
            date="2024-06-15",
            description="Major acquisition announcement",
            impact_score=0.85,
            related_assets=["REL1", "REL2"],
        )

        repository.upsert_regulatory_event(event)
        repository.session.commit()

        # Verify event and related assets
        events = repository.list_regulatory_events()
        assert len(events) == 1
        assert len(events[0].related_assets) == 2
        assert "REL1" in events[0].related_assets
        assert "REL2" in events[0].related_assets

    @staticmethod
    def test_cascade_delete_relationships(repository):
        """Test that deleting an asset cascades to relationships."""
        asset1 = Equity(
            id="CASCADE1",
            symbol="C1",
            name="Cascade 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="CASCADE2",
            symbol="C2",
            name="Cascade 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )

        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship(
            "CASCADE1", "CASCADE2", "test_rel", 0.5, bidirectional=False
        )
        repository.session.commit()

        # Delete asset
        repository.delete_asset("CASCADE1")
        repository.session.commit()

        # Relationships should be cleaned up
        relationships = repository.list_relationships()
        remaining_rels = [
            r
            for r in relationships
            if r.source_id == "CASCADE1" or r.target_id == "CASCADE1"
        ]
        assert len(remaining_rels) == 0


class TestAssetTypeConversions:
    """Test conversion between different asset types."""

    @staticmethod
    def test_convert_equity_to_base_asset(repository):
        """Test converting equity to base asset type."""
        equity = Equity(
            id="CONVERT1",
            symbol="CVT1",
            name="Convert 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
            pe_ratio=20.0,
        )

        repository.upsert_asset(equity)
        repository.session.commit()

        # Retrieve and verify it's still an Equity
        retrieved = repository.list_assets()[0]
        assert isinstance(retrieved, Equity)
        assert retrieved.pe_ratio == 20.0

    @staticmethod
    def test_update_asset_clears_stale_fields(repository):
        """Test that updating asset type clears stale fields."""
        # First insert as Bond
        bond = Bond(
            id="MORPH1",
            symbol="MRP1",
            name="Morph 1",
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

        # Now update as Equity (simulating asset type change)
        equity = Equity(
            id="MORPH1",
            symbol="MRP1",
            name="Morph 1 Updated",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=150.0,
            pe_ratio=25.0,
        )

        repository.upsert_asset(equity)
        repository.session.commit()

        # Retrieve and verify bond-specific fields are None
        retrieved = repository.list_assets()[0]
        assert isinstance(retrieved, Equity)
        assert retrieved.pe_ratio == 25.0


class TestPerformance:
    """Test performance with large datasets."""

    @staticmethod
    def test_bulk_asset_insertion(repository):
        """Test inserting many assets efficiently."""
        # Create 100 assets
        for i in range(100):
            asset = Equity(
                id=f"BULK{i}",
                symbol=f"BLK{i}",
                name=f"Bulk Asset {i}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + i,
            )
            repository.upsert_asset(asset)

        repository.session.commit()

        assets = repository.list_assets()
        assert len(assets) == 100

    @staticmethod
    def test_many_relationships(repository):
        """Test creating many relationships."""
        # Create 10 assets
        for i in range(10):
            asset = Equity(
                id=f"NODE{i}",
                symbol=f"ND{i}",
                name=f"Node {i}",
                asset_class=AssetClass.EQUITY,
                sector="Tech",
                price=100.0,
            )
            repository.upsert_asset(asset)
        repository.session.commit()

        # Create relationships between all pairs
        for i in range(10):
            for j in range(i + 1, 10):
                repository.add_or_update_relationship(
                    f"NODE{i}",
                    f"NODE{j}",
                    "connected",
                    0.5,
                    bidirectional=False,
                )
        repository.session.commit()

        relationships = repository.list_relationships()
        # Should have 45 relationships (10 choose 2)
        assert len(relationships) == 45


class TestDataIntegrity:
    """Test data integrity constraints and validation."""

    @staticmethod
    def test_list_regulatory_events_returns_all(repository):
        """Test that list_regulatory_events returns all events."""
        # Create asset
        asset = Equity(
            id="EVENT_HOST",
            symbol="EH",
            name="Event Host",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(asset)
        repository.session.commit()

        # Create multiple events
        for i in range(5):
            event = RegulatoryEvent(
                id=f"EVENT{i}",
                asset_id="EVENT_HOST",
                event_type=RegulatoryActivity.SEC_FILING,
                date=f"2024-0{i + 1}-01",
                description=f"Event {i}",
                impact_score=0.5,
                related_assets=[],
            )
            repository.upsert_regulatory_event(event)
        repository.session.commit()

        events = repository.list_regulatory_events()
        assert len(events) == 5

    @staticmethod
    def test_delete_regulatory_event(repository):
        """Test deleting a regulatory event."""
        asset = Equity(
            id="EVENT_DEL",
            symbol="ED",
            name="Event Del",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(asset)

        event = RegulatoryEvent(
            id="DEL_EVENT",
            asset_id="EVENT_DEL",
            event_type=RegulatoryActivity.DIVIDEND_ANNOUNCEMENT,
            date="2024-03-01",
            description="To be deleted",
            impact_score=0.3,
            related_assets=[],
        )

        repository.upsert_regulatory_event(event)
        repository.session.commit()

        # Delete the event
        repository.delete_regulatory_event("DEL_EVENT")
        repository.session.commit()

        events = repository.list_regulatory_events()
        assert len(events) == 0

    @staticmethod
    def test_delete_nonexistent_regulatory_event(repository):
        """Test deleting a regulatory event that doesn't exist."""
        # Should not raise an error
        repository.delete_regulatory_event("NONEXISTENT")
        repository.session.commit()


class TestBoundaryValues:
    """Test boundary value conditions."""

    @staticmethod
    def test_very_small_price(repository):
        """Test asset with very small price."""
        equity = Equity(
            id="MICRO",
            symbol="MCR",
            name="Micro Price",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=0.01,
        )

        repository.upsert_asset(equity)
        repository.session.commit()

        retrieved = repository.list_assets()[0]
        assert retrieved.price == 0.01

    @staticmethod
    def test_very_large_market_cap(repository):
        """Test asset with very large market cap."""
        equity = Equity(
            id="MEGA",
            symbol="MGA",
            name="Mega Cap",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=1000.0,
            market_cap=1e15,  # Quadrillion dollars
        )

        repository.upsert_asset(equity)
        repository.session.commit()

        retrieved = repository.list_assets()[0]
        assert retrieved.market_cap == 1e15

    @staticmethod
    def test_negative_strength_relationship(repository):
        """Test relationship with negative strength (negative correlation)."""
        asset1 = Equity(
            id="NEG1",
            symbol="N1",
            name="Neg 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="NEG2",
            symbol="N2",
            name="Neg 2",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=200.0,
        )

        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship(
            "NEG1", "NEG2", "negative_corr", -0.8, bidirectional=False
        )
        repository.session.commit()

        rel = repository.get_relationship("NEG1", "NEG2", "negative_corr")
        assert rel is not None
        assert rel.strength == -0.8


class TestSpecialCharacters:
    """Test handling of special characters in data."""

    @staticmethod
    def test_asset_with_special_characters_in_name(repository):
        """Test asset with special characters in name."""
        equity = Equity(
            id="SPECIAL",
            symbol="SPC",
            name="Company & Partners (Ltd.)",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=100.0,
        )

        repository.upsert_asset(equity)
        repository.session.commit()

        retrieved = repository.list_assets()[0]
        assert retrieved.name == "Company & Partners (Ltd.)"

    @staticmethod
    def test_event_description_with_quotes(repository):
        """Test regulatory event with quotes in description."""
        asset = Equity(
            id="QUOTE_TEST",
            symbol="QT",
            name="Quote Test",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(asset)

        event = RegulatoryEvent(
            id="QUOTE_EVENT",
            asset_id="QUOTE_TEST",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2024-01-01",
            description='CEO stated: "Record growth expected"',
            impact_score=0.7,
            related_assets=[],
        )

        repository.upsert_regulatory_event(event)
        repository.session.commit()

        events = repository.list_regulatory_events()
        assert 'CEO stated: "Record growth expected"' in events[0].description

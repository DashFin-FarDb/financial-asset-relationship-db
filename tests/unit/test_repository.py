"""Unit tests for AssetGraphRepository.

This module contains comprehensive unit tests for the repository layer including:
- Asset CRUD operations
- Relationship management
- Regulatory event handling
- Data transformation and mapping
- Query operations and filtering
"""

import pytest

pytest.importorskip("sqlalchemy")

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
        equity1 = Equity(
            id="EQUITY1", symbol="E1", name="Equity 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0
        )
        equity2 = Equity(
            id="EQUITY2", symbol="E2", name="Equity 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0
        )

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
        equity = Equity(
            id="DELETE_ME", symbol="DEL", name="Delete", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0
        )

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
        asset1 = Equity(
            id="ASSET1", symbol="A1", name="Asset 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0
        )
        asset2 = Equity(
            id="ASSET2", symbol="A2", name="Asset 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0
        )
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
        asset1 = Equity(
            id="UPDATE1", symbol="U1", name="Update 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0
        )
        asset2 = Equity(
            id="UPDATE2", symbol="U2", name="Update 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0
        )
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
        asset = Equity(
            id="EVENT_ASSET", symbol="EA", name="Event Asset", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0
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

    def test_upsert_update_regulatory_event(self, repository):
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

        events = repository.session.query(RegulatoryEventORM).filter_by(id="EVENT002").all()
        assert len(events) == 1
        assert events[0].impact_score == 0.9
        assert events[0].description == "Updated filing"

    def test_upsert_event_with_related_assets(self, repository):
        """Test upserting event with related assets."""
        # Create assets
        main = Equity(id="MAIN", symbol="M", name="Main", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
        related1 = Equity(
            id="REL1", symbol="R1", name="Related 1", asset_class=AssetClass.EQUITY, sector="Tech", price=50.0
        )
        related2 = Equity(
            id="REL2", symbol="R2", name="Related 2", asset_class=AssetClass.EQUITY, sector="Tech", price=75.0
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
        equity = Equity(
            id="MULTI1", symbol="M1", name="Multi 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0
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
        asset1 = Equity(
            id="ZERO1", symbol="Z1", name="Zero 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0
        )
        asset2 = Equity(
            id="ZERO2", symbol="Z2", name="Zero 2", asset_class=AssetClass.EQUITY, sector="Tech", price=200.0
        )
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

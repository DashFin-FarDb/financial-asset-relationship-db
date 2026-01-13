"""Unit tests for SQLAlchemy ORM models.

This module contains comprehensive unit tests for the database models including:
- AssetORM model structure and relationships
- AssetRelationshipORM constraints and relationships
- RegulatoryEventORM and related asset associations
- Database constraints and cascading behavior
- Model field validation and nullable constraints
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from src.data.database import create_session_factory, init_db
from src.data.db_models import AssetORM, AssetRelationshipORM, RegulatoryEventAssetORM, RegulatoryEventORM

pytest.importorskip("sqlalchemy")


@pytest.fixture
def db_session(tmp_path):
    """Create a test database session."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


class TestAssetORM:
    """Test cases for AssetORM model."""

    @staticmethod
    def test_asset_orm_table_name():
        """Test that AssetORM uses correct table name."""
        assert AssetORM.__tablename__ == "assets"

    @staticmethod
    def test_asset_orm_primary_key():
        """Test AssetORM primary key configuration."""
        inspector = inspect(AssetORM)
        pk_columns = [col.name for col in inspector.primary_key]
        assert "id" in pk_columns
        assert len(pk_columns) == 1

    @staticmethod
    def test_create_equity_asset(db_session):
        """Test creating an equity asset."""
        asset = AssetORM(
            id="TEST_EQUITY",
            symbol="TEST",
            name="Test Equity",
            asset_class="equity",
            sector="Technology",
            price=100.0,
            currency="USD",
            pe_ratio=25.0,
            dividend_yield=0.02,
            earnings_per_share=4.0,
        )
        db_session.add(asset)
        db_session.commit()

        retrieved = db_session.query(AssetORM).filter_by(id="TEST_EQUITY").first()
        assert retrieved is not None
        assert retrieved.symbol == "TEST"
        assert retrieved.pe_ratio == 25.0

    def test_create_bond_asset(self, db_session):
        """Test creating a bond asset."""
        asset = AssetORM(
            id="TEST_BOND",
            symbol="BOND",
            name="Test Bond",
            asset_class="fixed_income",
            sector="Finance",
            price=1000.0,
            currency="USD",
            yield_to_maturity=0.03,
            coupon_rate=0.025,
            maturity_date="2030-01-01",
            credit_rating="AAA",
            issuer_id="TEST_EQUITY",
        )
        db_session.add(asset)
        db_session.commit()

        retrieved = db_session.query(AssetORM).filter_by(id="TEST_BOND").first()
        assert retrieved is not None
        assert retrieved.yield_to_maturity == 0.03
        assert retrieved.credit_rating == "AAA"

    def test_create_commodity_asset(self, db_session):
        """Test creating a commodity asset."""
        asset = AssetORM(
            id="TEST_COMMODITY",
            symbol="GOLD",
            name="Gold Futures",
            asset_class="commodity",
            sector="Materials",
            price=1950.0,
            currency="USD",
            contract_size=100.0,
            delivery_date="2024-12-31",
            volatility=0.15,
        )
        db_session.add(asset)
        db_session.commit()

        retrieved = db_session.query(AssetORM).filter_by(id="TEST_COMMODITY").first()
        assert retrieved is not None
        assert retrieved.contract_size == 100.0
        assert retrieved.volatility == 0.15

    def test_create_currency_asset(self, db_session):
        """Test creating a currency asset."""
        asset = AssetORM(
            id="TEST_CURRENCY",
            symbol="EUR",
            name="Euro",
            asset_class="currency",
            sector="Currency",
            price=1.10,
            currency="USD",
            exchange_rate=1.10,
            country="Eurozone",
            central_bank_rate=0.04,
        )
        db_session.add(asset)
        db_session.commit()

        retrieved = db_session.query(AssetORM).filter_by(id="TEST_CURRENCY").first()
        assert retrieved is not None
        assert retrieved.exchange_rate == 1.10
        assert retrieved.country == "Eurozone"

    def test_asset_required_fields(self, db_session):
        """Test that required fields are enforced."""
        asset = AssetORM(
            id="TEST_REQUIRED",
            symbol="REQ",
            name="Test Required",
            asset_class="equity",
            sector="Test",
            price=100.0,
            currency="USD",
        )
        db_session.add(asset)
        db_session.commit()
        assert db_session.query(AssetORM).filter_by(id="TEST_REQUIRED").first() is not None

    def test_asset_nullable_fields(self, db_session):
        """Test that nullable fields can be None."""
        asset = AssetORM(
            id="TEST_NULLABLE",
            symbol="NULL",
            name="Test Nullable",
            asset_class="equity",
            sector="Test",
            price=100.0,
            currency="USD",
            pe_ratio=None,
            market_cap=None,
        )
        db_session.add(asset)
        db_session.commit()

        retrieved = db_session.query(AssetORM).filter_by(id="TEST_NULLABLE").first()
        assert retrieved.pe_ratio is None
        assert retrieved.market_cap is None

    def test_asset_update(self, db_session):
        """Test updating asset fields."""
        asset = AssetORM(
            id="TEST_UPDATE",
            symbol="UPD",
            name="Test Update",
            asset_class="equity",
            sector="Tech",
            price=100.0,
            currency="USD",
        )
        db_session.add(asset)
        db_session.commit()

        asset.price = 150.0
        asset.sector = "Technology"
        db_session.commit()

        retrieved = db_session.query(AssetORM).filter_by(id="TEST_UPDATE").first()
        assert retrieved.price == 150.0
        assert retrieved.sector == "Technology"

    def test_asset_deletion(self, db_session):
        """Test deleting an asset."""
        asset = AssetORM(
            id="TEST_DELETE",
            symbol="DEL",
            name="Test Delete",
            asset_class="equity",
            sector="Test",
            price=100.0,
            currency="USD",
        )
        db_session.add(asset)
        db_session.commit()

        db_session.delete(asset)
        db_session.commit()

        retrieved = db_session.query(AssetORM).filter_by(id="TEST_DELETE").first()
        assert retrieved is None


class TestAssetRelationshipORM:
    """Test cases for AssetRelationshipORM model."""

    @staticmethod
    def test_relationship_table_name():
        """Test that AssetRelationshipORM uses correct table name."""
        assert AssetRelationshipORM.__tablename__ == "asset_relationships"

    def test_create_relationship(self, db_session):
        """Test creating a relationship between assets."""
        # Create two assets
        asset1 = AssetORM(
            id="ASSET1", symbol="A1", name="Asset 1", asset_class="equity", sector="Tech", price=100.0, currency="USD"
        )
        asset2 = AssetORM(
            id="ASSET2", symbol="A2", name="Asset 2", asset_class="equity", sector="Tech", price=200.0, currency="USD"
        )
        db_session.add_all([asset1, asset2])
        db_session.commit()

        # Create relationship
        rel = AssetRelationshipORM(
            source_asset_id="ASSET1",
            target_asset_id="ASSET2",
            relationship_type="same_sector",
            strength=0.7,
            bidirectional=True,
        )
        db_session.add(rel)
        db_session.commit()

        retrieved = db_session.query(AssetRelationshipORM).filter_by(source_asset_id="ASSET1").first()
        assert retrieved is not None
        assert retrieved.target_asset_id == "ASSET2"
        assert retrieved.strength == 0.7

    def test_relationship_unique_constraint(self, db_session):
        """Test that duplicate relationships are prevented."""
        asset1 = AssetORM(
            id="ASSET_A", symbol="AA", name="Asset A", asset_class="equity", sector="Tech", price=100.0, currency="USD"
        )
        asset2 = AssetORM(
            id="ASSET_B", symbol="BB", name="Asset B", asset_class="equity", sector="Tech", price=200.0, currency="USD"
        )
        db_session.add_all([asset1, asset2])
        db_session.commit()

        rel1 = AssetRelationshipORM(
            source_asset_id="ASSET_A",
            target_asset_id="ASSET_B",
            relationship_type="test_rel",
            strength=0.5,
        )
        db_session.add(rel1)
        db_session.commit()

        # Try to add duplicate
        rel2 = AssetRelationshipORM(
            source_asset_id="ASSET_A",
            target_asset_id="ASSET_B",
            relationship_type="test_rel",
            strength=0.8,
        )
        db_session.add(rel2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_relationship_cascade_delete(self, db_session):
        """Test that relationships are deleted when assets are deleted."""
        asset1 = AssetORM(
            id="CASCADE1",
            symbol="C1",
            name="Cascade 1",
            asset_class="equity",
            sector="Tech",
            price=100.0,
            currency="USD",
        )
        asset2 = AssetORM(
            id="CASCADE2",
            symbol="C2",
            name="Cascade 2",
            asset_class="equity",
            sector="Tech",
            price=200.0,
            currency="USD",
        )
        db_session.add_all([asset1, asset2])
        db_session.commit()

        rel = AssetRelationshipORM(
            source_asset_id="CASCADE1",
            target_asset_id="CASCADE2",
            relationship_type="test",
            strength=0.5,
        )
        db_session.add(rel)
        db_session.commit()

        # Delete source asset
        db_session.delete(asset1)
        db_session.commit()

        # Relationship should be deleted
        remaining = db_session.query(AssetRelationshipORM).filter_by(source_asset_id="CASCADE1").first()
        assert remaining is None

    def test_bidirectional_flag(self, db_session):
        """Test bidirectional flag on relationships."""
        asset1 = AssetORM(
            id="BIDIR1", symbol="B1", name="Bidir 1", asset_class="equity", sector="Tech", price=100.0, currency="USD"
        )
        asset2 = AssetORM(
            id="BIDIR2", symbol="B2", name="Bidir 2", asset_class="equity", sector="Tech", price=200.0, currency="USD"
        )
        db_session.add_all([asset1, asset2])
        db_session.commit()

        rel = AssetRelationshipORM(
            source_asset_id="BIDIR1",
            target_asset_id="BIDIR2",
            relationship_type="bidirectional_test",
            strength=0.8,
            bidirectional=True,
        )
        db_session.add(rel)
        db_session.commit()

        retrieved = db_session.query(AssetRelationshipORM).filter_by(source_asset_id="BIDIR1").first()
        assert retrieved.bidirectional is True

    def test_relationship_strength_bounds(self, db_session):
        """Test that relationship strength can store various values."""
        asset1 = AssetORM(
            id="STRENGTH1",
            symbol="S1",
            name="Strength 1",
            asset_class="equity",
            sector="Tech",
            price=100.0,
            currency="USD",
        )
        asset2 = AssetORM(
            id="STRENGTH2",
            symbol="S2",
            name="Strength 2",
            asset_class="equity",
            sector="Tech",
            price=200.0,
            currency="USD",
        )
        db_session.add_all([asset1, asset2])
        db_session.commit()

        # Test various strength values
        for strength in [0.0, 0.5, 1.0]:
            rel = AssetRelationshipORM(
                source_asset_id="STRENGTH1",
                target_asset_id="STRENGTH2",
                relationship_type=f"strength_{strength}",
                strength=strength,
            )
            db_session.add(rel)
        db_session.commit()

        relationships = db_session.query(AssetRelationshipORM).filter_by(source_asset_id="STRENGTH1").all()
        assert len(relationships) == 3


class TestRegulatoryEventORM:
    """Test cases for RegulatoryEventORM model."""

    @staticmethod
    def test_regulatory_event_table_name():
        """Test that RegulatoryEventORM uses correct table name."""
        assert RegulatoryEventORM.__tablename__ == "regulatory_events"

    def test_create_regulatory_event(self, db_session):
        """Test creating a regulatory event."""
        asset = AssetORM(
            id="EVENT_ASSET",
            symbol="EA",
            name="Event Asset",
            asset_class="equity",
            sector="Tech",
            price=100.0,
            currency="USD",
        )
        db_session.add(asset)
        db_session.commit()

        event = RegulatoryEventORM(
            id="EVENT_001",
            asset_id="EVENT_ASSET",
            event_type="EARNINGS_REPORT",
            date="2024-01-15",
            description="Q4 2023 Earnings",
            impact_score=0.8,
        )
        db_session.add(event)
        db_session.commit()

        retrieved = db_session.query(RegulatoryEventORM).filter_by(id="EVENT_001").first()
        assert retrieved is not None
        assert retrieved.event_type == "EARNINGS_REPORT"
        assert retrieved.impact_score == 0.8

    @staticmethod
    def test_regulatory_event_cascade_delete(db_session):
        """Test that events are deleted when asset is deleted."""
        asset = AssetORM(
            id="EVENT_CASCADE",
            symbol="EC",
            name="Event Cascade",
            asset_class="equity",
            sector="Tech",
            price=100.0,
            currency="USD",
        )
        db_session.add(asset)
        db_session.commit()

        event = RegulatoryEventORM(
            id="EVENT_002",
            asset_id="EVENT_CASCADE",
            event_type="SEC_FILING",
            date="2024-02-01",
            description="Test filing",
            impact_score=0.5,
        )
        db_session.add(event)
        db_session.commit()

        # Delete asset
        db_session.delete(asset)
        db_session.commit()

        # Event should be deleted
        remaining = db_session.query(RegulatoryEventORM).filter_by(id="EVENT_002").first()
        assert remaining is None

    def test_regulatory_event_with_related_assets(self, db_session):
        """Test regulatory event with related assets."""
        # Create main asset and related assets
        main_asset = AssetORM(
            id="MAIN_ASSET",
            symbol="MA",
            name="Main Asset",
            asset_class="equity",
            sector="Tech",
            price=100.0,
            currency="USD",
        )
        related1 = AssetORM(
            id="RELATED1",
            symbol="R1",
            name="Related 1",
            asset_class="equity",
            sector="Tech",
            price=50.0,
            currency="USD",
        )
        related2 = AssetORM(
            id="RELATED2",
            symbol="R2",
            name="Related 2",
            asset_class="equity",
            sector="Tech",
            price=50.0,
            currency="USD",
        )
            sector = "Tech",
            price = 75.0,
            currency = "USD",
        )
        db_session.add_all([main_asset, related1, related2])
        db_session.commit()

        # Create event
        event = RegulatoryEventORM(
            id = "EVENT_003",
            asset_id = "MAIN_ASSET",
            event_type = "MERGER",
            date = "2024-03-01",
            description = "Merger announcement",
            impact_score = 0.9,
        )
        db_session.add(event)
        db_session.commit()

        # Add related assets
        rel1 = RegulatoryEventAssetORM(event_id="EVENT_003", asset_id="RELATED1")
        rel2 = RegulatoryEventAssetORM(event_id="EVENT_003", asset_id="RELATED2")
        db_session.add_all([rel1, rel2])
        db_session.commit()

        # Verify
        event = db_session.query(RegulatoryEventORM).filter_by(id="EVENT_003").first()
        assert len(event.related_assets) == 2


class TestRegulatoryEventAssetORM:
    """Test cases for RegulatoryEventAssetORM join table."""

    @ staticmethod
    def test_event_asset_table_name():
        """Test that RegulatoryEventAssetORM uses correct table name."""
        assert RegulatoryEventAssetORM.__tablename__ == "regulatory_event_assets"

    @ staticmethod
    def test_event_asset_unique_constraint(db_session):
        """Test that duplicate event-asset links are prevented."""
        asset = AssetORM(
            id = "UNIQUE_ASSET",
            symbol = "UA",
            name = "Unique Asset",
            asset_class = "equity",
            sector = "Tech",
            price = 100.0,
            currency = "USD",
        )
        related = AssetORM(
            id = "UNIQUE_RELATED",
            symbol = "UR",
            name = "Unique Related",
            asset_class = "equity",
            sector = "Tech",
            price = 50.0,
            currency = "USD",
        )
        db_session.add_all([asset, related])
        db_session.commit()

        event = RegulatoryEventORM(
            id = "UNIQUE_EVENT",
            asset_id = "UNIQUE_ASSET",
            event_type = "TEST",
            date = "2024-01-01",
            description = "Test",
            impact_score = 0.5,
        )
        db_session.add(event)
        db_session.commit()

        # Add related asset
        rel1 = RegulatoryEventAssetORM(event_id="UNIQUE_EVENT", asset_id="UNIQUE_RELATED")
        db_session.add(rel1)
        db_session.commit()

        # Try to add duplicate
        rel2 = RegulatoryEventAssetORM(event_id="UNIQUE_EVENT", asset_id="UNIQUE_RELATED")
        db_session.add(rel2)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_event_asset_cascade_delete_on_event(self, db_session):
        """Test cascade delete when event is removed."""
        asset = AssetORM(
            id = "CASCADE_ASSET",
            symbol = "CA",
            name = "Cascade Asset",
            asset_class = "equity",
            sector = "Tech",
            price = 100.0,
            currency = "USD",
        )
        related = AssetORM(
            id = "CASCADE_RELATED",
            symbol = "CR",
            name = "Cascade Related",
            asset_class = "equity",
            sector = "Tech",
            price = 50.0,
            currency = "USD",
        )
        db_session.add_all([asset, related])
        db_session.commit()

        event = RegulatoryEventORM(
            id = "CASCADE_EVENT",
            asset_id = "CASCADE_ASSET",
            event_type = "TEST",
            date = "2024-01-01",
            description = "Test",
            impact_score = 0.5,
        )
        db_session.add(event)
        db_session.commit()

        rel = RegulatoryEventAssetORM(event_id="CASCADE_EVENT", asset_id="CASCADE_RELATED")
        db_session.add(rel)
        db_session.commit()

        # Delete event
        db_session.delete(event)
        db_session.commit()

        # Related asset link should be deleted
        remaining = db_session.query(RegulatoryEventAssetORM).filter_by(event_id="CASCADE_EVENT").first()
        assert remaining is None

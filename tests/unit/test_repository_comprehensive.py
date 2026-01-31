"""Comprehensive additional unit tests for AssetGraphRepository.

This module contains additional comprehensive tests including:
- get_asset_by_id method testing
- Relationship strength validation (boundary values, out-of-range, type errors)
- Additional edge cases and negative tests
- Performance and stress tests
"""

import pytest
from sqlalchemy import create_engine

from src.data.database import create_session_factory, init_db
from src.data.repository import AssetGraphRepository
from src.models.financial_models import AssetClass, Equity

pytestmark = pytest.mark.unit


@pytest.fixture
def repository(tmp_path):
    """Create a repository with a test database."""
    db_path = tmp_path / "test_repo_comprehensive.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)
    session = factory()
    repo = AssetGraphRepository(session)
    yield repo
    session.close()
    engine.dispose()


class TestGetAssetById:
    """Test the get_asset_by_id method."""

    @staticmethod
    def test_get_existing_asset(repository):
        """Test retrieving an existing asset by ID."""
        equity = Equity(
            id="GET_BY_ID_TEST",
            symbol="GBIT",
            name="Get By Id Test",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        repository.upsert_asset(equity)
        repository.session.commit()

        retrieved = repository.get_asset_by_id("GET_BY_ID_TEST")

        assert retrieved is not None
        assert retrieved.id == "GET_BY_ID_TEST"
        assert retrieved.symbol == "GBIT"
        assert retrieved.price == 100.0

    @staticmethod
    def test_get_nonexistent_asset(repository):
        """Test retrieving an asset that doesn't exist."""
        result = repository.get_asset_by_id("NONEXISTENT_ID")
        assert result is None

    @staticmethod
    def test_get_asset_returns_correct_type(repository):
        """Test that get_asset_by_id returns the correct asset subclass."""
        equity = Equity(
            id="EQUITY_TYPE",
            symbol="EQT",
            name="Equity Type Test",
            asset_class=AssetClass.EQUITY,
            sector="Finance",
            price=150.0,
            pe_ratio=20.0,
        )
        repository.upsert_asset(equity)
        repository.session.commit()

        retrieved = repository.get_asset_by_id("EQUITY_TYPE")

        assert isinstance(retrieved, Equity)
        assert retrieved.pe_ratio == 20.0

    @staticmethod
    def test_get_asset_after_update(repository):
        """Test getting asset after it has been updated."""
        equity = Equity(
            id="UPDATE_GET",
            symbol="UG",
            name="Update Get",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(equity)
        repository.session.commit()

        # Update the asset
        equity.price = 200.0
        repository.upsert_asset(equity)
        repository.session.commit()

        retrieved = repository.get_asset_by_id("UPDATE_GET")
        assert retrieved.price == 200.0


class TestRelationshipStrengthValidation:
    """Test validation of relationship strength values."""

    @staticmethod
    def test_strength_validation_rejects_below_minus_one(repository):
        """Test that strength below -1.0 raises ValueError."""
        asset1 = Equity(
            id="STR1",
            symbol="S1",
            name="Strength 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR2",
            symbol="S2",
            name="Strength 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError, match="strength must be between -1.0 and 1.0"):
            repository.add_or_update_relationship("STR1", "STR2", "invalid", -1.1, bidirectional=False)

    @staticmethod
    def test_strength_validation_rejects_above_one(repository):
        """Test that strength above 1.0 raises ValueError."""
        asset1 = Equity(
            id="STR3",
            symbol="S3",
            name="Strength 3",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR4",
            symbol="S4",
            name="Strength 4",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError, match="strength must be between -1.0 and 1.0"):
            repository.add_or_update_relationship("STR3", "STR4", "invalid", 1.1, bidirectional=False)

    @staticmethod
    def test_strength_validation_accepts_zero(repository):
        """Test that strength of exactly 0.0 is accepted."""
        asset1 = Equity(
            id="STR5",
            symbol="S5",
            name="Strength 5",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR6",
            symbol="S6",
            name="Strength 6",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Should not raise
        repository.add_or_update_relationship("STR5", "STR6", "zero_strength", 0.0, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("STR5", "STR6", "zero_strength")
        assert rel.strength == 0.0

    @staticmethod
    def test_strength_validation_accepts_one(repository):
        """Test that strength of exactly 1.0 is accepted."""
        asset1 = Equity(
            id="STR7",
            symbol="S7",
            name="Strength 7",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR8",
            symbol="S8",
            name="Strength 8",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Should not raise
        repository.add_or_update_relationship("STR7", "STR8", "max_strength", 1.0, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("STR7", "STR8", "max_strength")
        assert rel.strength == 1.0

    @staticmethod
    def test_strength_validation_accepts_minus_one(repository):
        """Test that strength of exactly -1.0 is accepted."""
        asset1 = Equity(
            id="STR7A",
            symbol="S7A",
            name="Strength 7A",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR8A",
            symbol="S8A",
            name="Strength 8A",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Should not raise
        repository.add_or_update_relationship("STR7A", "STR8A", "min_strength", -1.0, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("STR7A", "STR8A", "min_strength")
        assert rel.strength == -1.0

    @staticmethod
    def test_strength_validation_accepts_negative_values(repository):
        """Test that negative strength values are accepted."""
        asset1 = Equity(
            id="STR7B",
            symbol="S7B",
            name="Strength 7B",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR8B",
            symbol="S8B",
            name="Strength 8B",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Should not raise
        repository.add_or_update_relationship("STR7B", "STR8B", "negative_corr", -0.5, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("STR7B", "STR8B", "negative_corr")
        assert rel.strength == -0.5

    @staticmethod
    def test_strength_validation_rejects_string(repository):
        """Test that non-numeric strength raises ValueError."""
        asset1 = Equity(
            id="STR9",
            symbol="S9",
            name="Strength 9",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR10",
            symbol="S10",
            name="Strength 10",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError, match="strength must be a numeric value"):
            repository.add_or_update_relationship("STR9", "STR10", "invalid", "0.5", bidirectional=False)

    @staticmethod
    def test_strength_validation_accepts_int_in_range(repository):
        """Test that integer strength values in range are accepted."""
        asset1 = Equity(
            id="STR11",
            symbol="S11",
            name="Strength 11",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="STR12",
            symbol="S12",
            name="Strength 12",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Integer 1 should be accepted as 1.0
        repository.add_or_update_relationship("STR11", "STR12", "int_strength", 1, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("STR11", "STR12", "int_strength")
        assert rel.strength == 1


class TestStrengthBoundaryValues:
    """Test boundary values for relationship strength."""

    @staticmethod
    def test_strength_just_above_zero(repository):
        """Test strength just above zero."""
        asset1 = Equity(
            id="BOUND1",
            symbol="B1",
            name="Bound 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="BOUND2",
            symbol="B2",
            name="Bound 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship("BOUND1", "BOUND2", "tiny", 0.0001, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("BOUND1", "BOUND2", "tiny")
        assert rel.strength == 0.0001

    @staticmethod
    def test_strength_just_below_one(repository):
        """Test strength just below one."""
        asset1 = Equity(
            id="BOUND3",
            symbol="B3",
            name="Bound 3",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="BOUND4",
            symbol="B4",
            name="Bound 4",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        repository.add_or_update_relationship("BOUND3", "BOUND4", "almost_max", 0.9999, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("BOUND3", "BOUND4", "almost_max")
        assert rel.strength == 0.9999

    @staticmethod
    def test_strength_just_below_minus_one_fails(repository):
        """Test that strength just below -1.0 fails validation."""
        asset1 = Equity(
            id="BOUND5",
            symbol="B5",
            name="Bound 5",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="BOUND6",
            symbol="B6",
            name="Bound 6",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError):
            repository.add_or_update_relationship("BOUND5", "BOUND6", "too_negative", -1.0001, bidirectional=False)

    @staticmethod
    def test_strength_just_above_one_fails(repository):
        """Test that strength just above one fails validation."""
        asset1 = Equity(
            id="BOUND7",
            symbol="B7",
            name="Bound 7",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="BOUND8",
            symbol="B8",
            name="Bound 8",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError):
            repository.add_or_update_relationship("BOUND7", "BOUND8", "over_max", 1.0001, bidirectional=False)


class TestStrengthTypeValidation:
    """Test type validation for relationship strength."""

    @staticmethod
    def test_strength_rejects_none(repository):
        """Test that None strength raises ValueError."""
        asset1 = Equity(
            id="TYPE1",
            symbol="T1",
            name="Type 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="TYPE2",
            symbol="T2",
            name="Type 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError, match="strength must be a numeric value"):
            repository.add_or_update_relationship("TYPE1", "TYPE2", "none_strength", None, bidirectional=False)

    @staticmethod
    def test_strength_rejects_list(repository):
        """Test that list strength raises ValueError."""
        asset1 = Equity(
            id="TYPE3",
            symbol="T3",
            name="Type 3",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="TYPE4",
            symbol="T4",
            name="Type 4",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError, match="strength must be a numeric value"):
            repository.add_or_update_relationship("TYPE3", "TYPE4", "list_strength", [0.5], bidirectional=False)

    @staticmethod
    def test_strength_rejects_dict(repository):
        """Test that dict strength raises ValueError."""
        asset1 = Equity(
            id="TYPE5",
            symbol="T5",
            name="Type 5",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="TYPE6",
            symbol="T6",
            name="Type 6",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        with pytest.raises(ValueError, match="strength must be a numeric value"):
            repository.add_or_update_relationship(
                "TYPE5", "TYPE6", "dict_strength", {"value": 0.5}, bidirectional=False
            )


class TestNegativeTestCases:
    """Test negative scenarios and error conditions."""

    @staticmethod
    def test_get_asset_with_empty_string_id(repository):
        """Test getting asset with empty string ID."""
        result = repository.get_asset_by_id("")
        assert result is None

    @staticmethod
    def test_get_asset_with_special_characters(repository):
        """Test getting asset with special character ID."""
        # First create an asset with special chars
        equity = Equity(
            id="SPECIAL@#$",
            symbol="SPC",
            name="Special",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(equity)
        repository.session.commit()

        retrieved = repository.get_asset_by_id("SPECIAL@#$")
        assert retrieved is not None
        assert retrieved.id == "SPECIAL@#$"

    @staticmethod
    def test_relationship_with_nonexistent_source(repository):
        """Test creating relationship with non-existent source asset."""
        asset2 = Equity(
            id="EXIST",
            symbol="EX",
            name="Exists",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(asset2)
        repository.session.commit()

        # This should not raise at the repository level (database constraints may differ)
        repository.add_or_update_relationship("NONEXIST", "EXIST", "test_rel", 0.5, bidirectional=False)
        # The relationship is created, but referential integrity depends on DB constraints


class TestStressAndPerformance:
    """Test repository under stress conditions."""

    @staticmethod
    def test_get_asset_many_times(repository):
        """Test getting the same asset many times."""
        equity = Equity(
            id="STRESS1",
            symbol="STR1",
            name="Stress 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(equity)
        repository.session.commit()

        # Get it 100 times
        for _ in range(100):
            result = repository.get_asset_by_id("STRESS1")
            assert result is not None
            assert result.id == "STRESS1"

    @staticmethod
    def test_many_strength_validations(repository):
        """Test strength validation with many different values."""
        asset1 = Equity(
            id="MANY1",
            symbol="M1",
            name="Many 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="MANY2",
            symbol="M2",
            name="Many 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Test many valid values
        valid_strengths = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 1.0]
        for i, strength in enumerate(valid_strengths):
            repository.add_or_update_relationship("MANY1", "MANY2", f"rel_{i}", strength, bidirectional=False)
            repository.session.commit()

            rel = repository.get_relationship("MANY1", "MANY2", f"rel_{i}")
            assert rel.strength == strength


class TestEdgeCasesAndRegression:
    """Test additional edge cases and regression scenarios."""

    @staticmethod
    def test_update_relationship_validates_new_strength(repository):
        """Test that updating a relationship validates the new strength."""
        asset1 = Equity(
            id="UPVAL1",
            symbol="UV1",
            name="Update Val 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="UPVAL2",
            symbol="UV2",
            name="Update Val 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Create valid relationship
        repository.add_or_update_relationship("UPVAL1", "UPVAL2", "update_test", 0.5, bidirectional=False)
        repository.session.commit()

        # Try to update with invalid strength
        with pytest.raises(ValueError):
            repository.add_or_update_relationship("UPVAL1", "UPVAL2", "update_test", 1.5, bidirectional=False)

    @staticmethod
    def test_get_asset_returns_fresh_data(repository):
        """Test that get_asset_by_id returns fresh data after updates."""
        equity = Equity(
            id="FRESH",
            symbol="FRS",
            name="Fresh",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        repository.upsert_asset(equity)
        repository.session.commit()

        # Get initial
        first = repository.get_asset_by_id("FRESH")
        assert first.price == 100.0

        # Update
        equity.price = 200.0
        repository.upsert_asset(equity)
        repository.session.commit()

        # Get again should show new price
        second = repository.get_asset_by_id("FRESH")
        assert second.price == 200.0

    @staticmethod
    def test_strength_validation_with_float_precision(repository):
        """Test strength validation with floating point precision edge cases."""
        asset1 = Equity(
            id="PREC1",
            symbol="PR1",
            name="Precision 1",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=100.0,
        )
        asset2 = Equity(
            id="PREC2",
            symbol="PR2",
            name="Precision 2",
            asset_class=AssetClass.EQUITY,
            sector="Tech",
            price=200.0,
        )
        repository.upsert_asset(asset1)
        repository.upsert_asset(asset2)
        repository.session.commit()

        # Test with very precise float
        precise_strength = 0.123456789012345
        repository.add_or_update_relationship("PREC1", "PREC2", "precise", precise_strength, bidirectional=False)
        repository.session.commit()

        rel = repository.get_relationship("PREC1", "PREC2", "precise")
        # Should preserve reasonable precision
        assert abs(rel.strength - precise_strength) < 1e-10

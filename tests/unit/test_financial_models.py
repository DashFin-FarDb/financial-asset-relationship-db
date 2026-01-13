# ruff: noqa: S101
"""Unit tests for financial models.

This module contains comprehensive unit tests for all financial model classes including:
- Asset base class creation and validation
- Equity, Bond, Commodity, Currency subclasses
- RegulatoryEvent class with impact scoring
- Input validation and error handling for all model types

Note: This test file uses assert statements which is the standard and recommended
approach for pytest. The S101 rule is suppressed because tests are not run with
Python optimization flags that would remove assert statements.
"""

# ruff: noqa: S101
# The S101 rule flags use of assert statements. In pytest test files, assert is the
# standard and recommended way to make assertions. Pytest rewrites these statements
# to provide detailed error messages, and test files are not run with Python's -O flag.

import pytest

from src.models.financial_models import Asset, AssetClass, Bond, Equity, RegulatoryActivity, RegulatoryEvent


class TestAsset:
    """Test cases for the Asset base class."""

    def test_asset_creation(self):
        """Test creating a valid asset."""
        asset = Asset(
            id="TEST_001",
            symbol="TEST",
            name="Test Asset",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
            market_cap=1e9,
            currency="USD",
        )
        assert asset.id == "TEST_001"
        assert asset.symbol == "TEST"
        assert asset.name == "Test Asset"
        assert asset.price == 100.0
        assert asset.currency == "USD"

    def test_asset_invalid_id(self):
        """Test that empty id raises ValueError."""
        with pytest.raises(ValueError, match="id must be a non-empty string"):
            Asset(
                id="",
                symbol="TEST",
                name="Test Asset",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
            )

    def test_asset_invalid_price(self):
        """Test that negative price raises ValueError."""
        with pytest.raises(ValueError, match="price must be a non-negative number"):
            Asset(
                id="TEST_001",
                symbol="TEST",
                name="Test Asset",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=-100.0,
            )

    def test_asset_invalid_currency(self):
        """Test that invalid currency code raises ValueError."""
        with pytest.raises(ValueError, match="Currency must be a valid 3-letter ISO code"):
            Asset(
                id="TEST_001",
                symbol="TEST",
                name="Test Asset",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
                currency="INVALID",
            )

    def test_asset_invalid_market_cap(self):
        """Test that negative market cap raises ValueError."""
        with pytest.raises(ValueError, match="Market cap must be a non-negative number or None"):
            Asset(
                id="TEST_001",
                symbol="TEST",
                name="Test Asset",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
                market_cap=-1e9,
            )


class TestEquity:
    """Test cases for the Equity class."""

    @staticmethod
    def test_equity_optional_fields():
        """Test equity with optional fields as None."""
        equity = Equity(
            id="TEST_002",
            symbol="TEST",
            name="Test Equity",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        assert equity.pe_ratio is None
        assert equity.dividend_yield is None
        assert equity.earnings_per_share is None

    def test_equity_creation(self, sample_equity):
        """Test creating a valid equity asset."""
        assert sample_equity.asset_class == AssetClass.EQUITY
        assert sample_equity.pe_ratio == 25.5
        assert sample_equity.dividend_yield == 0.005


class TestBond:
    """Test cases for the Bond class."""

    def test_bond_creation(self, sample_bond):
        """Test creating a valid bond asset."""
        assert sample_bond.asset_class == AssetClass.FIXED_INCOME
        assert sample_bond.yield_to_maturity == 0.03
        assert sample_bond.credit_rating == "AAA"
        assert sample_bond.issuer_id == "TEST_AAPL"

    @staticmethod
    def test_bond_optional_fields():
        """Test bond with optional fields as None."""
        bond = Bond(
            id="TEST_BOND_002",
            symbol="TEST_BOND",
            name="Test Bond",
            asset_class=AssetClass.FIXED_INCOME,
            sector="Technology",
            price=1000.0,
        )
        assert bond.yield_to_maturity is None
        assert bond.coupon_rate is None
        assert bond.issuer_id is None


class TestCommodity:
    """Test cases for the Commodity class."""

    @staticmethod
    def test_commodity_creation(sample_commodity):
        """Test creating a valid commodity asset."""
        assert sample_commodity.asset_class == AssetClass.COMMODITY
        assert sample_commodity.contract_size == 100.0
        assert sample_commodity.volatility == 0.15


class TestCurrency:
    """Test cases for the Currency class."""

    @staticmethod
    def test_currency_creation(sample_currency):
        """Test creating a valid currency asset."""
        assert sample_currency.asset_class == AssetClass.CURRENCY
        assert sample_currency.exchange_rate == 1.10
        assert sample_currency.country == "Eurozone"


class TestRegulatoryEvent:
    """Test cases for the RegulatoryEvent class."""

    @staticmethod
    def test_event_creation(sample_regulatory_event):
        """Test creating a valid regulatory event."""
        assert sample_regulatory_event.id == "EVENT_001"
        assert sample_regulatory_event.asset_id == "TEST_AAPL"
        assert sample_regulatory_event.event_type == RegulatoryActivity.EARNINGS_REPORT
        assert sample_regulatory_event.impact_score == 0.8

    @staticmethod
    def test_event_invalid_impact_score():
        """Test that impact score outside [-1, 1] raises ValueError."""
        with pytest.raises(ValueError, match="Impact score must be a float between -1 and 1"):
            RegulatoryEvent(
                id="EVENT_002",
                asset_id="TEST_001",
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                date="2024-01-15",
                description="Test Event",
                impact_score=2.0,
            )

    @staticmethod
    def test_event_invalid_date():
        """Test that invalid date format raises ValueError."""
        with pytest.raises(ValueError, match="Date must be in ISO 8601 format"):
            RegulatoryEvent(
                id="EVENT_003",
                asset_id="TEST_001",
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                date="invalid-date",
                description="Test Event",
                impact_score=0.5,
            )

    @staticmethod
    def test_event_empty_description():
        """Test that empty description raises ValueError."""
        with pytest.raises(ValueError, match="Description must be a non-empty string"):
            RegulatoryEvent(
                id="EVENT_004",
                asset_id="TEST_001",
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                date="2024-01-15",
                description="",
                impact_score=0.5,
            )

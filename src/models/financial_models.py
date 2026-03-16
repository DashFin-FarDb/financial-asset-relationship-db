"""Core financial domain models and enums used across the project."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# Asset Class Definitions
class AssetClass(Enum):
    """Asset-class categories used by domain models."""

    EQUITY = "Equity"
    FIXED_INCOME = "Fixed Income"
    COMMODITY = "Commodity"
    CURRENCY = "Currency"
    DERIVATIVE = "Derivative"


class RegulatoryActivity(Enum):
    """Regulatory activities associated with tracked assets."""

    EARNINGS_REPORT = "Earnings Report"
    SEC_FILING = "SEC Filing"
    DIVIDEND_ANNOUNCEMENT = "Dividend Announcement"
    BOND_ISSUANCE = "Bond Issuance"
    ACQUISITION = "Acquisition"
    BANKRUPTCY = "Bankruptcy"


@dataclass
class Asset:
    """Base asset class"""

    id: str
    symbol: str
    name: str
    asset_class: AssetClass
    sector: str
    price: float
    market_cap: Optional[float] = None
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate asset data after initialization"""
        self._validate_non_empty_string(
            self.id,
            "Asset id must be a non-empty string",
        )
        self._validate_non_empty_string(
            self.symbol,
            "Asset symbol must be a non-empty string",
        )
        self._validate_non_empty_string(
            self.name,
            "Asset name must be a non-empty string",
        )
        self._validate_non_negative_number(
            self.price,
            "Asset price must be a non-negative number",
        )
        self._validate_non_negative_number(
            self.market_cap,
            "Market cap must be a non-negative number or None",
            allow_none=True,
        )
        self._validate_currency_code(self.currency)

    @staticmethod
    def _validate_non_empty_string(value: object, error_message: str) -> None:
        """Ensure required string fields are non-empty strings."""
        if not isinstance(value, str) or not value:
            raise ValueError(error_message)

    @staticmethod
    def _validate_non_negative_number(
        value: object,
        error_message: str,
        *,
        allow_none: bool = False,
    ) -> None:
        """Ensure numeric fields are non-negative."""
        if value is None and allow_none:
            return
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(error_message)

    @staticmethod
    def _validate_currency_code(currency: str) -> None:
        """Ensure currency code is an uppercase 3-letter ISO-like token."""
        if not re.match(r"^[A-Z]{3}$", currency.upper()):
            raise ValueError("Currency must be a valid 3-letter ISO code")


@dataclass
class Equity(Asset):
    """Equity asset"""

    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    earnings_per_share: Optional[float] = None
    book_value: Optional[float] = None


@dataclass
class Bond(Asset):
    """Fixed income asset"""

    yield_to_maturity: Optional[float] = None
    coupon_rate: Optional[float] = None
    maturity_date: Optional[str] = None
    credit_rating: Optional[str] = None
    issuer_id: Optional[str] = None  # Link to company if corporate


@dataclass
class Commodity(Asset):
    """Commodity asset"""

    contract_size: Optional[float] = None
    delivery_date: Optional[str] = None
    volatility: Optional[float] = None


@dataclass
class Currency(Asset):
    """Currency asset"""

    exchange_rate: Optional[float] = None
    country: Optional[str] = None
    central_bank_rate: Optional[float] = None


@dataclass
class RegulatoryEvent:
    """Regulatory and corporate events"""

    id: str
    asset_id: str
    event_type: RegulatoryActivity
    date: str  # ISO 8601 recommended
    description: str
    impact_score: float  # -1 to 1
    related_assets: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate event data after initialization"""
        self._validate_non_empty_string(
            self.id,
            "Event id must be a non-empty string",
        )
        self._validate_non_empty_string(
            self.asset_id,
            "Asset id must be a non-empty string",
        )
        self._validate_impact_score(self.impact_score)
        self._validate_iso_date_prefix(self.date)
        self._validate_non_empty_string(
            self.description,
            "Description must be a non-empty string",
        )

    @staticmethod
    def _validate_non_empty_string(value: object, error_message: str) -> None:
        """Ensure required event fields are non-empty strings."""
        if not isinstance(value, str) or not value:
            raise ValueError(error_message)

    @staticmethod
    def _validate_impact_score(value: object) -> None:
        """Ensure event impact score is numeric and normalized to [-1, 1]."""
        if not isinstance(value, (int, float)) or not -1 <= value <= 1:
            raise ValueError("Impact score must be a float between -1 and 1")

    @staticmethod
    def _validate_iso_date_prefix(value: object) -> None:
        """Validate the basic ISO 8601 date prefix (YYYY-MM-DD)."""
        if (
            not isinstance(value, str)
            or not re.match(r"^\d{4}-\d{2}-\d{2}", value)
        ):
            raise ValueError("Date must be in ISO 8601 format (YYYY-MM-DD...)")

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# Asset Class Definitions
class AssetClass(Enum):
    EQUITY = "Equity"
    FIXED_INCOME = "Fixed Income"
    COMMODITY = "Commodity"
    CURRENCY = "Currency"
    DERIVATIVE = "Derivative"


class RegulatoryActivity(Enum):
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

    def __post_init__(self):
        """Validate asset data after initialization"""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Asset id must be a non-empty string")
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("Asset symbol must be a non-empty string")
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Asset name must be a non-empty string")
        if not isinstance(self.price, (int, float)) or self.price < 0:
            raise ValueError("Asset price must be a non-negative number")
        if self.market_cap is not None and (not isinstance(self.market_cap, (int, float)) or self.market_cap < 0):
            raise ValueError("Market cap must be a non-negative number or None")
        if not re.match(r"^[A-Z]{3}$", self.currency.upper()):
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

    def __post_init__(self):
        """Validate event data after initialization"""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Event id must be a non-empty string")
        if not self.asset_id or not isinstance(self.asset_id, str):
            raise ValueError("Asset id must be a non-empty string")
        if not isinstance(self.impact_score, (int, float)) or not -1 <= self.impact_score <= 1:
            raise ValueError("Impact score must be a float between -1 and 1")
        # Basic ISO 8601 date validation
        if not re.match(r"^\d{4}-\d{2}-\d{2}", self.date):
            raise ValueError("Date must be in ISO 8601 format (YYYY-MM-DD...)")
        if not self.description or not isinstance(self.description, str):
            raise ValueError("Description must be a non-empty string")

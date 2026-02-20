"""Pytest configuration and fixtures for the financial asset relationship
database tests.
"""

from typing import TYPE_CHECKING

import pytest

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


@pytest.fixture
def empty_graph():
    """Provide an empty AssetRelationshipGraph."""
    return AssetRelationshipGraph()


@pytest.fixture
def sample_equity():
    """
    Return a representative Equity asset used by tests.
    
    Returns:
        Equity: An `Equity` instance for Apple Inc. with id "AAPL", symbol "AAPL", asset_class AssetClass.EQUITY, sector "Technology", price 150.0, pe_ratio 25.5, and dividend_yield 0.005.
    """
    return Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=150.0,
        pe_ratio=25.5,
        dividend_yield=0.005,
    )


@pytest.fixture
def sample_bond():
    """
    Create a sample Bond asset used in tests.
    
    The returned Bond represents a fixed-income instrument issued by the sample equity with:
    id "AAPL_BOND", symbol "AAPL_B", issuer_id "AAPL", asset_class FIXED_INCOME, sector "Technology",
    price 100.0, yield_to_maturity 0.03, and credit_rating "AAA".
    
    Returns:
        Bond: A Bond instance populated with the values described above.
    """
    return Bond(
        id="AAPL_BOND",
        symbol="AAPL_B",
        name="Apple Bond",
        asset_class=AssetClass.FIXED_INCOME,
        sector="Technology",
        price=100.0,
        issuer_id="AAPL",
        yield_to_maturity=0.03,
        credit_rating="AAA",
    )


@pytest.fixture
def sample_commodity():
    """
    Create a sample Commodity asset for tests.
    
    Returns:
        Commodity: A Commodity instance representing gold with id "GOLD", symbol "GC", name "Gold", asset_class AssetClass.COMMODITY, sector "Metals", price 2000.0, contract_size 100.0, and volatility 0.15.
    """
    return Commodity(
        id="GOLD",
        symbol="GC",
        name="Gold",
        asset_class=AssetClass.COMMODITY,
        sector="Metals",
        price=2000.0,
        contract_size=100.0,
        volatility=0.15,
    )


@pytest.fixture
def sample_currency():
    """
    Return a sample Currency asset representing the Euro.
    
    Returns:
        Currency: Currency asset with id "EUR", symbol "EUR", name "Euro", asset_class AssetClass.CURRENCY, sector "Currency", price 1.1, exchange_rate 1.1, and country "Eurozone".
    """
    return Currency(
        id="EUR",
        symbol="EUR",
        name="Euro",
        asset_class=AssetClass.CURRENCY,
        sector="Currency",
        price=1.1,
        exchange_rate=1.1,
        country="Eurozone",
    )


@pytest.fixture
def sample_regulatory_event():
    """
    Create a sample RegulatoryEvent for use in tests.
    
    Returns:
        RegulatoryEvent: Event with id "EVENT_001", asset_id "TEST_AAPL", event_type earnings report, date "2024-01-01", description "Earnings report", impact_score 0.8, and related_assets ["AAPL_BOND"].
    """
    return RegulatoryEvent(
        id="EVENT_001",
        asset_id="TEST_AAPL",
        event_type=RegulatoryActivity.EARNINGS_REPORT,
        date="2024-01-01",
        description="Earnings report",
        impact_score=0.8,
        related_assets=["AAPL_BOND"],
    )


@pytest.fixture
def populated_graph(
    sample_equity,
    sample_bond,
    sample_commodity,
    sample_currency,
    sample_regulatory_event,
):
    """Provide a populated AssetRelationshipGraph with 4 assets and 1 event."""
    graph = AssetRelationshipGraph()
    graph.add_asset(sample_equity)
    graph.add_asset(sample_bond)
    graph.add_asset(sample_commodity)
    graph.add_asset(sample_currency)
    graph.add_regulatory_event(sample_regulatory_event)
    graph.build_relationships()
    return graph


if TYPE_CHECKING:
    from _pytest.config.argparsing import Parser


def pytest_addoption(parser: "Parser") -> None:
    """
    Register dummy coverage command-line options when pytest-cov is unavailable.

    If the `pytest-cov` plugin cannot be imported this registers `--cov` and
    `--cov-report` as benign, appendable options so test runs that include those
    flags do not error. If `pytest-cov` is importable this function has no effect.

    Parameters:
        parser (Parser): Pytest argument parser used to add the command-line options.
    """
    try:
        import pytest_cov  # type: ignore  # noqa: F401
    except ImportError:  # pragma: no cover
        _register_dummy_cov_options(parser)


def _register_dummy_cov_options(parser: "Parser") -> None:  # pragma: no cover
    """Register dummy --cov and --cov-report options."""
    group = parser.getgroup("cov")
    group.addoption(
        "--cov",
        action="append",
        dest="cov",
        default=[],
        metavar="path",
        help="Dummy option registered when pytest-cov is unavailable.",
    )
    group.addoption(
        "--cov-report",
        action="append",
        dest="cov_report",
        default=[],
        metavar="type",
        help="Dummy option registered when pytest-cov is unavailable.",
    )


@pytest.fixture
def _reset_graph():
    """Reset the graph singleton between tests."""
    from api.main import reset_graph

    reset_graph()
    yield


@pytest.fixture
def dividend_stock():
    """
    Provide a sample Equity representing a dividend-paying stock for tests.

    Returns:
        Equity: An Equity instance configured for testing with id "DIV_STOCK",
            symbol "DIVS", sector "Utilities", price 100.0,
            dividend_yield 0.04 and other common financial fields populated.
    """
    return Equity(
        id="DIV_STOCK",
        symbol="DIVS",
        name="Dividend Stock",
        asset_class=AssetClass.EQUITY,
        sector="Utilities",
        price=100.0,
        market_cap=1e10,
        pe_ratio=15.0,
        dividend_yield=0.04,
        earnings_per_share=6.67,
    )
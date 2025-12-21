"""Pytest configuration and fixtures for the financial asset relationship database tests."""

from typing import TYPE_CHECKING

import pytest

from src.models.financial_models import AssetClass, Equity

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
        Equity: An Equity instance configured for testing with id "DIV_STOCK", symbol "DIVS", sector "Utilities", price 100.0, dividend_yield 0.04 and other common financial fields populated.
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

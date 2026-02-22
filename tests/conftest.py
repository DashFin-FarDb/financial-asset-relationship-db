"""Pytest configuration and fixtures for the financial asset relationship
database tests.
"""

import os
from pathlib import Path
import shutil
from uuid import uuid4

# Ensure required API environment variables are set before any imports that
# initialize the database/auth layers.
REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_ROOT = REPO_ROOT / "repo-temp-base"
CACHE_ROOT = REPO_ROOT / "pytest_cache"
TMP_ROOT.mkdir(parents=True, exist_ok=True)
CACHE_ROOT.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("TMP", str(TMP_ROOT))
os.environ.setdefault("TEMP", str(TMP_ROOT))
os.environ.setdefault("TMPDIR", str(TMP_ROOT))
os.environ.setdefault("PYTEST_BASETEMP", str(TMP_ROOT))
os.environ.setdefault("PYTEST_CACHE_DIR", str(CACHE_ROOT))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-ci"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "adminpass"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_FULL_NAME"] = "Admin User"

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
    """Provide a sample Equity asset."""
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
    """Provide a sample Bond asset."""
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
    """Provide a sample Commodity asset."""
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
    """Provide a sample Currency asset."""
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
    """Provide a sample RegulatoryEvent."""
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


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest temp and cache directories for restricted environments."""
    if config.option.basetemp is None:
        config.option.basetemp = os.environ["PYTEST_BASETEMP"]

    cache_dir = Path(os.environ["PYTEST_CACHE_DIR"]).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    config.cache._cachedir = cache_dir


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int):
    """Avoid hard failures when temp cleanup lacks permissions."""
    outcome = yield
    if outcome.excinfo and isinstance(outcome.excinfo[1], PermissionError):
        outcome.force_result(None)


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


@pytest.fixture
def tmp_path():
    """Provide a writable temp path without relying on pytest's tmpdir cleanup."""
    temp_dir = TMP_ROOT / f"codex-tmp-{uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

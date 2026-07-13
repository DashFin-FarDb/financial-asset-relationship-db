"""Pytest configuration and fixtures for the database tests."""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Make scripts/ importable for compound unit tests (shared bootstrap; avoid per-module sys.path).
_SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

if TYPE_CHECKING:
    from src.logic.reconciliation_engine import ReconciliationPlan

# Ensure a clean SQLite database for the authentication layer before any modules import it.
_db_path = Path(__file__).resolve().parent / "test_auth.db"
if _db_path.exists():
    _db_path.unlink()

# Enforce hermeticity for test runs
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-bytes-long"
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = os.getenv("TEST_ADMIN_PASSWORD") or "changeme"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_FULL_NAME"] = "Test Admin"
os.environ["ADMIN_DISABLED"] = "false"

from datetime import timezone  # noqa: E402

from src.logic.asset_graph import AssetRelationshipGraph  # noqa: E402
from src.models.financial_models import (  # noqa: E402
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)

UTC = timezone.utc


@pytest.fixture
def empty_graph():
    """Provide an empty AssetRelationshipGraph."""
    return AssetRelationshipGraph()


@pytest.fixture
def sample_equity():
    """
    Create a sample Equity asset configured for tests.

    Returns:
        Equity: An Equity instance with id "AAPL", symbol "AAPL",
            name "Apple Inc.", asset_class AssetClass.EQUITY, sector
            "Technology", price 150.0, pe_ratio 25.5, and dividend_yield 0.005.
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
    Create a sample Bond asset for tests.

    The returned Bond is pre-populated with the following values:
    id "AAPL_BOND", symbol "AAPL_B", name "Apple Bond", asset_class
    FIXED_INCOME, sector "Technology", price 100.0, issuer_id "TEST_AAPL",
    yield_to_maturity 0.03, and credit_rating "AAA".

    Returns:
        Bond: A Bond instance configured with the sample Apple bond values.
    """
    return Bond(
        id="AAPL_BOND",
        symbol="AAPL_B",
        name="Apple Bond",
        asset_class=AssetClass.FIXED_INCOME,
        sector="Technology",
        price=100.0,
        issuer_id="TEST_AAPL",
        yield_to_maturity=0.03,
        credit_rating="AAA",
    )


@pytest.fixture
def sample_commodity():
    """
    Create a sample Commodity asset for tests.

    Returns:
        Commodity: A Commodity representing gold with id "GOLD", symbol "GC",
            sector "Metals", price 2000.0, contract_size 100.0, and
            volatility 0.15.
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
    Create a sample Currency asset configured for tests.

    Returns:
        Currency: A Currency instance with id "EUR", symbol "EUR", name "Euro",
            asset_class AssetClass.CURRENCY, sector "Currency", price 1.1,
            exchange_rate 1.1, and country "Eurozone".
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
    Create a sample RegulatoryEvent representing an earnings report for TEST_AAPL.

    Returns:
        RegulatoryEvent: Instance with id "EVENT_001", asset_id "TEST_AAPL",
            event_type RegulatoryActivity.EARNINGS_REPORT, date "2024-01-01",
            description "Earnings report", impact_score 0.8, and
            related_assets ["AAPL_BOND"].
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


@pytest.fixture
def _reset_graph():
    """Reset the graph singleton between tests."""
    from api.main import reset_graph

    reset_graph()
    yield


def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
    """Execute PRAGMA foreign_keys=ON for an SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Ensure SQLite engines enforce foreign-key constraints in tests."""
    if engine.url.get_backend_name() != "sqlite":
        return

    if not event.contains(engine, "connect", _set_sqlite_pragma):
        event.listen(engine, "connect", _set_sqlite_pragma)


def pytest_addoption(parser: Any) -> None:
    """Register dummy coverage options when pytest-cov is unavailable."""
    if not _cov_plugin_available():
        _register_dummy_cov_options(parser)


def _cov_plugin_available() -> bool:
    """Return whether pytest-cov is importable in the current environment."""
    return importlib.util.find_spec("pytest_cov") is not None


def _register_dummy_cov_options(parser: Any) -> None:
    """Register dummy --cov and --cov-report options."""
    group = parser.getgroup("cov")
    _safe_addoption(
        group,
        "--cov",
        action="append",
        dest="cov",
        default=[],
        metavar="path",
        help="Dummy option registered when pytest-cov is unavailable.",
    )
    _safe_addoption(
        group,
        "--cov-report",
        action="append",
        dest="cov_report",
        default=[],
        metavar="type",
        help="Dummy option registered when pytest-cov is unavailable.",
    )


def _safe_addoption(group: Any, *names: str, **kwargs: object) -> None:
    """Add a pytest option while ignoring duplicate-registration errors only."""
    try:
        group.addoption(*names, **kwargs)  # type: ignore[attr-defined]
    except ValueError as exc:
        if "already added" not in str(exc):
            raise


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


# Fixtures for rebuild drift evaluator tests


@pytest.fixture
def mock_session_factory():
    """Create a mock session factory for drift evaluator tests."""
    from unittest.mock import MagicMock, Mock

    session_factory = Mock()
    mock_session = MagicMock()
    session_factory.return_value = mock_session
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None
    return session_factory, mock_session


@pytest.fixture
def mock_lock():
    """Create a mock distributed lock for drift evaluator tests."""
    from unittest.mock import Mock

    return Mock()


@pytest.fixture
def mock_rebuild_job():
    """Create mock rebuild jobs with specific configurations."""
    from datetime import datetime
    from unittest.mock import Mock

    from src.data.db_models import RebuildJobStatus

    def _make_job(
        job_id: str = "test-job-123",
        status=None,
        active_worker_id: str | None = "worker-456",
        heartbeat_at: datetime | None = None,
    ):
        """Build a mock RebuildJob with configurable fields for tests."""
        if status is None:
            status = RebuildJobStatus.RUNNING
        if heartbeat_at is None:
            heartbeat_at = datetime.now(UTC)

        job = Mock()
        job.job_id = job_id
        job.status = status
        job.active_worker_id = active_worker_id
        job.last_heartbeat_at = heartbeat_at
        return job

    return _make_job


@pytest.fixture
def make_reconciliation_plan() -> Callable[..., ReconciliationPlan]:
    """Return a factory function to create ReconciliationPlan instances for testing."""
    from datetime import datetime

    from src.logic.reconciliation_engine import (
        ActionType,
        ExecutionMode,
        ExecutionSafety,
        ReconciliationPlan,
        Severity,
    )

    def _make(
        drift_type: str = "none",
        severity: Severity = Severity.NONE,
        actions: tuple[ActionType, ...] = (ActionType.NOOP,),
        target_state: str = "healthy",
        execution_mode: ExecutionMode = ExecutionMode.AUTOMATIC,
        safety_state: ExecutionSafety = ExecutionSafety.CONVERGED,
        reason: str = "Graph is healthy",
        metadata: dict[str, str | int | float | bool | None] | None = None,
        created_at: datetime | None = None,
    ) -> ReconciliationPlan:
        """Build a ReconciliationPlan with sensible defaults for tests."""
        if metadata is None:
            metadata = {}
        if created_at is None:
            created_at = datetime.now(UTC)
        return ReconciliationPlan(
            drift_type=drift_type,
            severity=severity,
            actions=actions,
            target_state=target_state,
            execution_mode=execution_mode,
            safety_state=safety_state,
            reason=reason,
            metadata=metadata,
            created_at=created_at,
        )

    return _make

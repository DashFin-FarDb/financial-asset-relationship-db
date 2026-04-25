"""
Pytest configuration and shared fixtures.

This file centralizes:
- Database engine/session fixtures (SQLite file or in-memory)
- Environment isolation for tests
- Coverage flag compatibility when pytest-cov is unavailable
- Common test helpers (e.g., factories) to avoid repeated boilerplate
"""

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.database import (
    Base,
    create_engine_from_url,
    create_session_factory,
    session_scope,
)


def _cov_plugin_available() -> bool:
    """Return whether pytest-cov is importable in the current environment."""
    return importlib.util.find_spec("pytest_cov") is not None


def pytest_addoption(parser: Any) -> None:
    """Register fallback pytest-cov options when pytest-cov is unavailable."""
    if not _cov_plugin_available():
        _register_dummy_cov_options(parser)


def _safe_addoption(group: Any, *names: str, **kwargs: object) -> None:
    """Add a pytest option while ignoring duplicate-registration errors only."""
    try:
        group.addoption(*names, **kwargs)  # type: ignore[attr-defined]
    except ValueError as exc:
        if "already added" not in str(exc):
            raise


def _register_dummy_cov_options(parser: Any) -> None:
    """Register no-op coverage options when pytest-cov is unavailable."""
    group = parser.getgroup("cov")

    # Flags that take optional values (can be used with or without arguments)
    _safe_addoption(
        group,
        "--cov",
        action="append",
        dest="cov_source",
        default=[],
        nargs="?",
        const=True,
        metavar="SOURCE",
    )
    _safe_addoption(
        group,
        "--cov-report",
        action="append",
        dest="cov_report",
        default=[],
        metavar="TYPE",
    )

    # Flags that take required values
    _safe_addoption(group, "--cov-config", action="store", dest="cov_config", default=None, metavar="PATH")
    _safe_addoption(group, "--cov-context", action="store", dest="cov_context", default=None, metavar="CONTEXT")
    _safe_addoption(group, "--cov-fail-under", action="store", dest="cov_fail_under", default=None, metavar="MIN")

    # Boolean flags
    _safe_addoption(group, "--cov-append", action="store_true", dest="cov_append", default=False)
    _safe_addoption(group, "--cov-branch", action="store_true", dest="cov_branch", default=False)
    _safe_addoption(group, "--cov-reset", action="store_true", dest="cov_reset", default=False)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove developer or production environment variables from each test."""
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    monkeypatch.delenv("USE_REAL_DATA_FETCHER", raising=False)
    monkeypatch.delenv("GRAPH_CACHE_PATH", raising=False)
    monkeypatch.delenv("REAL_DATA_CACHE_PATH", raising=False)


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    """Return a temporary SQLite database URL for tests."""
    db_path = tmp_path / "test_asset_graph.db"
    return f"sqlite:///{db_path}"


@pytest.fixture()
def engine(database_url: str) -> Iterator:
    """Create a test database engine and dispose it after use."""
    eng = create_engine_from_url(database_url)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a SQLAlchemy session factory bound to the test engine."""
    return create_session_factory(engine)


@pytest.fixture()
def db_session(session_factory: Any) -> Iterator:
    """Yield a transaction-scoped database session for tests."""
    with session_scope(session_factory) as session:
        yield session

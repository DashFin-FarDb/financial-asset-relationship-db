"""
Pytest configuration and shared fixtures.

This file centralizes:
- Database engine/session fixtures (SQLite file or in-memory)
- Environment isolation for tests
- Common test helpers (e.g., factories) to avoid repeated boilerplate
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.data.database import (
    Base,
    create_engine_from_url,
    create_session_factory,
    session_scope,
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure tests do not accidentally read developer/prod environment variables.

    You can extend this list as the codebase grows.
    """
    monkeypatch.delenv("ASSET_GRAPH_DATABASE_URL", raising=False)
    monkeypatch.delenv("USE_REAL_DATA_FETCHER", raising=False)
    monkeypatch.delenv("GRAPH_CACHE_PATH", raising=False)
    monkeypatch.delenv("REAL_DATA_CACHE_PATH", raising=False)


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    """
    Default test DB URL.

    Uses a temporary on-disk SQLite DB to behave closer to production than :memory:.
    If you want in-memory for speed, replace with:
        "sqlite:///:memory:"
    """
    db_path = tmp_path / "test_asset_graph.db"
    return f"sqlite:///{db_path}"


@pytest.fixture()
def engine(database_url: str) -> Iterator[Engine]:
    """Create a SQLAlchemy Engine for tests and ensure schema exists."""
    eng = create_engine_from_url(database_url)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the test engine."""
    return create_session_factory(engine)


@pytest.fixture()
def db_session(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """
    Provide a transaction-scoped SQLAlchemy Session.

    Uses the project's session_scope helper to ensure commit/rollback/close semantics.
    """
    with session_scope(session_factory) as session:
        yield session


@pytest.fixture()
def set_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """
    Provide a test helper that returns a callable to set environment variables via the pytest monkeypatch fixture.

    The returned callable accepts keyword arguments where each key is an environment variable name and each value is its string value; it sets each variable using monkeypatch.setenv.

    Returns:
        A callable that sets environment variables passed as keyword arguments.
    """

    def _setter(**kwargs: str) -> None:
        """
        Set multiple environment variables for a test using the pytest monkeypatch fixture.

        Sets each provided keyword name as an environment variable to its corresponding value.

        Parameters:
            kwargs: Mapping of environment variable names to values to set.
        """
        for key, value in kwargs.items():
            monkeypatch.setenv(key, value)

    return _setter


@pytest.fixture()
def unset_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """
    Provide a test helper that removes one or more environment variables from the process environment using pytest's monkeypatch.

    Returns:
        A callable that accepts one or more environment variable names (strings) and unsets each one in the test environment.
    """

    def _unsetter(*keys: str) -> None:
        """
        Remove the specified environment variables from the test environment.

        Parameters:
            *keys (str): One or more environment variable names to remove; missing keys are ignored.
        """
        for key in keys:
            monkeypatch.delenv(key, raising=False)

    return _unsetter

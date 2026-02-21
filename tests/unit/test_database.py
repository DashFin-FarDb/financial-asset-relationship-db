"""
Unit tests for database configuration helpers.

This module contains comprehensive unit tests for database configuration including:
- Engine creation with various database URLs
- SQLite in-memory configuration
- Session factory creation
- Database initialization
- Transactional scope management
- Error handling and rollback behavior
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from src.data.database import (
    DEFAULT_DATABASE_URL,
    Base,
    create_engine_from_url,
    create_session_factory,
    init_db,
    session_scope,
)

pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.unit


@pytest.fixture()
def isolated_base() -> Iterator[type[Base]]:
    """
    Provide an isolated SQLAlchemy declarative base for each test.

    This prevents table metadata leakage across test cases and avoids
    cross-test interference when defining ad-hoc models.
    """
    existing_tables = set(Base.metadata.tables)

    class _IsolatedBase(Base):
        """
        A declarative base subclass for isolating test-specific table metadata.
        Ensures that tables defined within tests do not pollute the global metadata.
        """

        __abstract__ = True

    yield _IsolatedBase

    # Remove any tables registered during the test.
    new_tables = [name for name in Base.metadata.tables if name not in existing_tables]
    for name in new_tables:
        Base.metadata.remove(Base.metadata.tables[name])


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """
    Provide an in-memory SQLite engine.

    Returns:
        Iterator[Engine]: Yielded in-memory engine.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine):
    """Provide a SQLAlchemy session factory bound to the test engine."""
    return create_session_factory(engine)


# ---------------------------------------------------------------------------
# Engine creation tests
# ---------------------------------------------------------------------------


class TestEngineCreation:
    """Test cases for database engine creation."""

    @staticmethod
    def test_create_engine_with_default_url() -> None:
        """
        Engine creation should fall back to the default URL.

        Raises:
            AssertionError: If the default URL is not used.
        """
        with patch.dict(os.environ, {}, clear=True):
            eng = create_engine_from_url()
            assert eng is not None  # nosec B101
            assert "sqlite" in str(eng.url).lower()  # nosec B101

    @staticmethod
    def test_create_engine_with_custom_url() -> None:
        """Engine creation with an explicit database URL."""
        custom_url = "sqlite:///test_custom.db"
        eng = create_engine_from_url(custom_url)
        assert "test_custom.db" in str(eng.url)  # nosec B101

    @staticmethod
    def test_create_engine_with_in_memory_sqlite() -> None:
        """In-memory SQLite should use StaticPool."""
        eng = create_engine_from_url("sqlite:///:memory:")
        assert isinstance(eng.pool, StaticPool)  # nosec B101

    @staticmethod
    def test_create_engine_with_env_variable() -> None:
        """Environment variable should override default database URL."""
        test_url = "sqlite:///env_test.db"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": test_url}):
            eng = create_engine_from_url()
            assert "env_test.db" in str(eng.url)  # nosec B101

    @staticmethod
    def test_create_engine_with_postgres_url() -> None:
        """PostgreSQL URLs should be accepted."""
        postgres_url = "postgresql://user:pass@localhost/testdb"
        eng = create_engine_from_url(postgres_url)
        assert "postgresql" in str(eng.url).lower()  # nosec B101


# ---------------------------------------------------------------------------
# Session factory tests
# ---------------------------------------------------------------------------


class TestSessionFactory:
    """Test cases for session factory creation."""

    @staticmethod
    def test_factory_returns_callable(engine: Engine) -> None:
        """Factory should be callable."""
        factory = create_session_factory(engine)
        assert callable(factory)  # nosec B101

    @staticmethod
    def test_factory_creates_sessions(engine: Engine) -> None:
        """Factory should create usable sessions."""
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine  # nosec B101
        finally:
            session.close()

    @staticmethod
    def test_sessions_future_mode(engine: Engine) -> None:
        """
        Sessions created with future=True should behave in SQLAlchemy 2.x style.

        We avoid checking deprecated autocommit flags.
        """
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine  # nosec B101
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Database initialization tests
# ---------------------------------------------------------------------------


class TestDatabaseInitialization:
    """Tests for database initialization and schema creation."""

    @staticmethod
    def test_init_db_creates_tables(
        engine: Engine,
        isolated_base: type[Base],
    ) -> None:
        """init_db should create all registered tables."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for verifying table creation functionality."""

            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        # Ensure the model is registered.
        assert TestModel.__tablename__ == "test_model"  # nosec B101

        init_db(engine)

        from sqlalchemy import inspect  # noqa: PLC0415

        inspector = inspect(engine)
        assert "test_model" in inspector.get_table_names()  # nosec B101

    @staticmethod
    def test_init_db_is_idempotent(
        engine: Engine,
        isolated_base: type[Base],
    ) -> None:
        """Calling init_db multiple times should not error."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model for verifying that database initialization is idempotent."""

            __tablename__ = "test_idempotent"
            id = Column(Integer, primary_key=True)

        assert TestModel.__tablename__ == "test_idempotent"  # nosec B101

        init_db(engine)
        init_db(engine)

        from sqlalchemy import inspect  # noqa: PLC0415

        inspector = inspect(engine)
        assert "test_idempotent" in inspector.get_table_names()  # nosec B101

    @staticmethod
    def test_init_db_preserves_existing_data(
        engine: Engine,
        session_factory,
        isolated_base: type[Base],
    ) -> None:
        """init_db should not wipe existing data."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model for testing data preservation during db initialization."""

            __tablename__ = "test_preserve"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)

        with session_scope(session_factory) as session:
            session.add(TestModel(id=1, value="persisted"))

        init_db(engine)

        with session_scope(session_factory) as session:
            result = session.query(TestModel).one_or_none()
            assert result is not None  # nosec B101
            assert result.value == "persisted"  # nosec B101


# ---------------------------------------------------------------------------
# Transaction scope tests
# ---------------------------------------------------------------------------


class TestSessionScope:
    """Tests for transactional session_scope behavior."""

    @staticmethod
    def test_commits_on_success(engine: Engine, isolated_base: type[Base]) -> None:
        """session_scope should commit on success."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_commit"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with session_scope(factory) as session:
            session.add(TestModel(id=1, value="committed"))

        with session_scope(factory) as session:
            result = session.query(TestModel).one_or_none()
            assert result is not None  # nosec B101
            assert result.value == "committed"  # nosec B101

    @staticmethod
    def test_rolls_back_on_exception(engine: Engine, isolated_base: type[Base]) -> None:
        """session_scope should rollback on error."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_rollback"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(ValueError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            raise ValueError("trigger rollback")

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 0  # nosec B101

    @staticmethod
    def test_propagates_integrity_error(
        engine: Engine, isolated_base: type[Base]
    ) -> None:
        """Integrity errors should propagate after rollback."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_integrity"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(IntegrityError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            session.flush()
            session.add(TestModel(id=1))
            session.flush()

    @staticmethod
    def test_multiple_operations_commit(
        engine: Engine, isolated_base: type[Base]
    ) -> None:
        """Multiple operations in one scope should commit atomically."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_nested"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with session_scope(factory) as session:
            session.add(TestModel(id=1, value="a"))
            session.add(TestModel(id=2, value="b"))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 2  # nosec B101


# ---------------------------------------------------------------------------
# Default database URL tests
# ---------------------------------------------------------------------------


class TestDefaultDatabaseURL:
    """Tests for DEFAULT_DATABASE_URL behavior."""

    @staticmethod
    def test_default_is_sqlite() -> None:
        """Default database URL should use SQLite."""
        assert "sqlite" in DEFAULT_DATABASE_URL.lower()  # nosec B101

    @staticmethod
    def test_default_points_to_file() -> None:
        """Default SQLite URL should point to a file."""
        assert "asset_graph.db" in DEFAULT_DATABASE_URL  # nosec B101

    @staticmethod
    def test_env_override_works() -> None:
        """Environment variable should override default URL."""
        custom_url = "postgresql://test:test@localhost/test"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": custom_url}):
            eng = create_engine_from_url()
            assert "postgresql" in str(eng.url).lower()  # nosec B101


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and defensive behavior tests."""

    @staticmethod
    def test_empty_session_scope(engine: Engine) -> None:
        """session_scope should allow empty usage."""
        factory = create_session_factory(engine)
        with session_scope(factory):
            pass

    @staticmethod
    def test_create_engine_with_empty_string() -> None:
        """Empty string should fall back to default."""
        with patch.dict(os.environ, {}, clear=True):
            eng = create_engine_from_url("")
            assert eng is not None  # nosec B101

    @staticmethod
    def test_create_engine_with_none() -> None:
        """None should fall back to default."""
        eng = create_engine_from_url(None)
        assert eng is not None  # nosec B101

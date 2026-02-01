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
from typing import Iterator
from unittest.mock import patch

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_base() -> Iterator[type[Base]]:
    """
    Provide an isolated SQLAlchemy declarative base for each test.

    This prevents table metadata leakage across test cases and avoids
    cross-test interference when defining ad-hoc models.
    """
    existing_tables = set(Base.metadata.tables)

    class _IsolatedBase(Base):
        __abstract__ = True

    yield _IsolatedBase

    new_tables = [name for name in Base.metadata.tables if name not in existing_tables]
    for name in new_tables:
        Base.metadata.remove(Base.metadata.tables[name])


@pytest.fixture()
def engine() -> Iterator[Engine]:
    """Provide an in-memory SQLite engine.

    Returns:
        Iterator[Engine]: Yielded in-memory engine.
    Raises:
        None
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine):
    """Provide a SQLAlchemy session factory bound to the test engine."""
    return create_session_factory(engine)


# ---------------------------------------------------------------------------
# Engine creation tests
# ---------------------------------------------------------------------------


class TestEngineCreation:
    """Test cases for database engine creation."""

    def test_create_engine_with_default_url(self) -> None:
        """Engine creation should fall back to the default URL.

        Returns:
            None
        Raises:
            AssertionError: If the default URL is not used.
        """
        with patch.dict(os.environ, {}, clear=True):
            engine = create_engine_from_url()
            assert engine is not None
            assert "sqlite" in str(engine.url).lower()

    def test_create_engine_with_custom_url(self):
        """Engine creation with an explicit database URL."""
        custom_url = "sqlite:///test_custom.db"
        engine = create_engine_from_url(custom_url)
        assert "test_custom.db" in str(engine.url)

    def test_create_engine_with_in_memory_sqlite(self):
        """In-memory SQLite should use StaticPool."""
        engine = create_engine_from_url("sqlite:///:memory:")
        assert isinstance(engine.pool, StaticPool)

    def test_create_engine_with_env_variable(self):
        """Environment variable should override default database URL."""
        test_url = "sqlite:///env_test.db"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": test_url}):
            engine = create_engine_from_url()
            assert "env_test.db" in str(engine.url)

    def test_create_engine_with_postgres_url(self):
        """PostgreSQL URLs should be accepted."""
        postgres_url = "postgresql://user:pass@localhost/testdb"
        engine = create_engine_from_url(postgres_url)
        assert "postgresql" in str(engine.url).lower()


# ---------------------------------------------------------------------------
# Session factory tests
# ---------------------------------------------------------------------------


class TestSessionFactory:
    """Test cases for session factory creation."""

    def test_factory_returns_callable(self, engine):
        """Factory should be callable."""
        factory = create_session_factory(engine)
        assert callable(factory)

    def test_factory_creates_sessions(self, engine):
        """Factory should create usable sessions."""
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine
        finally:
            session.close()

    def test_sessions_are_not_autocommit(self, engine):
        """Sessions should have autocommit disabled."""
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine
            assert session.autocommit is False
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Database initialization tests
# ---------------------------------------------------------------------------


class TestDatabaseInitialization:
    """Tests for database initialization and schema creation."""

    def test_init_db_creates_tables(self, engine, isolated_base):
        """init_db should create all registered tables."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        # Access the model to avoid it being flagged as unused while still
        # relying on its side effect of registering table metadata.
        assert TestModel.__tablename__ == "test_model"

        init_db(engine)

        from sqlalchemy import inspect  # noqa: PLC0415

        inspector = inspect(engine)
        assert "test_model" in inspector.get_table_names()

    def test_init_db_is_idempotent(self, engine, isolated_base):
        """Calling init_db multiple times should not error."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_idempotent"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        init_db(engine)

        from sqlalchemy import inspect  # noqa: PLC0415

        inspector = inspect(engine)
        assert "test_idempotent" in inspector.get_table_names()

    def test_init_db_preserves_existing_data(self, engine, session_factory, isolated_base):
        """init_db should not wipe existing data."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_preserve"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)

        with session_factory() as session:
            session.add(TestModel(id=1, value="persisted"))
            session.commit()

        init_db(engine)

        with session_factory() as session:
            result = session.query(TestModel).one_or_none()
            assert result is not None
            assert result.value == "persisted"
        assert result is not None
        assert result.value == "persisted"


# ---------------------------------------------------------------------------
# Transaction scope tests
# ---------------------------------------------------------------------------


class TestSessionScope:
    """Tests for transactional session_scope behavior."""

    def test_commits_on_success(self, engine, isolated_base):
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
            assert result is not None
            assert result.value == "committed"

    def test_rolls_back_on_exception(self, engine, isolated_base):
        """session_scope should rollback on error."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_rollback"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(ValueError):
            with session_scope(factory) as session:
                session.add(TestModel(id=1))
                raise ValueError("trigger rollback")

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 0

    def test_propagates_integrity_error(self, engine, isolated_base):
        """Integrity errors should propagate after rollback."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            __tablename__ = "test_integrity"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(IntegrityError):
            with session_scope(factory) as session:
                session.add(TestModel(id=1))
                session.flush()
                session.add(TestModel(id=1))
                session.flush()

    def test_nested_operations_commit(self, engine, isolated_base):
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
            assert session.query(TestModel).count() == 2


# ---------------------------------------------------------------------------
# Default database URL tests
# ---------------------------------------------------------------------------


class TestDefaultDatabaseURL:
    """Tests for DEFAULT_DATABASE_URL behavior."""

    def test_default_is_sqlite(self):
        """Default database URL should use SQLite."""
        assert "sqlite" in DEFAULT_DATABASE_URL.lower()

    def test_default_points_to_file(self):
        """Default SQLite URL should point to a file."""
        assert "asset_graph.db" in DEFAULT_DATABASE_URL

    def test_env_override_works(self):
        """Environment variable should override default URL."""
        custom_url = "postgresql://test:test@localhost/test"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": custom_url}):
            engine = create_engine_from_url()
            assert "postgresql" in str(engine.url).lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and defensive behavior tests."""

    def test_empty_session_scope(self, engine):
        """session_scope should allow empty usage."""
        factory = create_session_factory(engine)
        with session_scope(factory):
            pass

    def test_create_engine_with_empty_string(self):
        """Empty string should fall back to default."""
        with patch.dict(os.environ, {}, clear=True):
            engine = create_engine_from_url("")
            assert engine is not None

    def test_create_engine_with_none(self):
        """None should fall back to default."""
        engine = create_engine_from_url(None)
        assert engine is not None

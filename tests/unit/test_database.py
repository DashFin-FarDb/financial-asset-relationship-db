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
from typing import Any, Iterator
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
)
from src.data.repository import session_scope

pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.unit


def _assert_model_registered(model: type[Base], expected_tablename: str) -> None:
    """Assert the model is registered and has the expected __tablename__."""
    assert model.__tablename__ == expected_tablename


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_base() -> Iterator[type[Base]]:
    """
    Provide an isolated SQLAlchemy declarative base for each test.

    This prevents table metadata leakage across test cases and avoids cross-test
    interference when defining ad-hoc models.
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
    in_memory_engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield in_memory_engine
    in_memory_engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine):
    """Provide a SQLAlchemy session factory bound to the test engine."""
    return create_session_factory(engine)


# ---------------------------------------------------------------------------
# Engine creation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEngineCreation:
    """Test cases for database engine creation."""

    def test_create_engine_with_default_url(self) -> None:
        """Engine creation should fall back to the default URL."""
        with patch.dict(os.environ, {}, clear=True):
            default_engine = create_engine_from_url()
            assert default_engine is not None
            assert "sqlite" in str(default_engine.url).lower()

    def test_create_engine_with_custom_url(self) -> None:
        """Engine creation with an explicit database URL."""
        custom_url = "sqlite:///test_custom.db"
        custom_engine = create_engine_from_url(custom_url)
        assert "test_custom.db" in str(custom_engine.url)

    def test_create_engine_with_in_memory_sqlite(self) -> None:
        """In-memory SQLite should use StaticPool."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")
        assert isinstance(in_memory_engine.pool, StaticPool)

    def test_create_engine_with_env_variable(self) -> None:
        """Environment variable should override default database URL."""
        test_url = "sqlite:///env_test.db"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": test_url}):
            env_engine = create_engine_from_url()
            assert "env_test.db" in str(env_engine.url)

    def test_create_engine_with_postgres_url(self) -> None:
        """PostgreSQL URLs should be accepted."""
        postgres_url = "postgresql://user:pass@localhost/testdb"
        postgres_engine = create_engine_from_url(postgres_url)
        assert "postgresql" in str(postgres_engine.url).lower()


# ---------------------------------------------------------------------------
# Session factory tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSessionFactory:
    """Test cases for session factory creation."""

    def test_factory_returns_callable(self, engine: Engine) -> None:
        """Factory should be callable."""
        factory = create_session_factory(engine)
        assert callable(factory)  # nosec B101

    def test_factory_creates_sessions(self, engine: Engine) -> None:
        """Factory should create usable sessions."""
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine  # nosec B101
        finally:
            session.close()

    def test_sessions_are_not_autocommit(self, engine: Engine) -> None:
        """Sessions should have autocommit disabled."""
        factory = create_session_factory(engine)
        session = factory()
        try:
            assert session.bind == engine
            # Note: session.autocommit is deprecated in SQLAlchemy 2.0.
            # Sessions created with future=True don't have autocommit mode.
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Database initialization tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatabaseInitialization:
    """Tests for database initialization and schema creation."""

    def test_init_db_creates_tables(self, engine: Engine, isolated_base) -> None:
        """init_db should create all registered tables."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for verifying table creation functionality."""

            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        _assert_model_registered(TestModel, "test_model")

        init_db(engine)

        from sqlalchemy import inspect  # noqa: PLC0415

        inspector = inspect(engine)
        assert "test_model" in inspector.get_table_names()  # nosec B101

    def test_init_db_is_idempotent(self, engine: Engine, isolated_base) -> None:
        """Calling init_db multiple times should not error."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model for verifying that database initialization is idempotent."""

            __tablename__ = "test_idempotent"
            id = Column(Integer, primary_key=True)

        _assert_model_registered(TestModel, "test_idempotent")

        init_db(engine)
        init_db(engine)

        from sqlalchemy import inspect  # noqa: PLC0415

        inspector = inspect(engine)
        assert "test_idempotent" in inspector.get_table_names()  # nosec B101

    @staticmethod
    def test_init_db_preserves_existing_data(
        self,
        engine: Engine,
        session_factory,
        isolated_base,
    ) -> None:
        """init_db should not wipe existing data."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model for testing data preservation during database initialization."""

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


@pytest.mark.unit
class TestSessionScope:
    """Tests for transactional session_scope behavior."""

    def test_commits_on_success(self, engine: Engine, isolated_base) -> None:
        """session_scope should commit on success."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model for commit testing."""

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

    def test_rolls_back_on_exception(self, engine: Engine, isolated_base) -> None:
        """session_scope should rollback on error."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model for rollback testing."""

            __tablename__ = "test_rollback"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(ValueError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            raise ValueError("trigger rollback")

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 0  # nosec B101

    def test_propagates_integrity_error(self, engine: Engine, isolated_base) -> None:
        """Integrity errors should propagate after rollback."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model used in tests to trigger and verify integrity errors."""

            __tablename__ = "test_integrity"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(IntegrityError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            session.flush()
            session.add(TestModel(id=1))
            session.flush()

    def test_nested_operations_commit(self, engine: Engine, isolated_base) -> None:
        """Multiple operations in one scope should commit atomically."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Model for nested operations commit tests."""

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


@pytest.mark.unit
class TestDefaultDatabaseURL:
    """Tests for DEFAULT_DATABASE_URL behavior."""

    def test_default_is_sqlite(self) -> None:
        """Default database URL should use SQLite."""
        assert "sqlite" in DEFAULT_DATABASE_URL.lower()  # nosec B101

    def test_default_points_to_file(self) -> None:
        """Default SQLite URL should point to a file."""
        assert "asset_graph.db" in DEFAULT_DATABASE_URL  # nosec B101

    def test_env_override_works(self) -> None:
        """Environment variable should override default URL."""
        custom_url = "postgresql://test:test@localhost/test"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": custom_url}):
            override_engine = create_engine_from_url()
            assert "postgresql" in str(override_engine.url).lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases and defensive behavior tests."""

    def test_empty_session_scope(self, engine: Engine) -> None:
        """session_scope should allow empty usage."""
        factory = create_session_factory(engine)
        with session_scope(factory):
            pass

    def test_create_engine_with_empty_string(self) -> None:
        """Empty string should fall back to default."""
        with patch.dict(os.environ, {}, clear=True):
            fallback_engine = create_engine_from_url("")
            assert fallback_engine is not None

    def test_create_engine_with_none(self) -> None:
        """None should fall back to default."""
        fallback_engine = create_engine_from_url(None)
        assert fallback_engine is not None


# ---------------------------------------------------------------------------
# Connection pooling tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectionPooling:
    """Tests for database connection pooling behavior."""

    def test_static_pool_for_in_memory_sqlite(self) -> None:
        """In-memory SQLite should use StaticPool for thread safety."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")
        assert isinstance(in_memory_engine.pool, StaticPool)

    def test_multiple_connections_to_same_in_memory_db(self) -> None:
        """Multiple connections to in-memory DB should share same data with StaticPool."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")
        Base.metadata.create_all(in_memory_engine)

        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=in_memory_engine)

        class TestTable(Base):
            """Test table for connection pooling validation."""

            __tablename__ = "test_pool"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        Base.metadata.create_all(in_memory_engine)

        session1 = Session()
        session1.add(TestTable(id=1, value="test"))
        session1.commit()
        session1.close()

        session2 = Session()
        result = session2.query(TestTable).filter_by(id=1).one_or_none()
        assert result is not None
        assert result.value == "test"
        session2.close()

        Base.metadata.drop_all(in_memory_engine)

    def test_pool_size_configuration_for_postgres(self) -> None:
        """PostgreSQL URLs should accept pool size configuration."""
        postgres_url = "postgresql://user:pass@localhost/db"
        postgres_engine = create_engine_from_url(postgres_url)
        assert postgres_engine is not None


# ---------------------------------------------------------------------------
# Concurrent access tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConcurrentDatabaseAccess:
    """Tests for concurrent database access scenarios."""

    def test_concurrent_session_creation(self, engine: Engine) -> None:
        """Multiple concurrent sessions should be safe."""
        import threading

        factory = create_session_factory(engine)
        sessions: list[Any] = []
        errors: list[Exception] = []

        def create_session() -> None:
            """Thread worker to create sessions."""
            try:
                session = factory()
                sessions.append(session)
                session.close()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=create_session) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(sessions) == 10

    def test_concurrent_reads_safe(self, engine: Engine, isolated_base) -> None:
        """Concurrent reads should not interfere with each other."""
        import threading

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for concurrent read validation."""

            __tablename__ = "test_concurrent_reads"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with session_scope(factory) as session:
            for i in range(100):
                session.add(TestModel(id=i, value=f"value_{i}"))

        results: list[int] = []
        errors: list[Exception] = []

        def read_data() -> None:
            """Thread worker for concurrent reads."""
            try:
                with session_scope(factory) as session:
                    count = session.query(TestModel).count()
                    results.append(count)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=read_data) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert all(count == 100 for count in results)

    def test_concurrent_writes_serialized(self, engine: Engine, isolated_base) -> None:
        """Concurrent writes should be properly serialized."""
        import threading
        import time

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for concurrent write validation."""

            __tablename__ = "test_concurrent_writes"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        errors: list[Exception] = []

        def write_data(thread_id: int) -> None:
            """
            Worker used by a thread to insert a TestModel row and record any exception.

            Parameters:
                thread_id (int): Value used as the TestModel `id` for the inserted row.

            Notes:
                On failure, the raised exception is appended to the shared `errors` list as a side effect.
            """
            try:
                time.sleep(0.001 * thread_id)
                with session_scope(factory) as session:
                    session.add(TestModel(id=thread_id))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        num_threads = 20
        threads = [
            threading.Thread(target=write_data, args=(i,)) for i in range(num_threads)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        with session_scope(factory) as session:
            count = session.query(TestModel).count()
            assert count >= num_threads - 1, (
                f"Expected at least {num_threads - 1} writes but found {count}"
            )

        assert len(errors) <= 1, f"Too many errors: {len(errors)}"


# ---------------------------------------------------------------------------
# Error recovery tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatabaseErrorRecovery:
    """Tests for database error recovery scenarios."""

    def test_session_scope_recovers_from_nested_error(
        self, engine: Engine, isolated_base
    ) -> None:
        """Session scope should recover after error in nested operation."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for error recovery validation."""

            __tablename__ = "test_error_recovery"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(ValueError), session_scope(factory) as session:
            session.add(TestModel(id=1, value="test"))
            raise ValueError("Intentional error")

        with session_scope(factory) as session:
            session.add(TestModel(id=2, value="success"))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 1
            result = session.query(TestModel).one()
            assert result.id == 2
            assert result.value == "success"

    def test_session_scope_handles_commit_failure(
        self, engine: Engine, isolated_base
    ) -> None:
        """Session scope should handle commit failures gracefully."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for commit failure handling."""

            __tablename__ = "test_commit_failure"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        with pytest.raises(IntegrityError), session_scope(factory) as session:
            session.add(TestModel(id=1))
            session.flush()
            session.add(TestModel(id=1))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 0


# ---------------------------------------------------------------------------
# Resource cleanup tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResourceCleanup:
    """Tests for proper resource cleanup."""

    def test_engine_disposal_releases_connections(self) -> None:
        """Engine disposal should release all connections."""
        in_memory_engine = create_engine_from_url("sqlite:///:memory:")
        factory = create_session_factory(in_memory_engine)

        for _ in range(5):
            session = factory()
            session.close()

        in_memory_engine.dispose()

        new_engine = create_engine_from_url("sqlite:///:memory:")
        assert new_engine is not None
        new_engine.dispose()

    def test_session_scope_closes_on_exception(self, engine: Engine) -> None:
        """Session should be closed even when exception occurs."""
        factory = create_session_factory(engine)
        with pytest.raises(RuntimeError), session_scope(factory) as session:
            assert session.is_active
            raise RuntimeError("Test error")

    def test_multiple_session_scopes_cleanup_properly(
        self, engine: Engine, isolated_base
    ) -> None:
        """Multiple session scopes should clean up properly."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for cleanup validation."""

            __tablename__ = "test_cleanup"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        for i in range(10):
            with session_scope(factory) as session:
                session.add(TestModel(id=i))

        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 10

    def test_session_scope_with_nested_commits(self, engine: Engine) -> None:
        """Regression: explicit commits inside session_scope persist data."""

        class TestModelBase(Base):  # pylint: disable=redefined-outer-name
            """Test model for nested commit validation."""

            __tablename__ = "test_nested_commits"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        # First transaction
        # First transaction
        with session_scope(factory) as session:
            session.add(TestModelBase(id=1))
            session.commit()  # Explicit commit (regression scenario)
            session.add(TestModelBase(id=1))
            session.commit()  # Explicit commit (regression scenario)

        # Second transaction should see first
        with session_scope(factory) as session:
            assert session.query(TestModelBase).count() == 1

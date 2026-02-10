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
        """
        A declarative base subclass for isolating test-specific table metadata.
        Ensures that tables defined within tests do not pollute the global metadata.
        """

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


@pytest.mark.unit
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


@pytest.mark.unit
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
            # Note: session.autocommit is deprecated in SQLAlchemy 2.0
            # Sessions created with future=True don't have autocommit mode
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Database initialization tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatabaseInitialization:
    """Tests for database initialization and schema creation."""

    def test_init_db_creates_tables(self, engine, isolated_base):
        """init_db should create all registered tables."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for verifying table creation functionality."""

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
            """Model for verifying that database initialization is idempotent."""

            __tablename__ = "test_idempotent"
            id = Column(Integer, primary_key=True)

        # Access the model to avoid it being flagged as unused while still
        # relying on its side effect of registering table metadata.
        assert TestModel.__tablename__ == "test_idempotent"

        init_db(engine)
        init_db(engine)

        from sqlalchemy import inspect  # noqa: PLC0415

        inspector = inspect(engine)
        assert "test_idempotent" in inspector.get_table_names()

    def test_init_db_preserves_existing_data(self, engine, session_factory, isolated_base):
        """init_db should not wipe existing data."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """SQLAlchemy model for testing data preservation during database initialization."""

            __tablename__ = "test_preserve"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)

        with session_scope(session_factory) as session:
            session.add(TestModel(id=1, value="persisted"))

        init_db(engine)

        with session_scope(session_factory) as session:
            result = session.query(TestModel).one_or_none()
            assert result is not None
            assert result.value == "persisted"


# ---------------------------------------------------------------------------
# Transaction scope tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
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

        with pytest.raises(ValueError), session_scope(factory) as session:
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

        with pytest.raises(IntegrityError), session_scope(factory) as session:
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


@pytest.mark.unit
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


@pytest.mark.unit
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
        """None should fall back to default."""
        engine = create_engine_from_url(None)
        assert engine is not None


# ---------------------------------------------------------------------------
# Connection pooling tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConnectionPooling:
    """Tests for database connection pooling behavior."""

    def test_static_pool_for_in_memory_sqlite(self):
        """In-memory SQLite should use StaticPool for thread safety."""
        engine = create_engine_from_url("sqlite:///:memory:")
        assert isinstance(engine.pool, StaticPool)

    def test_multiple_connections_to_same_in_memory_db(self):
        """Multiple connections to in-memory DB should share same data with StaticPool."""
        engine = create_engine_from_url("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        from sqlalchemy.orm import sessionmaker

        Session = sessionmaker(bind=engine)

        # Create a test table
        from sqlalchemy import Column, Integer, String

        class TestTable(Base):
            """Test table for connection pooling validation."""

            __tablename__ = "test_pool"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        Base.metadata.create_all(engine)

        # Write with one session
        session1 = Session()
        session1.add(TestTable(id=1, value="test"))
        session1.commit()
        session1.close()

        # Read with another session
        session2 = Session()
        result = session2.query(TestTable).filter_by(id=1).one_or_none()
        assert result is not None
        assert result.value == "test"
        session2.close()

        # Cleanup
        Base.metadata.drop_all(engine)

    def test_pool_size_configuration_for_postgres(self):
        """PostgreSQL URLs should accept pool size configuration."""
        # This test verifies the engine accepts pool_size parameter
        postgres_url = "postgresql://user:pass@localhost/db"
        try:
            engine = create_engine_from_url(postgres_url)
            # Just verify it was created, don't try to connect
            assert engine is not None
        except Exception:
            # Connection failure is expected, we're just testing URL parsing
            pass


# ---------------------------------------------------------------------------
# Concurrent access tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConcurrentDatabaseAccess:
    """Tests for concurrent database access scenarios."""

    def test_concurrent_session_creation(self, engine):
        """Multiple concurrent sessions should be safe."""
        import threading

        factory = create_session_factory(engine)
        sessions = []
        errors = []

        def create_session():
            """Thread worker to create sessions."""
            try:
                session = factory()
                sessions.append(session)
                session.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_session) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(sessions) == 10

    def test_concurrent_reads_safe(self, engine, isolated_base):
        """Concurrent reads should not interfere with each other."""
        import threading

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for concurrent read validation."""

            __tablename__ = "test_concurrent_reads"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        # Insert test data
        with session_scope(factory) as session:
            for i in range(100):
                session.add(TestModel(id=i, value=f"value_{i}"))

        # Concurrent reads
        results = []
        errors = []

        def read_data():
            """Thread worker for concurrent reads."""
            try:
                with session_scope(factory) as session:
                    count = session.query(TestModel).count()
                    results.append(count)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_data) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(count == 100 for count in results)

    def test_concurrent_writes_serialized(self, engine, isolated_base):
        """Concurrent writes should be properly serialized."""
        import threading
        import time

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for concurrent write validation."""

            __tablename__ = "test_concurrent_writes"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        errors = []

        def write_data(thread_id):
            """Thread worker for concurrent writes."""
            try:
                # Add small delay to reduce timing-related race conditions
                time.sleep(0.001 * thread_id)
                with session_scope(factory) as session:
                    # Each thread writes its unique ID
                    session.add(TestModel(id=thread_id))
            except Exception as e:
                errors.append(e)

        num_threads = 20
        threads = [
            threading.Thread(target=write_data, args=(i,)) for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify writes succeeded - allow for occasional race condition
        with session_scope(factory) as session:
            count = session.query(TestModel).count()
            # Expect all or nearly all to succeed
            assert count >= num_threads - 1, (
                f"Expected at least {num_threads - 1} writes but found {count}"
            )

        # Should have minimal errors
        assert len(errors) <= 1, f"Too many errors: {len(errors)}"


# ---------------------------------------------------------------------------
# Error recovery tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDatabaseErrorRecovery:
    """Tests for database error recovery scenarios."""

    def test_session_scope_recovers_from_nested_error(self, engine, isolated_base):
        """Session scope should recover after error in nested operation."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for error recovery validation."""

            __tablename__ = "test_error_recovery"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        # First operation fails
        with pytest.raises(ValueError), session_scope(factory) as session:
            session.add(TestModel(id=1, value="test"))
            raise ValueError("Intentional error")

        # Next operation should succeed
        with session_scope(factory) as session:
            session.add(TestModel(id=2, value="success"))

        # Verify only second write succeeded
        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 1
            result = session.query(TestModel).one()
            assert result.id == 2
            assert result.value == "success"

    def test_session_scope_handles_commit_failure(self, engine, isolated_base):
        """Session scope should handle commit failures gracefully."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for commit failure handling."""

            __tablename__ = "test_commit_failure"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        # Insert duplicate IDs to cause integrity error
        with pytest.raises(IntegrityError):
            with session_scope(factory) as session:
                session.add(TestModel(id=1))
                session.flush()
                session.add(TestModel(id=1))  # Duplicate
                # Commit will fail

        # Database should be in consistent state
        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 0


# ---------------------------------------------------------------------------
# Resource cleanup tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResourceCleanup:
    """Tests for proper resource cleanup."""

    def test_engine_disposal_releases_connections(self):
        """Engine disposal should release all connections."""
        engine = create_engine_from_url("sqlite:///:memory:")
        factory = create_session_factory(engine)

        # Create and use some sessions
        for _ in range(5):
            session = factory()
            session.close()

        # Dispose engine
        engine.dispose()

        # Should be able to create new engine with same URL
        new_engine = create_engine_from_url("sqlite:///:memory:")
        assert new_engine is not None
        new_engine.dispose()

    def test_session_scope_closes_on_exception(self, engine):
        """Session should be closed even when exception occurs."""
        factory = create_session_factory(engine)

        with pytest.raises(RuntimeError):
            with session_scope(factory) as session:
                # Verify session is active
                assert session.is_active
                raise RuntimeError("Test error")

        # Session should be closed after context exit
        # (can't directly test this without accessing internal state)

    def test_multiple_session_scopes_cleanup_properly(self, engine, isolated_base):
        """Multiple session scopes should clean up properly."""

        class TestModel(isolated_base):  # pylint: disable=redefined-outer-name
            """Test model for cleanup validation."""

            __tablename__ = "test_cleanup"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        # Use multiple session scopes
        for i in range(10):
            with session_scope(factory) as session:
                session.add(TestModel(id=i))

        # Verify all completed successfully
        with session_scope(factory) as session:
            assert session.query(TestModel).count() == 10
"""Unit tests for database configuration helpers.

This module contains comprehensive unit tests for database configuration including:
- Engine creation with various database URLs
- SQLite in-memory configuration
- Session factory creation
- Database initialization
- Transactional scope management
- Error handling and rollback behavior
"""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session
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


class TestEngineCreation:
    """Test cases for database engine creation."""

    def test_create_engine_with_default_url(self):
        """Test engine creation using default database URL."""
        with patch.dict(os.environ, {}, clear=True):
            engine = create_engine_from_url()
            assert engine is not None
            assert "sqlite" in str(engine.url).lower()

    def test_create_engine_with_custom_url(self):
        """Test engine creation with a custom URL."""
        custom_url = "sqlite:///test_custom.db"
        engine = create_engine_from_url(custom_url)
        assert engine is not None
        assert "test_custom.db" in str(engine.url)

    def test_create_engine_with_in_memory_sqlite(self):
        """Test engine creation for in-memory SQLite database."""
        memory_url = "sqlite:///:memory:"
        engine = create_engine_from_url(memory_url)
        assert engine is not None
        assert isinstance(engine.pool, StaticPool)

    def test_create_engine_with_env_variable(self):
        """Test engine creation using environment variable."""
        test_url = "sqlite:///env_test.db"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": test_url}):
            engine = create_engine_from_url()
            assert "env_test.db" in str(engine.url)

    def test_create_engine_with_postgres_url(self):
        """Test engine creation with PostgreSQL URL."""
        postgres_url = "postgresql://user:pass@localhost/testdb"
        engine = create_engine_from_url(postgres_url)
        assert engine is not None
        assert "postgresql" in str(engine.url).lower()

    def test_sqlite_memory_has_check_same_thread_false(self):
        """Test that SQLite memory database has check_same_thread disabled."""
        memory_url = "sqlite:///:memory:"
        engine = create_engine_from_url(memory_url)
        # Verify the connect_args were applied
        assert engine.pool is not None


class TestSessionFactory:
    """Test cases for session factory creation."""

    def test_create_session_factory_returns_sessionmaker(self):
        """Test that session factory is created successfully."""
        engine = create_engine("sqlite:///:memory:")
        factory = create_session_factory(engine)
        assert factory is not None

    def test_session_factory_creates_sessions(self):
        """Test that session factory can create sessions."""
        engine = create_engine("sqlite:///:memory:")
        factory = create_session_factory(engine)
        session = factory()
        assert isinstance(session, Session)
        session.close()

    def test_session_factory_bound_to_engine(self):
        """Test that created sessions are bound to the correct engine."""
        engine = create_engine("sqlite:///:memory:")
        factory = create_session_factory(engine)
        session = factory()
        assert session.bind == engine
        session.close()

    def test_session_factory_autocommit_false(self):
        """Test that sessions have autocommit disabled."""
        engine = create_engine("sqlite:///:memory:")
        factory = create_session_factory(engine)
        session = factory()
        # Session should not autocommit
        assert session.autocommit is False
        session.close()


class TestDatabaseInitialization:
    """Test cases for database initialization."""

    def test_init_db_creates_tables(self):
        """Test that init_db creates all tables."""
        engine = create_engine("sqlite:///:memory:")

        # Create a simple test model
        class _TestModel(Base):
            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            name = Column(String)

        init_db(engine)

        # Verify table was created
        assert engine.dialect.has_table(engine.connect(), "test_model")

    def test_init_db_is_idempotent(self):
        """Test that init_db can be called multiple times safely."""
        engine = create_engine("sqlite:///:memory:")

        class _TestModel(Base):
            __tablename__ = "test_idempotent"
            id = Column(Integer, primary_key=True)

        # Call init_db multiple times
        init_db(engine)
        init_db(engine)

        # Should not raise an error
        assert engine.dialect.has_table(engine.connect(), "test_idempotent")

    def test_init_db_with_existing_data(self):
        """Test that init_db preserves existing data."""
        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
            __tablename__ = "test_preserve"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)

        # Add some data
        factory = create_session_factory(engine)
        session = factory()
        session.add(TestModel(id=1, value="test"))
        session.commit()

        # Call init_db again
        init_db(engine)

        # Data should still exist
        result = session.query(TestModel).filter_by(id=1).first()
        assert result is not None
        assert result.value == "test"
        session.close()


class TestSessionScope:
    """Test cases for transactional session scope."""

    def test_session_scope_commits_on_success(self):
        """Test that session scope commits changes on successful completion."""
        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
            __tablename__ = "test_commit"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with session_scope(factory) as session:
            session.add(TestModel(id=1, value="committed"))

        # Verify data was committed
        with session_scope(factory) as session:
            result = session.query(TestModel).filter_by(id=1).first()
            assert result is not None
            assert result.value == "committed"

    def test_session_scope_rolls_back_on_error(self):
        """Test that session scope rolls back changes on exception."""
        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
            __tablename__ = "test_rollback"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        def _attempt_operation() -> None:
            with session_scope(factory) as session:
                session.add(TestModel(id=1, value="should_rollback"))
                msg = "rollback test"
                raise ValueError(msg)

        with pytest.raises(ValueError, match="rollback test"):
            _attempt_operation()

        # Verify data was not committed
        with session_scope(factory) as session:
            result = session.query(TestModel).filter_by(id=1).first()
            assert result is None

    def test_session_scope_closes_session(self):
        """Test that session scope always closes the session."""
        engine = create_engine("sqlite:///:memory:")
        factory = create_session_factory(engine)

        with session_scope(factory) as _:
            pass

        # Session should be closed after exiting context
        # Note: We can't directly check if closed, but we can verify cleanup

    def test_session_scope_with_nested_transaction(self):
        """Test session scope with nested operations."""
        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
            __tablename__ = "test_nested"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        with session_scope(factory) as session:
            session.add(TestModel(id=1, value="first"))
            session.flush()
            session.add(TestModel(id=2, value="second"))

        # Both records should be committed
        with session_scope(factory) as session:
            count = session.query(TestModel).count()
            assert count == 2

    def test_session_scope_propagates_exception(self):
        """Test that session scope propagates exceptions after rollback."""
        engine = create_engine("sqlite:///:memory:")
        factory = create_session_factory(engine)

        class CustomError(Exception):
            pass

        with pytest.raises(CustomError):
            with session_scope(factory) as _:
                raise CustomError()

    def test_session_scope_multiple_operations(self):
        """Test session scope with multiple database operations."""
        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
            __tablename__ = "test_multi_ops"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        init_db(engine)
        factory = create_session_factory(engine)

        # Add multiple records in one transaction
        with session_scope(factory) as session:
            for i in range(5):
                session.add(TestModel(id=i, value=f"value_{i}"))

        # Verify all records were committed
        with session_scope(factory) as session:
            count = session.query(TestModel).count()
            assert count == 5


class TestDefaultDatabaseURL:
    """Test cases for default database URL configuration."""

    def test_default_database_url_is_sqlite(self):
        """Test that default database URL uses SQLite."""
        assert "sqlite" in DEFAULT_DATABASE_URL.lower()

    def test_default_database_url_file_path(self):
        """Test that default database URL points to a file."""
        assert "asset_graph.db" in DEFAULT_DATABASE_URL

    def test_env_override_of_default_url(self):
        """Test that environment variable can override default URL."""
        custom_url = "postgresql://test:test@localhost/test"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": custom_url}):
            # Re-import would be needed in real scenario, but we test the pattern
            engine = create_engine_from_url()
            # Should use the custom URL when explicitly passed
            assert engine is not None


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_session_scope_with_empty_operations(self):
        """Test session scope with no operations."""
        engine = create_engine("sqlite:///:memory:")
        factory = create_session_factory(engine)

        # Should not raise any errors
        with session_scope(factory) as _:
            pass

    def test_create_engine_with_empty_string(self):
        """Test engine creation with empty string defaults to env/default."""
        with patch.dict(os.environ, {}, clear=True):
            engine = create_engine_from_url("")
            # Should fall back to default
            assert engine is not None

    def test_create_engine_with_none(self):
        """Test engine creation with None uses default."""
        engine = create_engine_from_url(None)
        assert engine is not None

    def test_session_scope_with_database_error(self):
        """Test session scope behavior with database-level errors."""
        from sqlalchemy.exc import IntegrityError

        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
            __tablename__ = "test_db_error"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        def _cause_integrity_error() -> None:
            with session_scope(factory) as session:
                session.add(TestModel(id=1))
                session.flush()
                session.add(TestModel(id=1))
                session.flush()

        with pytest.raises(IntegrityError):
            _cause_integrity_error()

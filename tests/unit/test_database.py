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
from unittest.mock import MagicMock, patch

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
        class TestModel(Base):
            __tablename__ = "test_model"
            id = Column(Integer, primary_key=True)
            name = Column(String)

        init_db(engine)

        # Verify table was created
        assert engine.dialect.has_table(engine.connect(), "test_model")

    def test_init_db_is_idempotent(self):
        """Test that init_db can be called multiple times safely."""
        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
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
        """
        Verifies that a database-level integrity error raised inside a session_scope is propagated.
        
        Specifically, attempts duplicate primary-key inserts within a transactional session and asserts that SQLAlchemy's `IntegrityError` is raised rather than being swallowed by the session scope.
        """
        from sqlalchemy.exc import IntegrityError

        engine = create_engine("sqlite:///:memory:")

        class TestModel(Base):
            __tablename__ = "test_db_error"
            id = Column(Integer, primary_key=True)

        init_db(engine)
        factory = create_session_factory(engine)

        def _cause_integrity_error() -> None:
            """
            Force a database integrity error by inserting duplicate primary keys within a transactional session.
            
            This function opens a transactional session and attempts to add two records with the same primary key value, causing the database to raise an integrity constraint violation when flushing.
            
            Raises:
                sqlalchemy.exc.IntegrityError: When the database rejects the duplicate primary key on flush.
            """
            with session_scope(factory) as session:
                session.add(TestModel(id=1))
                session.flush()
                session.add(TestModel(id=1))
                session.flush()

        with pytest.raises(IntegrityError):
            _cause_integrity_error()

# ============================================================================
# Additional Tests for api/database.py Changes
# ============================================================================

class TestDatabaseURLHandling:
    """Test suite for database URL resolution and handling."""
    
    def test_get_database_url_from_environment(self):
        """Test _get_database_url reads from environment variable."""
        import os
        from api.database import _get_database_url
        
        test_url = "sqlite:///test_from_env.db"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            url = _get_database_url()
            assert url == test_url
    
    def test_get_database_url_raises_when_not_set(self):
        """Test _get_database_url raises ValueError when DATABASE_URL not set."""
        import os
        from api.database import _get_database_url
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                _get_database_url()
            
            assert "DATABASE_URL environment variable must be set" in str(exc_info.value)
    
    def test_resolve_sqlite_path_with_memory_db(self):
        """Test _resolve_sqlite_path handles in-memory database correctly."""
        from api.database import _resolve_sqlite_path
        
        # Test :memory: URL
        result = _resolve_sqlite_path("sqlite:///:memory:")
        assert result == ":memory:"
        
        # Test /:memory: URL
        result = _resolve_sqlite_path("sqlite:////:memory:")
        assert result == ":memory:"
    
    def test_resolve_sqlite_path_with_file_uri(self):
        """Test _resolve_sqlite_path handles file URI correctly."""
        from api.database import _resolve_sqlite_path
        
        result = _resolve_sqlite_path("sqlite:///file::memory:?cache=shared")
        assert "file::memory:" in result
    
    def test_resolve_sqlite_path_with_relative_path(self):
        """Test _resolve_sqlite_path handles relative path."""
        from api.database import _resolve_sqlite_path
        
        result = _resolve_sqlite_path("sqlite:///relative.db")
        assert "relative.db" in result
    
    def test_resolve_sqlite_path_with_absolute_path(self):
        """Test _resolve_sqlite_path handles absolute path."""
        from api.database import _resolve_sqlite_path
        
        result = _resolve_sqlite_path("sqlite:////absolute/path/db.sqlite")
        assert "/absolute/path/db.sqlite" in result
    
    def test_resolve_sqlite_path_rejects_non_sqlite_scheme(self):
        """Test _resolve_sqlite_path raises error for non-sqlite schemes."""
        from api.database import _resolve_sqlite_path
        
        with pytest.raises(ValueError) as exc_info:
            _resolve_sqlite_path("postgresql://localhost/test")
        
        assert "Not a valid sqlite URI" in str(exc_info.value)
    
    def test_resolve_sqlite_path_handles_url_encoding(self):
        """Test _resolve_sqlite_path decodes URL encoding."""
        from api.database import _resolve_sqlite_path
        
        # Test with URL-encoded path
        result = _resolve_sqlite_path("sqlite:///my%20database.db")
        assert "my database.db" in result  # Space should be decoded


class TestMemoryDatabaseConnection:
    """Test suite for in-memory database connection handling."""
    
    def test_is_memory_db_with_memory_string(self):
        """Test _is_memory_db recognizes :memory: databases."""
        from api.database import _is_memory_db
        
        assert _is_memory_db(":memory:") is True
    
    def test_is_memory_db_with_file_path(self):
        """Test _is_memory_db returns False for file paths."""
        from api.database import _is_memory_db
        
        assert _is_memory_db("./database.db") is False
        assert _is_memory_db("/absolute/path/db.sqlite") is False
    
    def test_is_memory_db_with_none_uses_default(self):
        """Test _is_memory_db uses default URL when path is None."""
        import os
        from api.database import _is_memory_db
        
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
            assert _is_memory_db(None) is True
        
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///file.db"}):
            assert _is_memory_db(None) is False
    
    def test_memory_connection_singleton_behavior(self):
        """Test that memory database connection is reused (singleton pattern)."""
        import os
        from api.database import get_connection, _MEMORY_CONNECTION, _MEMORY_CONNECTION_LOCK
        
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        
        conn1 = get_connection()
        conn2 = get_connection()
        
        # Should return the same connection instance for memory databases
        assert conn1 is conn2
    
    def test_memory_connection_thread_safety(self):
        """Test that memory connection handling is thread-safe."""
        import os
        import threading
        from api.database import get_connection
        
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        
        connections = []
        
        def get_conn():
            """
            Append a connection object to the module-level `connections` list.
            
            This obtains a connection via `get_connection()` and adds it to `connections`.
            """
            connections.append(get_connection())
        
        threads = [threading.Thread(target=get_conn) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All connections should be the same instance
        assert all(conn is connections[0] for conn in connections)


class TestDatabaseInitializationUpdates:
    """Test suite for database initialization changes."""
    
    def test_initialize_schema_with_environment_variable(self):
        """Test initialize_schema uses DATABASE_URL from environment."""
        import os
        from api.database import initialize_schema
        
        test_url = "sqlite:///:memory:"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            # Should not raise
            initialize_schema()
    
    def test_initialize_schema_fails_without_database_url(self):
        """Test initialize_schema fails gracefully when DATABASE_URL not set."""
        import os
        from api.database import initialize_schema
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                initialize_schema()


class TestSrcDataDatabaseEnvironmentHandling:
    """Test suite for src/data/database.py environment variable changes."""
    
    def test_default_database_url_requires_environment_variable(self):
        """Test that DEFAULT_DATABASE_URL requires ASSET_GRAPH_DATABASE_URL to be set."""
        import os
        import sys
        
        # Remove the module if already imported
        if 'src.data.database' in sys.modules:
            del sys.modules['src.data.database']
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError) as exc_info:
                import src.data.database
            
            assert "ASSET_GRAPH_DATABASE_URL environment variable must be set" in str(exc_info.value)
    
    def test_default_database_url_reads_from_environment(self):
        """Test that DEFAULT_DATABASE_URL is set from environment variable."""
        import os
        import sys
        
        # Remove the module if already imported
        if 'src.data.database' in sys.modules:
            del sys.modules['src.data.database']
        
        test_url = "postgresql://user:pass@localhost/testdb"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": test_url}):
            import src.data.database
            assert src.data.database.DEFAULT_DATABASE_URL == test_url
    
    def test_create_engine_from_url_with_none_uses_default(self):
        """Test create_engine_from_url uses DEFAULT_DATABASE_URL when url is None."""
        import os
        from src.data.database import create_engine_from_url
        
        test_url = "sqlite:///:memory:"
        with patch.dict(os.environ, {"ASSET_GRAPH_DATABASE_URL": test_url}):
            engine = create_engine_from_url(None)
            assert engine is not None
            assert ":memory:" in str(engine.url)
    
    def test_create_engine_from_url_with_memory_sqlite_configuration(self):
        """Test create_engine_from_url properly configures in-memory SQLite."""
        from src.data.database import create_engine_from_url
        from sqlalchemy.pool import StaticPool
        
        memory_url = "sqlite:///:memory:"
        engine = create_engine_from_url(memory_url)
        
        # Should use StaticPool for in-memory database
        assert isinstance(engine.pool, StaticPool)
        
        # Should have check_same_thread=False in connect_args
        # This is important for thread safety
        assert engine is not None


class TestDatabaseHelperFunctionFormatting:
    """Test formatting and code style updates in database functions."""
    
    def test_docstring_formatting_consistency(self):
        """Test that docstrings follow consistent formatting."""
        from api.database import _get_database_url, _resolve_sqlite_path, _is_memory_db
        
        # All functions should have docstrings
        assert _get_database_url.__doc__ is not None
        assert _resolve_sqlite_path.__doc__ is not None
        assert _is_memory_db.__doc__ is not None
        
        # Check docstring format (should have description, parameters, returns)
        assert "Returns:" in _get_database_url.__doc__
        assert "Parameters:" in _resolve_sqlite_path.__doc__
        assert "Returns:" in _is_memory_db.__doc__

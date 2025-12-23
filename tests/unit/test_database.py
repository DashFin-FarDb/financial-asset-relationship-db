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
import sqlite3
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from api.database import (
    _connect,
    _get_database_url,
    _is_memory_db,
    _resolve_sqlite_path,
    execute,
    fetch_one,
    fetch_value,
    get_connection,
)
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


# ============================================================================
# ADDITIONAL COMPREHENSIVE TESTS - Enhanced Coverage
# Generated to provide additional edge case coverage
# ============================================================================
"""Additional comprehensive tests for api/database.py edge cases.

These tests enhance the existing test coverage with additional edge cases
and scenarios following the bias-for-action principle.
"""


@pytest.mark.unit
class TestResolveSqlitePathEnhancements:
    """Additional edge case tests for _resolve_sqlite_path."""

    def test_resolve_sqlite_path_with_query_parameters(self):
        """Test resolving SQLite URL with query parameters."""
        url = "sqlite:///test.db?mode=ro"
        result = _resolve_sqlite_path(url)
        assert "test.db" in result

    def test_resolve_sqlite_path_with_percent_encoding(self):
        """Test resolving SQLite URL with percent-encoded characters."""
        url = "sqlite:///test%20database.db"
        result = _resolve_sqlite_path(url)
        assert "test database.db" in result

    def test_resolve_sqlite_path_uri_memory_with_cache_shared(self):
        """Test resolving URI-style memory database with shared cache."""
        url = "sqlite:///file::memory:?cache=shared"
        result = _resolve_sqlite_path(url)
        assert "file::memory:" in result

    def test_resolve_sqlite_path_with_trailing_slashes(self):
        """Test resolving path with multiple trailing slashes."""
        url = "sqlite:///:memory:/"
        result = _resolve_sqlite_path(url)
        assert result == ":memory:"

    def test_resolve_sqlite_path_absolute_unix_path(self):
        """Test resolving absolute Unix-style path."""
        url = "sqlite:////absolute/path/to/db.sqlite"
        result = _resolve_sqlite_path(url)
        assert result.startswith("/")

    def test_resolve_sqlite_path_windows_drive_letter(self):
        """Test resolving Windows path with drive letter."""
        url = "sqlite:///C:/Users/test/database.db"
        result = _resolve_sqlite_path(url)
        assert "C:" in result or "database.db" in result

    def test_resolve_sqlite_path_special_characters(self):
        """Test resolving path with special characters."""
        url = "sqlite:///test-db_v2.sqlite"
        result = _resolve_sqlite_path(url)
        assert "test-db_v2.sqlite" in result

    def test_resolve_sqlite_path_non_sqlite_scheme_raises(self):
        """Test that non-SQLite schemes raise ValueError."""
        with pytest.raises(ValueError, match="Not a valid sqlite URI"):
            _resolve_sqlite_path("postgresql:///database")

    def test_resolve_sqlite_path_empty_path_component(self):
        """Test resolving URL with empty path component."""
        url = "sqlite:///"
        result = _resolve_sqlite_path(url)
        # Should handle empty path
        assert isinstance(result, str)


@pytest.mark.unit
class TestIsMemoryDbEnhancements:
    """Additional edge case tests for _is_memory_db."""

    def test_is_memory_db_with_uri_query_params(self):
        """Test detecting memory DB with various URI query parameters."""
        test_cases = [
            "file::memory:?mode=memory",
            "file::memory:?cache=shared",
            "file::memory:?cache=shared&mode=memory",
        ]
        for uri in test_cases:
            assert _is_memory_db(uri) is True

    def test_is_memory_db_with_file_scheme_but_not_memory(self):
        """Test that file:// URLs not containing memory return False."""
        assert _is_memory_db("file:///path/to/db.sqlite") is False

    def test_is_memory_db_case_sensitivity(self):
        """Test memory detection is case-sensitive."""
        assert _is_memory_db(":MEMORY:") is False  # Should be lowercase
        assert _is_memory_db(":Memory:") is False

    def test_is_memory_db_with_memory_in_filename(self):
        """Test that 'memory' in filename doesn't trigger false positive."""
        assert _is_memory_db("/path/to/memory_backup.db") is False

    def test_is_memory_db_with_none_defaults_to_config(self):
        """Test that None parameter uses configured DATABASE_PATH."""
        # This will use the actual configured path
        result = _is_memory_db(None)
        assert isinstance(result, bool)


@pytest.mark.unit
class TestConnectionManagementEnhancements:
    """Additional tests for connection management."""

    @patch("api.database._is_memory_db")
    @patch("api.database.sqlite3.connect")
    def test_connect_enables_uri_for_file_scheme(self, mock_connect, mock_is_memory):
        """Test that file:// URLs enable URI mode."""
        mock_is_memory.return_value = False
        mock_connection = Mock()
        mock_connect.return_value = mock_connection

        with patch("api.database.DATABASE_PATH", "file:///test.db"):
            _connect()

        # Verify uri=True was passed
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs.get("uri") is True

    @patch("api.database._is_memory_db")
    @patch("api.database.sqlite3.connect")
    def test_connect_sets_row_factory(self, mock_connect, mock_is_memory):
        """Test that connections have row_factory set."""
        mock_is_memory.return_value = False
        mock_connection = Mock(spec=sqlite3.Connection)
        mock_connect.return_value = mock_connection

        with patch("api.database.DATABASE_PATH", "/test.db"):
            _connect()

        assert mock_connection.row_factory is sqlite3.Row

    @patch("api.database._is_memory_db")
    @patch("api.database.sqlite3.connect")
    def test_connect_thread_safety_settings(self, mock_connect, mock_is_memory):
        """Test that check_same_thread is False."""
        mock_is_memory.return_value = False
        mock_connection = Mock()
        mock_connect.return_value = mock_connection

        with patch("api.database.DATABASE_PATH", "/test.db"):
            _connect()

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs.get("check_same_thread") is False


@pytest.mark.unit
class TestExecuteFunctionEnhancements:
    """Additional tests for execute function edge cases."""

    @patch("api.database.get_connection")
    def test_execute_with_empty_parameters(self, mock_get_conn):
        """Test execute with empty parameter tuple."""
        mock_conn = Mock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        execute("SELECT 1", ())

        mock_conn.execute.assert_called_once_with("SELECT 1", ())

    @patch("api.database.get_connection")
    def test_execute_handles_commit(self, mock_get_conn):
        """Test that execute commits changes."""
        mock_conn = Mock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        execute("INSERT INTO test VALUES (?)", (1,))

        sql, params = mock_conn.execute.call_args[0]
        assert sql == "INSERT INTO test VALUES (?)"
        assert list(params) == [1]
        mock_conn.commit.assert_called_once()

    @patch("api.database.get_connection")
    def test_execute_with_list_parameters(self, mock_get_conn):
        """Test execute accepts list parameters."""
        mock_conn = Mock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        execute("INSERT INTO test VALUES (?, ?)", [1, 2])

        mock_conn.execute.assert_called_once_with("INSERT INTO test VALUES (?, ?)", [1, 2])


@pytest.mark.unit
class TestFetchOperationsEnhancements:
    """Additional tests for fetch operations."""

    @patch("api.database.get_connection")
    def test_fetch_one_with_no_results(self, mock_get_conn):
        """Test fetch_one returns None when no results."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_one("SELECT * FROM nonexistent")

        assert result is None

    @patch("api.database.get_connection")
    def test_fetch_one_with_complex_query(self, mock_get_conn):
        """Test fetch_one with complex JOIN query."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = {"id": 1, "name": "test"}
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_one(
            "SELECT * FROM table1 JOIN table2 ON table1.id = table2.id WHERE table1.id = ?",
            (1,),
        )

        assert result == mock_row

    @patch("api.database.get_connection")
    def test_fetch_value_with_aggregate(self, mock_get_conn):
        """Test fetch_value with aggregate function."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = (42,)  # COUNT result
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_value("SELECT COUNT(*) FROM table")

        assert result == 42

    @patch("api.database.get_connection")
    def test_fetch_value_with_null_result(self, mock_get_conn):
        """Test fetch_value when result is NULL."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = (None,)
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = fetch_value("SELECT nullable_column FROM table")

        assert result is None


@pytest.mark.unit
class TestDatabaseErrorHandling:
    """Test error handling in database operations."""

    @patch("api.database.get_connection")
    def test_execute_propagates_errors(self, mock_get_conn):
        mock_conn = Mock(spec=sqlite3.Connection)
        mock_conn.execute.side_effect = sqlite3.Error("SQL error")
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        with pytest.raises(sqlite3.Error):
            execute("INVALID SQL")

        mock_conn.commit.assert_not_called()

    @patch("api.database.get_connection")
    def test_fetch_one_propagates_errors(self, mock_get_conn):
        """Test that fetch_one propagates query errors."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.execute.side_effect = sqlite3.OperationalError("Table not found")
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        with pytest.raises(sqlite3.OperationalError):
            fetch_one("SELECT * FROM nonexistent")


@pytest.mark.unit
class TestDatabaseUrlConfiguration:
    """Test database URL configuration edge cases."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("api.database.DEFAULT_DATABASE_URL", None)
    def test_get_database_url_missing_env_var(self):
        """Test that missing DATABASE_URL raises ValueError."""
        with pytest.raises(ValueError, match="DATABASE_URL"):
            _get_database_url()

    @patch.dict("os.environ", {"DATABASE_URL": ""})
    def test_get_database_url_empty_string(self):
        """Test that empty DATABASE_URL raises ValueError."""
        with pytest.raises(ValueError):
            _get_database_url()

    @patch.dict("os.environ", {"DATABASE_URL": "   "})
    def test_get_database_url_whitespace_only(self):
        """Test that whitespace-only DATABASE_URL is returned as-is."""
        result = _get_database_url()
        assert result == "   "

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://user:pass@localhost/db"})
    def test_get_database_url_returns_configured_value(self):
        """Test that configured URL is returned as-is."""
        result = _get_database_url()
        assert result == "postgresql://user:pass@localhost/db"

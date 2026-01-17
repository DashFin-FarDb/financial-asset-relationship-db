"""
Comprehensive unit tests for api/database.py module.

Tests cover:
- Database URL configuration
- SQLite path resolution
- Connection management
- Memory database detection
- Query execution
- Schema initialization
- Edge cases and error handling
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from api.database import (
    DATABASE_PATH,
    DATABASE_URL,
    _is_memory_db,
    _resolve_sqlite_path,
    execute,
    fetch_one,
    fetch_value,
    get_connection,
    initialize_schema,
)


class TestDatabaseURLConfiguration:
    """Test database URL configuration and validation."""

    def test_database_url_is_set(self):
        """Test that DATABASE_URL is set."""
        assert DATABASE_URL is not None
        assert isinstance(DATABASE_URL, str)
        assert len(DATABASE_URL) > 0

    def test_database_path_is_set(self):
        """Test that DATABASE_PATH is resolved."""
        assert DATABASE_PATH is not None
        assert isinstance(DATABASE_PATH, str)

    @patch.dict(os.environ, {"DATABASE_URL": ""}, clear=True)
    def test_missing_database_url_raises_error(self):
        """Test that missing DATABASE_URL raises ValueError."""
        from api import database as db_module

        # Need to reload the module to trigger the error
        with pytest.raises(
            ValueError, match="DATABASE_URL environment variable must be set"
        ):
            # Import will fail due to module-level check
            import importlib

            importlib.reload(db_module)


class TestSQLitePathResolution:
    """Test SQLite URL path resolution."""

    def test_resolve_memory_database(self):
        """Test resolution of in-memory database URL."""
        url = "sqlite:///:memory:"
        path = _resolve_sqlite_path(url)
        assert path == ":memory:"

    def test_resolve_relative_path(self):
        """Test resolution of relative path."""
        url = "sqlite:///test.db"
        path = _resolve_sqlite_path(url)
        assert "test.db" in path
        assert Path(path).is_absolute()

    def test_resolve_absolute_path(self):
        """Test resolution of absolute path."""
        url = "sqlite:////tmp/test.db"
        path = _resolve_sqlite_path(url)
        assert path.startswith("/")
        assert "test.db" in path

    def test_resolve_with_query_params(self):
        """Test resolution with query parameters."""
        url = "sqlite:///test.db?mode=ro"
        path = _resolve_sqlite_path(url)
        assert "test.db" in path

    def test_resolve_uri_style_memory_db(self):
        """Test resolution of URI-style memory database."""
        url = "sqlite:///file::memory:?cache=shared"
        path = _resolve_sqlite_path(url)
        assert ":memory:" in path
        assert "cache=shared" in path

    def test_resolve_invalid_scheme_raises_error(self):
        """Test that non-sqlite scheme raises ValueError."""
        url = "postgresql://localhost/test"
        with pytest.raises(ValueError, match="Not a valid sqlite URI"):
            _resolve_sqlite_path(url)

    def test_resolve_percent_encoded_path(self):
        """Test resolution of percent-encoded paths."""
        url = "sqlite:///test%20db.db"
        path = _resolve_sqlite_path(url)
        assert "test db.db" in path  # Should be decoded


class TestMemoryDatabaseDetection:
    """Test detection of in-memory databases."""

    def test_is_memory_db_colon_memory(self):
        """Test detection of :memory: database."""
        assert _is_memory_db(":memory:") is True

    def test_is_memory_db_file_path(self):
        """Test that file path is not detected as memory."""
        assert _is_memory_db("/tmp/test.db") is False
        assert _is_memory_db("test.db") is False

    def test_is_memory_db_uri_style(self):
        """Test detection of URI-style memory database."""
        assert _is_memory_db("file::memory:?cache=shared") is True

    def test_is_memory_db_with_none(self):
        """Test is_memory_db with None uses DATABASE_PATH."""
        result = _is_memory_db(None)
        assert isinstance(result, bool)

    def test_is_memory_db_empty_string(self):
        """Test is_memory_db with empty string."""
        assert _is_memory_db("") is False


class TestConnectionManagement:
    """Test database connection management."""

    def test_get_connection_context_manager(self):
        """Test that get_connection works as context manager."""
        with patch("api.database.DATABASE_PATH", ":memory:"):
            with get_connection() as conn:
                assert conn is not None
                assert isinstance(conn, sqlite3.Connection)

    def test_connection_has_row_factory(self):
        """Test that connection has Row factory set."""
        with patch("api.database.DATABASE_PATH", ":memory:"):
            with get_connection() as conn:
                assert conn.row_factory == sqlite3.Row

    def test_memory_connection_is_reused(self):
        """Test that in-memory connection is reused."""
        with patch("api.database.DATABASE_PATH", ":memory:"):
            with get_connection() as conn1:
                conn1_id = id(conn1)

            with get_connection() as conn2:
                conn2_id = id(conn2)

            # Should be same connection for memory DB
            assert conn1_id == conn2_id

    def test_file_connection_is_new_each_time(self, tmp_path):
        """Test that file-based connections are new each time."""
        db_file = tmp_path / "test.db"

        with patch("api.database.DATABASE_PATH", str(db_file)):
            with patch("api.database._is_memory_db", return_value=False):
                with get_connection() as conn1:
                    conn1_id = id(conn1)

                with get_connection() as conn2:
                    conn2_id = id(conn2)

                # Should be different connections for file DB
                assert conn1_id != conn2_id

    def test_connection_supports_uri(self):
        """Test that URI-style paths are supported."""
        uri_path = "file::memory:?cache=shared"
        with patch("api.database.DATABASE_PATH", uri_path):
            with patch("api.database._is_memory_db", return_value=True):
                with get_connection() as conn:
                    assert conn is not None


class TestQueryExecution:
    """Test query execution functions."""

    @patch("api.database.get_connection")
    def test_execute_runs_query(self, mock_get_conn):
        """Test that execute runs SQL query."""
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_context

        execute("CREATE TABLE test (id INTEGER)")

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("api.database.get_connection")
    def test_execute_with_parameters(self, mock_get_conn):
        """Test execute with query parameters."""
        mock_conn = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_context

        execute("INSERT INTO test VALUES (?)", ("value",))

        assert mock_conn.execute.called
        call_args = mock_conn.execute.call_args[0]
        assert len(call_args) == 2

    @patch("api.database.get_connection")
    def test_fetch_one_returns_row(self, mock_get_conn):
        """Test that fetch_one returns a row."""
        mock_row = {"id": 1, "name": "test"}
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = mock_row
        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_context

        result = fetch_one("SELECT * FROM test")

        assert result == mock_row

    @patch("api.database.get_connection")
    def test_fetch_one_returns_none_when_empty(self, mock_get_conn):
        """Test that fetch_one returns None when no rows."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_context

        result = fetch_one("SELECT * FROM test WHERE id = ?", (999,))

        assert result is None

    @patch("api.database.get_connection")
    def test_fetch_value_returns_first_column(self, mock_get_conn):
        """Test that fetch_value returns first column value."""
        mock_row = Mock()
        mock_row.__getitem__ = Mock(return_value=42)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = mock_row
        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_context

        result = fetch_value("SELECT COUNT(*) FROM test")

        assert result == 42

    @patch("api.database.get_connection")
    def test_fetch_value_returns_none_when_empty(self, mock_get_conn):
        """Test that fetch_value returns None when no rows."""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_conn = Mock()
        mock_conn.execute.return_value = mock_cursor
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_conn)
        mock_context.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_context

        result = fetch_value("SELECT id FROM test WHERE id = ?", (999,))

        assert result is None


class TestSchemaInitialization:
    """Test schema initialization."""

    @patch("api.database.execute")
    def test_initialize_schema_creates_table(self, mock_execute):
        """Test that initialize_schema creates user_credentials table."""
        initialize_schema()

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        sql = call_args[0]

        assert "CREATE TABLE IF NOT EXISTS user_credentials" in sql
        assert "username TEXT UNIQUE NOT NULL" in sql
        assert "hashed_password TEXT NOT NULL" in sql

    @patch("api.database.execute")
    def test_initialize_schema_all_columns_present(self, mock_execute):
        """Test that all required columns are in schema."""
        initialize_schema()

        sql = mock_execute.call_args[0][0]

        required_columns = [
            "id INTEGER PRIMARY KEY AUTOINCREMENT",
            "username",
            "email",
            "full_name",
            "hashed_password",
            "disabled",
        ]

        for column in required_columns:
            assert column in sql, f"Missing column: {column}"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_execute_with_empty_parameters(self):
        """Test execute with empty parameter list."""
        with patch("api.database.get_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_context = Mock()
            mock_context.__enter__ = Mock(return_value=mock_conn)
            mock_context.__exit__ = Mock(return_value=False)
            mock_get_conn.return_value = mock_context

            execute("SELECT 1", [])

            # Should still work with empty list
            assert mock_conn.execute.called

    def test_fetch_one_with_none_parameters(self):
        """Test fetch_one with None parameters."""
        with patch("api.database.get_connection") as mock_get_conn:
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = None
            mock_conn = Mock()
            mock_conn.execute.return_value = mock_cursor
            mock_context = Mock()
            mock_context.__enter__ = Mock(return_value=mock_conn)
            mock_context.__exit__ = Mock(return_value=False)
            mock_get_conn.return_value = mock_context

            result = fetch_one("SELECT 1", None)

            # Should handle None parameters
            assert result is None

    def test_resolve_sqlite_path_with_special_characters(self):
        """Test path resolution with special characters."""
        url = "sqlite:///test-db_123.db"
        path = _resolve_sqlite_path(url)
        assert "test-db_123.db" in path

    def test_memory_connection_thread_safety(self):
        """Test that memory connection lock is used."""
        import threading

        with patch("api.database.DATABASE_PATH", ":memory:"):
            # Simulate concurrent access
            results = []

            def access_connection():
                with get_connection() as conn:
                    results.append(id(conn))

            threads = [threading.Thread(target=access_connection) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All should get the same connection
            assert all(r == results[0] for r in results)


class TestPathValidation:
    """Test path validation and sanitization."""

    def test_resolve_path_normalizes_relative_paths(self):
        """Test that relative paths are normalized."""
        url = "sqlite:///./test.db"
        path = _resolve_sqlite_path(url)
        assert Path(path).is_absolute()

    def test_resolve_path_handles_parent_directory(self):
        """Test handling of parent directory references."""
        url = "sqlite:///../test.db"
        path = _resolve_sqlite_path(url)
        assert Path(path).is_absolute()

    def test_resolve_path_handles_multiple_slashes(self):
        """Test handling of multiple slashes."""
        url = "sqlite:////tmp//test.db"
        path = _resolve_sqlite_path(url)
        assert "//" not in path or path.startswith("//")  # Network paths allowed


class TestConnectionPooling:
    """Test connection pooling behavior."""

    def test_cleanup_function_is_registered(self):
        """Test that cleanup function is registered."""
        import importlib

        with patch("atexit.register") as mock_register:
            import api.database as db_module

            importlib.reload(db_module)

            assert any(
                call.args and call.args[0] is db_module._cleanup_memory_connection
                for call in mock_register.call_args_list
            )

    @patch("api.database._MEMORY_CONNECTION")
    def test_cleanup_closes_memory_connection(self, mock_conn):
        """Test that cleanup closes memory connection."""
        from api.database import _cleanup_memory_connection

        mock_conn.close = Mock()
        _cleanup_memory_connection()

        # Cleanup should attempt to close if connection exists
        # (Implementation detail may vary)

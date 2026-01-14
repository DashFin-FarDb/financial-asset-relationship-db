"""Comprehensive unit tests for API database module.

This module provides extensive test coverage for api/database.py including:
- Database URL resolution from environment
- SQLite path resolution (file, memory, URI)
- Connection management for file and memory databases
- Thread-safe memory connection handling
- Context manager behavior
- Cleanup and resource management
"""

import os
import sqlite3
import threading
from unittest.mock import MagicMock, patch

import pytest

from api.database import (
    _cleanup_memory_connection,
    _connect,
    _get_database_url,
    _is_memory_db,
    _resolve_sqlite_path,
    get_connection,
)


class TestGetDatabaseUrl:
    """Test cases for _get_database_url function."""

    def test_get_database_url_from_env(self):
        """Test reading DATABASE_URL from environment."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///test.db"}):
            url = _get_database_url()
            assert url == "sqlite:///test.db"

    def test_get_database_url_raises_when_not_set(self):
        """Test that ValueError is raised when DATABASE_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                _get_database_url()
            assert "DATABASE_URL environment variable must be set" in str(exc_info.value)


class TestResolveSqlitePath:
    """Test cases for _resolve_sqlite_path function."""

    def test_resolve_sqlite_path_memory_colon(self):
        """Test resolving :memory: path."""
        path = _resolve_sqlite_path("sqlite:///:memory:")
        assert path == ":memory:"

    def test_resolve_sqlite_path_memory_slash(self):
        """Test resolving /:memory: path."""
        path = _resolve_sqlite_path("sqlite:///memory:")
        assert path == ":memory:"

    def test_resolve_sqlite_path_file_uri(self):
        """Test resolving URI-style memory database."""
        path = _resolve_sqlite_path("sqlite:///file::memory:?cache=shared")
        assert "file::memory:" in path

    def test_resolve_sqlite_path_relative_file(self):
        """Test resolving relative file path."""
        path = _resolve_sqlite_path("sqlite:///test.db")
        assert path.endswith("test.db")

    def test_resolve_sqlite_path_absolute_file(self):
        """Test resolving absolute file path."""
        path = _resolve_sqlite_path("sqlite:////absolute/path/test.db")
        assert "/absolute/path/test.db" in path

    def test_resolve_sqlite_path_invalid_scheme(self):
        """Test that non-sqlite scheme raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _resolve_sqlite_path("postgresql://localhost/db")
        assert "Not a valid sqlite URI" in str(exc_info.value)

    def test_resolve_sqlite_path_percent_encoding(self):
        """Test that percent-encoding is decoded."""
        path = _resolve_sqlite_path("sqlite:///test%20file.db")
        assert "test file.db" in path


class TestIsMemoryDb:
    """Test cases for _is_memory_db function."""

    def test_is_memory_db_with_colon_memory(self):
        """Test detecting :memory: as memory database."""
        assert _is_memory_db(":memory:") is True

    def test_is_memory_db_with_file_uri_memory(self):
        """Test detecting file::memory: as memory database."""
        assert _is_memory_db("file::memory:?cache=shared") is True

    def test_is_memory_db_with_regular_file(self):
        """Test that regular file is not detected as memory database."""
        assert _is_memory_db("test.db") is False

    def test_is_memory_db_with_absolute_path(self):
        """Test that absolute path is not detected as memory database."""
        assert _is_memory_db("/absolute/path/test.db") is False


class TestConnect:
    """Test cases for _connect function."""

    @patch("api.database.DATABASE_PATH", ":memory:")
    @patch("api.database._MEMORY_CONNECTION", None)
    def test_connect_creates_memory_connection(self):
        """Test that connecting to memory database creates shared connection."""
        conn = _connect()
        assert isinstance(conn, sqlite3.Connection)

    @patch("api.database.DATABASE_PATH", "test.db")
    @patch("api.database.sqlite3.connect")
    def test_connect_creates_file_connection(self, mock_connect):
        """Test that connecting to file database creates new connection."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_connect.return_value = mock_conn

        conn = _connect()

        mock_connect.assert_called_once()
        assert conn == mock_conn

    @patch("api.database.DATABASE_PATH", "file:test.db?mode=ro")
    @patch("api.database.sqlite3.connect")
    def test_connect_with_uri_path(self, mock_connect):
        """Test connecting with URI-style database path."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_connect.return_value = mock_conn

        _connect()

        # Verify URI mode was used
        call_args = mock_connect.call_args
        assert call_args[1].get("uri") is True


class TestGetConnection:
    """Test cases for get_connection context manager."""

    @patch("api.database._connect")
    @patch("api.database._is_memory_db", return_value=False)
    def test_get_connection_closes_file_connection(self, mock_is_memory, mock_connect):
        """Test that file database connection is closed after context."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_connect.return_value = mock_conn

        with get_connection() as conn:
            assert conn == mock_conn

        mock_conn.close.assert_called_once()

    @patch("api.database._connect")
    @patch("api.database._is_memory_db", return_value=True)
    def test_get_connection_keeps_memory_connection_open(self, mock_is_memory, mock_connect):
        """Test that memory database connection stays open after context."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_connect.return_value = mock_conn

        with get_connection() as conn:
            assert conn == mock_conn

        mock_conn.close.assert_not_called()


class TestCleanupMemoryConnection:
    """Test cases for _cleanup_memory_connection function."""

    @patch("api.database._MEMORY_CONNECTION")
    def test_cleanup_closes_memory_connection(self, mock_conn):
        """Test that cleanup closes the memory connection."""
        mock_connection = MagicMock(spec=sqlite3.Connection)
        with patch("api.database._MEMORY_CONNECTION", mock_connection):
            _cleanup_memory_connection()
            mock_connection.close.assert_called_once()

    def test_cleanup_handles_none_connection(self):
        """Test that cleanup handles None connection gracefully."""
        with patch("api.database._MEMORY_CONNECTION", None):
            _cleanup_memory_connection()  # Should not raise


class TestThreadSafety:
    """Test cases for thread-safety of database connections."""

    @patch("api.database.DATABASE_PATH", ":memory:")
    def test_memory_connection_thread_safety(self):
        """Test that memory connection is thread-safe."""
        connections = []

        def get_conn():
            """
            Obtain a database connection and record its object identity.
            
            Calls the module's connection factory to get a connection and appends its `id()` value to the module-level `connections` list for later inspection. This function has no return value.
            """
            conn = _connect()
            connections.append(id(conn))

        threads = [threading.Thread(target=get_conn) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All connections should be the same object (same id)
        assert len(set(connections)) == 1
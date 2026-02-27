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
            assert "DATABASE_URL environment variable must be set" in str(
                exc_info.value
            )


class TestResolveSqlitePath:
    """Test cases for _resolve_sqlite_path function."""

    def test_resolve_sqlite_path_memory_colon(self):
        """Test resolving :memory: path."""
        path = _resolve_sqlite_path("sqlite:///:memory:")
        assert path == ":memory:"


    def test_resolve_sqlite_path_file_uri(self):
        """Test resolving a URI-style SQLite memory database path."""
        path = _resolve_sqlite_path("sqlite:///file::memory:?cache=shared")
        assert "file::memory:" in path

    def test_resolve_sqlite_path_relative_file(self):
        """Test resolving a relative SQLite file path."""
        path = _resolve_sqlite_path("sqlite:///test.db")
        assert path.endswith("test.db")

    def test_resolve_sqlite_path_absolute_file(self):
        """Test resolving an absolute SQLite file path."""
        path = _resolve_sqlite_path("sqlite:////absolute/path/test.db")
        assert "/absolute/path/test.db" in path

    def test_resolve_sqlite_path_invalid_scheme(self):
        """Test that a non-sqlite scheme raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _resolve_sqlite_path("postgresql://localhost/db")
        assert "Not a valid sqlite URI" in str(exc_info.value)

    def test_resolve_sqlite_path_percent_encoding(self):
        """Test percent-encoding decoding in SQLite path."""
        path = _resolve_sqlite_path("sqlite:///test%20file.db")
        assert "test file.db" in path


class TestIsMemoryDb:
    """Test cases for _is_memory_db function."""

    def test_is_memory_db_with_colon_memory(self):
        """Test if ':memory:' is recognized as a memory database."""
        assert _is_memory_db(":memory:") is True

    def test_is_memory_db_with_file_uri_memory(self):
        """Test if 'file::memory:' is recognized as a memory database."""
        assert _is_memory_db("file::memory:?cache=shared") is True

    def test_is_memory_db_with_regular_file(self):
        """Test that a regular file is not detected as a memory database."""
        assert _is_memory_db("test.db") is False

    def test_is_memory_db_with_absolute_path(self):
        """Test that absolute path is not detected as memory database."""
        assert _is_memory_db("/absolute/path/test.db") is False


class TestConnect:
    """Test cases for _connect function."""

    def test_connect_creates_memory_connection(self):
        """Test that connecting to a memory database returns a sqlite3.Connection."""
        import api.database
        from api.database import _DatabaseConnectionManager

        temp_manager = _DatabaseConnectionManager(":memory:")
        with patch.object(api.database, "_db_manager", temp_manager):
            try:
                conn = _connect()
                assert isinstance(conn, sqlite3.Connection)
            finally:
                if temp_manager._memory_connection is not None:
                    temp_manager._memory_connection.close()
                    temp_manager._memory_connection = None

    def test_connect_creates_file_connection(self):
        """Test that connecting to the file database uses the db manager."""
        import api.database

        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_manager = MagicMock()
        mock_manager.connect.return_value = mock_conn

        with patch.object(api.database, "_db_manager", mock_manager):
            conn = _connect()

        mock_manager.connect.assert_called_once()
        assert conn == mock_conn

    def test_connect_with_uri_path(self):
        """Test connecting with a URI-style database path."""
        import api.database
        from api.database import _DatabaseConnectionManager

        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_conn.row_factory = None

        with patch("api.database.sqlite3.connect", return_value=mock_conn) as mock_sqlite_connect:
            temp_manager = _DatabaseConnectionManager("file:test.db?mode=ro")
            with patch.object(api.database, "_db_manager", temp_manager):
                _connect()

        call_kwargs = mock_sqlite_connect.call_args[1]
        assert call_kwargs.get("uri") is True


class TestGetConnection:
    """Test cases for get_connection context manager."""

    @patch("api.database._connect")
    @patch("api.database._is_memory_db", return_value=False)
    def test_get_connection_closes_file_connection(self, mock_is_memory, mock_connect):
        """Test that the file database connection is closed after use."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_connect.return_value = mock_conn

        with get_connection() as conn:
            assert conn == mock_conn

        mock_conn.close.assert_called_once()

    @patch("api.database._connect")
    @patch("api.database._is_memory_db", return_value=True)
    def test_get_connection_keeps_memory_connection_open(
        self, mock_is_memory, mock_connect
    ):
        """Test that the memory database connection remains open."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_connect.return_value = mock_conn

        with get_connection() as conn:
            assert conn == mock_conn

        mock_conn.close.assert_not_called()



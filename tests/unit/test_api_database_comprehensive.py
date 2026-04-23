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
from src.config.settings import get_settings


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
            assert "DATABASE_URL" in str(exc_info.value)


class TestResolveSqlitePath:
    """Test cases for _resolve_sqlite_path function."""

    def test_resolve_sqlite_path_memory_colon(self):
        """Test resolving :memory: path."""
        path = _resolve_sqlite_path("sqlite:///:memory:")
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

    def test_connect_creates_memory_connection(self):
        """Test that connecting to memory database returns a sqlite3.Connection."""
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
        """Test that connecting to file database delegates to the db manager."""
        import api.database

        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_manager = MagicMock()
        mock_manager.connect.return_value = mock_conn

        with patch.object(api.database, "_db_manager", mock_manager):
            conn = _connect()

        mock_manager.connect.assert_called_once()
        assert conn == mock_conn

    def test_connect_resolves_uri_path_via_settings(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "sqlite:///file:test.db?mode=ro"},
            clear=False,
        ):
            get_settings.cache_clear()
            with patch("api.database.sqlite3.connect") as mock_connect:
                mock_connection = MagicMock()
                mock_connect.return_value = mock_connection

                connection = database._connect()

            assert connection is mock_connection
            mock_connect.assert_called_once()
            assert mock_connect.call_args.kwargs["uri"] is True


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


class TestDatabaseConnectionManagerLegacyRemoval:
    """Tests verifying that LEGACY_CONNECTION was removed from _DatabaseConnectionManager."""

    def test_legacy_connection_class_attribute_does_not_exist(self):
        """LEGACY_CONNECTION class attribute must not exist on the manager after the PR change."""
        from api.database import _DatabaseConnectionManager

        assert not hasattr(
            _DatabaseConnectionManager, "LEGACY_CONNECTION"
        ), "LEGACY_CONNECTION class attribute should have been removed"

    def test_file_connection_does_not_set_legacy_connection(self, tmp_path):
        """Connecting to a file-backed database must not set any LEGACY_CONNECTION attribute."""
        from api.database import _DatabaseConnectionManager

        db_path = str(tmp_path / "test_legacy.db")
        manager = _DatabaseConnectionManager(db_path)
        conn = manager.connect()
        try:
            assert not hasattr(
                _DatabaseConnectionManager, "LEGACY_CONNECTION"
            ), "File connect() must not create LEGACY_CONNECTION"
            assert not hasattr(
                manager, "LEGACY_CONNECTION"
            ), "File connect() must not set LEGACY_CONNECTION on instance"
        finally:
            conn.close()


class TestConnectModuleLevelCaching:
    """Tests for the module-level _MEMORY_CONNECTION caching in _connect()."""

    def test_connect_caches_memory_connection_in_module_global(self):
        """_connect() must store the connection in the module-level _MEMORY_CONNECTION for in-memory DBs."""
        import api.database

        temp_manager = api.database._DatabaseConnectionManager(":memory:")
        saved_module_conn = api.database._MEMORY_CONNECTION
        saved_module_conn_manager = api.database._MEMORY_CONNECTION_MANAGER
        api.database._MEMORY_CONNECTION = None
        api.database._MEMORY_CONNECTION_MANAGER = None
        try:
            with patch.object(api.database, "_db_manager", temp_manager):
                with patch.object(api.database, "_is_memory_db", return_value=True):
                    conn = api.database._connect()
                    assert (
                        api.database._MEMORY_CONNECTION is conn
                    ), "_MEMORY_CONNECTION global must be set to the returned connection"
        finally:
            api.database._MEMORY_CONNECTION = saved_module_conn
            api.database._MEMORY_CONNECTION_MANAGER = saved_module_conn_manager
            if temp_manager._memory_connection is not None:
                temp_manager._memory_connection.close()
                temp_manager._memory_connection = None

    def test_connect_returns_same_memory_connection_on_repeated_calls(self):
        """Second call to _connect() for in-memory DB must return the cached connection."""
        import api.database

        temp_manager = api.database._DatabaseConnectionManager(":memory:")
        saved_module_conn = api.database._MEMORY_CONNECTION
        saved_module_conn_manager = api.database._MEMORY_CONNECTION_MANAGER
        api.database._MEMORY_CONNECTION = None
        api.database._MEMORY_CONNECTION_MANAGER = None
        try:
            with patch.object(api.database, "DATABASE_PATH", ":memory:"):
                with patch.object(api.database, "_db_manager", temp_manager):
                    conn1 = api.database._connect()
                    conn2 = api.database._connect()
                    assert conn1 is conn2, "Repeated _connect() calls must return the same cached connection"
        finally:
            api.database._MEMORY_CONNECTION = saved_module_conn
            api.database._MEMORY_CONNECTION_MANAGER = saved_module_conn_manager
            if temp_manager._memory_connection is not None:
                temp_manager._memory_connection.close()
                temp_manager._memory_connection = None

    def test_connect_does_not_cache_file_connection(self):
        """_connect() must not touch _MEMORY_CONNECTION when the DB is file-backed."""
        import api.database

        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_manager = MagicMock()
        mock_manager.connect.return_value = mock_conn

        saved_module_conn = api.database._MEMORY_CONNECTION
        saved_module_conn_manager = api.database._MEMORY_CONNECTION_MANAGER
        api.database._MEMORY_CONNECTION = None
        api.database._MEMORY_CONNECTION_MANAGER = None
        try:
            with patch.object(api.database, "_db_manager", mock_manager):
                with patch.object(api.database, "_is_memory_db", return_value=False):
                    api.database._connect()
                    assert (
                        api.database._MEMORY_CONNECTION is None
                    ), "_MEMORY_CONNECTION must remain None for file-backed databases"
        finally:
            api.database._MEMORY_CONNECTION = saved_module_conn
            api.database._MEMORY_CONNECTION_MANAGER = saved_module_conn_manager


class TestCleanupMemoryConnection:
    """Tests for the refactored _cleanup_memory_connection() function."""

    def test_cleanup_clears_module_level_memory_connection(self):
        """_cleanup_memory_connection() must set module-level _MEMORY_CONNECTION to None."""
        import api.database

        mock_conn = MagicMock(spec=sqlite3.Connection)
        saved = api.database._MEMORY_CONNECTION
        api.database._MEMORY_CONNECTION = mock_conn
        try:
            with patch.object(api.database._db_manager, "close_shared_connection"):
                api.database._cleanup_memory_connection()
            assert api.database._MEMORY_CONNECTION is None
        finally:
            api.database._MEMORY_CONNECTION = saved

    def test_cleanup_closes_module_connection_when_distinct_from_manager(self):
        """When module and manager hold different connections, the module one must be closed."""
        import api.database

        module_conn = MagicMock(spec=sqlite3.Connection)
        manager_conn = MagicMock(spec=sqlite3.Connection)

        saved = api.database._MEMORY_CONNECTION
        api.database._MEMORY_CONNECTION = module_conn
        try:
            with patch.object(api.database._db_manager, "_memory_connection", manager_conn, create=True):
                with patch.object(api.database._db_manager, "close_shared_connection"):
                    api.database._cleanup_memory_connection()
            module_conn.close.assert_called_once()
        finally:
            api.database._MEMORY_CONNECTION = saved

    def test_cleanup_does_not_double_close_when_connections_are_same(self):
        """When module-level and manager connections are identical, only one close must occur."""
        import api.database

        shared_conn = MagicMock(spec=sqlite3.Connection)

        saved = api.database._MEMORY_CONNECTION
        api.database._MEMORY_CONNECTION = shared_conn
        try:
            # Patch _memory_connection on the real _db_manager instance
            original_mc = api.database._db_manager._memory_connection
            api.database._db_manager._memory_connection = shared_conn
            try:
                with patch.object(api.database._db_manager, "close_shared_connection"):
                    api.database._cleanup_memory_connection()
                # The module-level branch skips close because they are the same object
                shared_conn.close.assert_not_called()
            finally:
                api.database._db_manager._memory_connection = original_mc
        finally:
            api.database._MEMORY_CONNECTION = saved

    def test_cleanup_is_idempotent(self):
        """Calling _cleanup_memory_connection() multiple times must not raise."""
        import api.database

        saved = api.database._MEMORY_CONNECTION
        api.database._MEMORY_CONNECTION = None
        try:
            with patch.object(api.database._db_manager, "close_shared_connection"):
                api.database._cleanup_memory_connection()
                api.database._cleanup_memory_connection()
        finally:
            api.database._MEMORY_CONNECTION = saved

    def test_cleanup_always_calls_manager_close_shared_connection(self):
        """_cleanup_memory_connection() must always delegate to the manager's close_shared_connection."""
        import api.database

        saved = api.database._MEMORY_CONNECTION
        api.database._MEMORY_CONNECTION = None
        try:
            with patch.object(api.database._db_manager, "close_shared_connection") as mock_close:
                api.database._cleanup_memory_connection()
            mock_close.assert_called_once()
        finally:
            api.database._MEMORY_CONNECTION = saved

    def test_cleanup_propagates_module_connection_close_error(self):
        """If closing the module-level connection raises, the error must propagate after manager cleanup."""
        import api.database

        module_conn = MagicMock(spec=sqlite3.Connection)
        module_conn.close.side_effect = sqlite3.Error("forced close error")
        manager_conn = MagicMock(spec=sqlite3.Connection)

        saved = api.database._MEMORY_CONNECTION
        api.database._MEMORY_CONNECTION = module_conn
        try:
            with patch.object(api.database._db_manager, "_memory_connection", manager_conn, create=True):
                with patch.object(api.database._db_manager, "close_shared_connection"):
                    with pytest.raises(sqlite3.Error, match="forced close error"):
                        api.database._cleanup_memory_connection()
        finally:
            api.database._MEMORY_CONNECTION = saved


class TestAtexitRegistration:
    """Tests related to atexit registration changes."""

    def test_cleanup_memory_connection_is_callable(self):
        """_cleanup_memory_connection must be a plain callable (no alias wrapping)."""
        import api.database

        assert callable(api.database._cleanup_memory_connection)

    def test_close_shared_memory_connection_alias_removed(self):
        """The _close_shared_memory_connection alias must no longer exist in the module."""
        import api.database

        assert not hasattr(
            api.database, "_close_shared_memory_connection"
        ), "_close_shared_memory_connection alias should have been removed"

    def test_atexit_db_close_registered_flag_removed(self):
        """The _ATEXIT_DB_CLOSE_REGISTERED module-level flag must no longer exist."""
        import api.database

        assert not hasattr(
            api.database, "_ATEXIT_DB_CLOSE_REGISTERED"
        ), "_ATEXIT_DB_CLOSE_REGISTERED guard variable should have been removed"

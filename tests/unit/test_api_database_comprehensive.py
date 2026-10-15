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
from unittest.mock import MagicMock, patch

import pytest

from api.database import _connect, _get_database_url, _is_memory_db, _resolve_sqlite_path, get_connection


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear cached settings before and after each test."""
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestGetDatabaseUrl:
    """Test cases for _get_database_url function."""

    def test_get_database_url_from_env(self):
        """Test reading DATABASE_URL from centralized settings."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///test.db"}):
            from src.config.settings import get_settings

            get_settings.cache_clear()
            url = _get_database_url()

        assert "sqlite:///test.db" == url

    def test_get_database_url_ignores_asset_graph_database_url(self):
        """Test that API database helpers do not consume ASSET_GRAPH_DATABASE_URL."""
        with patch.dict(
            os.environ,
            {
                "ASSET_GRAPH_DATABASE_URL": "postgresql://user:pass@localhost/db",
                "DATABASE_URL": "sqlite:///api.db",
            },
        ):
            from src.config.settings import get_settings

            get_settings.cache_clear()
            url = _get_database_url()

        assert "sqlite:///api.db" == url

    def test_get_database_url_raises_when_database_url_not_set(self):
        """Test that ValueError is raised when DATABASE_URL is not set."""
        with patch.dict(
            os.environ,
            {"ASSET_GRAPH_DATABASE_URL": "postgresql://user:pass@localhost/db"},
            clear=True,
        ):
            from src.config.settings import get_settings

            get_settings.cache_clear()
            with pytest.raises(ValueError) as exc_info:
                _get_database_url()

        assert "No database URL configured" in str(exc_info.value)


class TestResolveSqlitePath:
    """Test cases for _resolve_sqlite_path function."""

    def test_resolve_sqlite_path_memory_colon(self):
        """Test resolving :memory: path."""
        path = _resolve_sqlite_path("sqlite:///:memory:")
        assert ":memory:" == path

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
        with patch.object(api.database._CONNECTION_STATE, "manager", temp_manager):
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

        with patch.object(api.database._CONNECTION_STATE, "manager", mock_manager):
            conn = _connect()

        mock_manager.connect.assert_called_once()
        assert conn == mock_conn

    def test_connect_with_uri_path(self):
        """Test connecting with URI-style database path uses URI mode."""
        import api.database

        temp_manager = api.database._DatabaseConnectionManager("file:test.db?mode=ro")

        with (
            patch.object(api.database, "DATABASE_PATH", "file:test.db?mode=ro"),
            patch.object(api.database._CONNECTION_STATE, "manager", temp_manager),
            patch("api.database.sqlite3.connect") as mock_connect,
        ):
            mock_connection = MagicMock()
            mock_connect.return_value = mock_connection

            connection = _connect()

        assert connection is mock_connection
        mock_connect.assert_called_once_with(
            "file:test.db?mode=ro",
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
            uri=True,
        )


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
        saved_module_conn = api.database._CONNECTION_STATE.connection
        saved_module_conn_manager = api.database._CONNECTION_STATE.connection_manager
        api.database._CONNECTION_STATE.connection = None
        api.database._CONNECTION_STATE.connection_manager = None
        try:
            with (
                patch.object(api.database._CONNECTION_STATE, "manager", temp_manager),
                patch.object(api.database, "_is_memory_db", return_value=True),
            ):
                conn = api.database._connect()
                assert (
                    api.database._CONNECTION_STATE.connection is conn
                ), "_MEMORY_CONNECTION global must be set to the returned connection"
        finally:
            api.database._CONNECTION_STATE.connection = saved_module_conn
            api.database._CONNECTION_STATE.connection_manager = saved_module_conn_manager
            if temp_manager._memory_connection is not None:
                temp_manager._memory_connection.close()
                temp_manager._memory_connection = None

    def test_connect_returns_same_memory_connection_on_repeated_calls(self):
        """Second call to _connect() for in-memory DB must return the cached connection."""
        import api.database

        temp_manager = api.database._DatabaseConnectionManager(":memory:")
        saved_module_conn = api.database._CONNECTION_STATE.connection
        saved_module_conn_manager = api.database._CONNECTION_STATE.connection_manager
        api.database._CONNECTION_STATE.connection = None
        api.database._CONNECTION_STATE.connection_manager = None
        try:
            with (
                patch.object(api.database, "DATABASE_PATH", ":memory:"),
                patch.object(api.database._CONNECTION_STATE, "manager", temp_manager),
            ):
                conn1 = api.database._connect()
                conn2 = api.database._connect()
                assert conn1 is conn2, "Repeated _connect() calls must return the same cached connection"
        finally:
            api.database._CONNECTION_STATE.connection = saved_module_conn
            api.database._CONNECTION_STATE.connection_manager = saved_module_conn_manager
            if temp_manager._memory_connection is not None:
                temp_manager._memory_connection.close()
                temp_manager._memory_connection = None

    def test_connect_does_not_cache_file_connection(self):
        """_connect() must not touch _MEMORY_CONNECTION when the DB is file-backed."""
        import api.database

        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_manager = MagicMock()
        mock_manager.connect.return_value = mock_conn

        saved_module_conn = api.database._CONNECTION_STATE.connection
        saved_module_conn_manager = api.database._CONNECTION_STATE.connection_manager
        api.database._CONNECTION_STATE.connection = None
        api.database._CONNECTION_STATE.connection_manager = None
        try:
            with (
                patch.object(api.database._CONNECTION_STATE, "manager", mock_manager),
                patch.object(api.database, "_is_memory_db", return_value=False),
            ):
                api.database._connect()
                assert (
                    api.database._CONNECTION_STATE.connection is None
                ), "_MEMORY_CONNECTION must remain None for file-backed databases"
        finally:
            api.database._CONNECTION_STATE.connection = saved_module_conn
            api.database._CONNECTION_STATE.connection_manager = saved_module_conn_manager


class TestCleanupMemoryConnection:
    """Tests for the refactored _cleanup_memory_connection() function."""

    def test_cleanup_clears_module_level_memory_connection(self):
        """_cleanup_memory_connection() must set module-level _MEMORY_CONNECTION to None."""
        import api.database

        mock_conn = MagicMock(spec=sqlite3.Connection)
        saved = api.database._CONNECTION_STATE.connection
        api.database._CONNECTION_STATE.connection = mock_conn
        try:
            with patch.object(api.database._CONNECTION_STATE.manager, "close_shared_connection"):
                api.database._cleanup_memory_connection()
            assert api.database._CONNECTION_STATE.connection is None
        finally:
            api.database._CONNECTION_STATE.connection = saved

    def test_cleanup_closes_module_connection_when_distinct_from_manager(self):
        """When module and manager hold different connections, the module one must be closed."""
        import api.database

        module_conn = MagicMock(spec=sqlite3.Connection)
        manager_conn = MagicMock(spec=sqlite3.Connection)

        saved = api.database._CONNECTION_STATE.connection
        api.database._CONNECTION_STATE.connection = module_conn
        try:
            with (
                patch.object(api.database._CONNECTION_STATE.manager, "_memory_connection", manager_conn, create=True),
                patch.object(api.database._CONNECTION_STATE.manager, "close_shared_connection"),
            ):
                api.database._cleanup_memory_connection()
            module_conn.close.assert_called_once()
        finally:
            api.database._CONNECTION_STATE.connection = saved

    def test_cleanup_does_not_double_close_when_connections_are_same(self):
        """When module-level and manager connections are identical, only one close must occur."""
        import api.database

        shared_conn = MagicMock(spec=sqlite3.Connection)

        saved = api.database._CONNECTION_STATE.connection
        api.database._CONNECTION_STATE.connection = shared_conn
        try:
            # Patch _memory_connection on the real _db_manager instance
            original_mc = api.database._CONNECTION_STATE.manager._memory_connection
            api.database._CONNECTION_STATE.manager._memory_connection = shared_conn
            try:
                with patch.object(api.database._CONNECTION_STATE.manager, "close_shared_connection"):
                    api.database._cleanup_memory_connection()
                # The module-level branch skips close because they are the same object
                shared_conn.close.assert_not_called()
            finally:
                api.database._CONNECTION_STATE.manager._memory_connection = original_mc
        finally:
            api.database._CONNECTION_STATE.connection = saved

    def test_cleanup_is_idempotent(self):
        """Calling _cleanup_memory_connection() multiple times must not raise."""
        import api.database

        saved = api.database._CONNECTION_STATE.connection
        api.database._CONNECTION_STATE.connection = None
        try:
            with patch.object(api.database._CONNECTION_STATE.manager, "close_shared_connection"):
                api.database._cleanup_memory_connection()
                api.database._cleanup_memory_connection()
        finally:
            api.database._CONNECTION_STATE.connection = saved

    def test_cleanup_always_calls_manager_close_shared_connection(self):
        """_cleanup_memory_connection() must always delegate to the manager's close_shared_connection."""
        import api.database

        saved = api.database._CONNECTION_STATE.connection
        api.database._CONNECTION_STATE.connection = None
        try:
            with patch.object(api.database._CONNECTION_STATE.manager, "close_shared_connection") as mock_close:
                api.database._cleanup_memory_connection()
            mock_close.assert_called_once()
        finally:
            api.database._CONNECTION_STATE.connection = saved

    def test_cleanup_propagates_module_connection_close_error(self):
        """If closing the module-level connection raises, the error must propagate after manager cleanup."""
        import api.database

        module_conn = MagicMock(spec=sqlite3.Connection)
        module_conn.close.side_effect = sqlite3.Error("forced close error")
        manager_conn = MagicMock(spec=sqlite3.Connection)

        saved = api.database._CONNECTION_STATE.connection
        api.database._CONNECTION_STATE.connection = module_conn
        try:
            with (
                patch.object(api.database._CONNECTION_STATE.manager, "_memory_connection", manager_conn, create=True),
                patch.object(api.database._CONNECTION_STATE.manager, "close_shared_connection"),
                pytest.raises(sqlite3.Error, match="forced close error"),
            ):
                api.database._cleanup_memory_connection()
        finally:
            api.database._CONNECTION_STATE.connection = saved


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


@pytest.mark.unit
def test_binding_restores_connection_state_when_temporary_cleanup_fails(monkeypatch) -> None:
    """Cleanup failure must not replace the previous target or its owned cache."""
    import api.database

    state = api.database._CONNECTION_STATE
    previous = (
        api.database._effective_database_target(),
        state.target,
        state.manager,
        state.connection,
        state.connection_manager,
    )
    temporary = MagicMock()
    temporary._memory_connection = None
    failure = sqlite3.Error("temporary close failed")
    temporary.close_shared_connection.side_effect = failure
    monkeypatch.setattr(api.database, "_DatabaseConnectionManager", lambda _path: temporary)
    with (
        pytest.raises(sqlite3.Error, match="temporary close failed"),
        api.database.bind_database_url("sqlite:///:memory:"),
    ):
        assert state.manager is temporary
    restored = (
        api.database._effective_database_target(),
        state.target,
        state.manager,
        state.connection,
        state.connection_manager,
    )
    assert restored == previous


@pytest.mark.unit
def test_nested_binding_restores_each_owned_target_and_cache() -> None:
    """Nested failure closes only the inner cache and restores each previous binding."""
    import api.database

    state = api.database._CONNECTION_STATE
    previous = (state.target, state.manager, state.connection, state.connection_manager)
    constants = (api.database.DATABASE_URL, api.database.DATABASE_TYPE, api.database.DATABASE_PATH)
    with (
        api.database.bind_database_url("sqlite:///:memory:"),
        api.database.get_connection() as outer,
    ):
        outer.execute("CREATE TABLE outer_sentinel (value INTEGER)")
        outer_target = state.target
        outer_manager = state.manager
        with (
            pytest.raises(RuntimeError, match="inner binding failed"),
            api.database.bind_database_url("sqlite:///:memory:"),
            api.database.get_connection() as inner,
        ):
            assert inner is not outer
            raise RuntimeError("inner binding failed")
        assert state.target is outer_target
        assert state.manager is outer_manager
        assert state.connection is outer
        assert outer is not None
        assert 0 == outer.execute("SELECT COUNT(*) FROM outer_sentinel").fetchone()[0]
        assert inner is not None
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            inner.execute("SELECT 1")
    assert (state.target, state.manager, state.connection, state.connection_manager) == previous
    assert (api.database.DATABASE_URL, api.database.DATABASE_TYPE, api.database.DATABASE_PATH) == constants
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        outer.execute("SELECT 1")


@pytest.mark.unit
def test_binding_setup_failure_preserves_state_and_releases_lock(monkeypatch) -> None:
    """Manager construction failure publishes no target and leaves binding usable."""
    import api.database

    state = api.database._CONNECTION_STATE
    previous = (state.target, state.manager, state.connection, state.connection_manager)
    failure = sqlite3.Error("manager construction failed")
    with monkeypatch.context() as scoped:
        scoped.setattr(api.database, "_DatabaseConnectionManager", MagicMock(side_effect=failure))
        with (
            pytest.raises(sqlite3.Error, match="manager construction failed"),
            api.database.bind_database_url("sqlite:///:memory:"),
        ):
            pytest.fail("failed setup must not enter the binding body")
    assert (state.target, state.manager, state.connection, state.connection_manager) == previous
    with api.database.bind_database_url("sqlite:///:memory:"):
        assert state.target is not None
        assert ":memory:" == state.target.path
    assert (state.target, state.manager, state.connection, state.connection_manager) == previous


@pytest.mark.unit
def test_invalid_binding_url_does_not_change_state() -> None:
    """Unsupported schemes fail before creating or publishing a binding."""
    import api.database

    state = api.database._CONNECTION_STATE
    previous = (state.target, state.manager, state.connection, state.connection_manager)
    with (
        pytest.raises(ValueError, match="Unsupported database URL scheme"),
        api.database.bind_database_url("https://invalid.example/database"),
    ):
        pytest.fail("invalid target must not enter the binding body")
    assert (state.target, state.manager, state.connection, state.connection_manager) == previous


def _binding_lock_is_available_to_worker() -> bool:
    """Acquire and release the binding lock from a thread other than the test owner."""
    import api.database

    acquired = api.database._DATABASE_BINDING_LOCK.acquire(blocking=False)
    if acquired:
        api.database._DATABASE_BINDING_LOCK.release()
    return acquired


def _fail_inside_bound_database(executor) -> None:
    """Raise from inside a binding after proving another thread cannot acquire its lock."""
    import api.database

    with api.database.bind_database_url("sqlite:///:memory:"):
        assert executor.submit(_binding_lock_is_available_to_worker).result(timeout=5) is False
        raise RuntimeError("binding body failed")


@pytest.mark.unit
def test_binding_lock_is_held_then_released_after_failure() -> None:
    """A failing binding retains exclusion until restoration and releases it afterwards."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(RuntimeError, match="binding body failed"):
            _fail_inside_bound_database(executor)
        assert executor.submit(_binding_lock_is_available_to_worker).result(timeout=5) is True


@pytest.mark.unit
def test_postgresql_binding_uses_owned_target_without_mutating_constants() -> None:
    """The driver receives the bound URL and backend while import-time exports stay stable."""
    import api.database

    constants = (api.database.DATABASE_URL, api.database.DATABASE_TYPE, api.database.DATABASE_PATH)
    target = "postgresql://runtime@127.0.0.1/runtime_db"
    connection = MagicMock()
    with (
        patch("psycopg2.connect", return_value=connection) as connect,
        api.database.bind_database_url(target),
    ):
        with api.database.get_connection() as opened:
            assert opened is connection
        assert target == connect.call_args.args[0]
        assert "postgresql" == api.database._effective_database_target().database_type
        assert target == api.database._effective_database_target().path
    assert (api.database.DATABASE_URL, api.database.DATABASE_TYPE, api.database.DATABASE_PATH) == constants
    connection.close.assert_called_once()

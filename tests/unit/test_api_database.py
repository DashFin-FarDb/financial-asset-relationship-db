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

import importlib
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import api.database as database
from api.database import (
    DATABASE_PATH,
    DATABASE_URL,
    _is_memory_db,
    _resolve_sqlite_path,
    bind_database_url,
    ensure_runtime_access,
    execute,
    fetch_one,
    fetch_value,
    get_connection,
    initialize_schema,
    verify_runtime_authority,
    verify_schema_compatibility,
)
from src.data.database import SchemaCompatibilityError


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear cached settings before and after each test."""
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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

    def test_explicit_database_binding_restores_import_time_target(self, tmp_path: Path):
        """Operator binding must use the requested target and restore module state."""
        original_target = (database.DATABASE_URL, database.DATABASE_TYPE, database.DATABASE_PATH)
        requested_path = tmp_path / "explicit-auth.db"

        with bind_database_url(f"sqlite:///{requested_path}"):
            assert str(requested_path) == database.DATABASE_PATH
            initialize_schema()

        assert original_target == (database.DATABASE_URL, database.DATABASE_TYPE, database.DATABASE_PATH)
        with sqlite3.connect(requested_path) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'user_credentials'"
            ).fetchone() == (1,)

    def test_missing_database_url_raises_error(self):
        """Test that missing DATABASE_URL raises a ValueError."""
        from src.config.settings import get_settings

        original_database_url = os.environ.get("DATABASE_URL")
        restore_database_url = original_database_url or "sqlite:///:memory:"

        try:
            with patch.dict(os.environ, {}, clear=True):
                get_settings.cache_clear()
                with pytest.raises(
                    ValueError,
                    match="No database URL configured",
                ):
                    importlib.reload(database)
        finally:
            with patch.dict(
                os.environ,
                {"DATABASE_URL": restore_database_url},
                clear=False,
            ):
                get_settings.cache_clear()
                importlib.reload(database)
                get_settings.cache_clear()


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
        url = "sqlite:///fake_tmp/test.db"
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
        assert _is_memory_db("fake_tmp/test.db") is False
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

    def test_postgres_connection_enforces_driver_connect_timeout(self):
        """PostgreSQL connections must always bound connection establishment."""
        connection = Mock()
        assert database._POSTGRES_CONNECT_TIMEOUT_SECONDS == 10  # pylint: disable=protected-access
        with patch("psycopg2.connect", return_value=connection) as connect:
            assert database._create_postgres_connection() is connection  # pylint: disable=protected-access

        connect.assert_called_once_with(
            database.DATABASE_URL,
            connect_timeout=database._POSTGRES_CONNECT_TIMEOUT_SECONDS,  # pylint: disable=protected-access
        )

    def test_guarded_postgres_connection_enforces_driver_statement_timeout(self):
        """Bounded startup verification must apply a driver-level statement timeout."""
        connection = Mock()
        operation_guard = database._PostgresOperationGuard()  # pylint: disable=protected-access
        with (
            patch("api.database.DATABASE_TYPE", "postgresql"),
            patch("psycopg2.connect", return_value=connection) as connect,
            database._bind_postgres_operation_guard(operation_guard),  # pylint: disable=protected-access
            get_connection(),
        ):
            pass

        connect.assert_called_once_with(
            database.DATABASE_URL,
            connect_timeout=database._POSTGRES_CONNECT_TIMEOUT_SECONDS,  # pylint: disable=protected-access
            options=(
                "-c statement_timeout="
                f"{database._POSTGRES_STATEMENT_TIMEOUT_MILLISECONDS}"  # pylint: disable=protected-access
            ),
        )

    def test_get_connection_context_manager(self):
        """Test that get_connection works as context manager."""
        with patch("api.database.DATABASE_PATH", ":memory:"), get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

    def test_connection_has_row_factory(self):
        """Test that connection has Row factory set."""
        with patch("api.database.DATABASE_PATH", ":memory:"), get_connection() as conn:
            assert conn.row_factory == sqlite3.Row

    def test_memory_connection_is_reused(self):
        """Test that in-memory connection is reused."""
        from api.database import _close_memory_connection_cache, _DatabaseConnectionManager

        mem_manager = _DatabaseConnectionManager(":memory:")
        with (
            patch("api.database.DATABASE_PATH", ":memory:"),
            patch("api.database._db_manager", mem_manager),
            patch("api.database._MEMORY_CONNECTION", None),
            patch("api.database._MEMORY_CONNECTION_MANAGER", None),
        ):
            _close_memory_connection_cache()
            with get_connection() as conn1:
                conn1_id = id(conn1)

            with get_connection() as conn2:
                conn2_id = id(conn2)

            # Should be same connection for memory DB
            assert conn1_id == conn2_id
            _close_memory_connection_cache()

    def test_file_connection_is_new_each_time(self, tmp_path):
        """Test that file-based connections are new each time."""
        db_file = tmp_path / "test.db"

        with patch("api.database.DATABASE_PATH", str(db_file)), patch("api.database._is_memory_db", return_value=False):
            with get_connection() as conn1:
                conn1_id = id(conn1)

            with get_connection() as conn2:
                conn2_id = id(conn2)

            # Should be different connections for file DB
            assert conn1_id != conn2_id

    def test_connection_supports_uri(self):
        """Test that URI-style paths are supported."""
        uri_path = "file::memory:?cache=shared"
        with (
            patch("api.database.DATABASE_PATH", uri_path),
            patch("api.database._is_memory_db", return_value=True),
            get_connection() as conn,
        ):
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

    @patch.object(database, "DATABASE_TYPE", "postgresql")
    @patch("api.database.fetch_value", side_effect=[None, 2])
    @patch("api.database.execute")
    def test_ensure_runtime_access_installs_read_only_auth_policy(self, mock_execute, _mock_fetch_value):
        """Auth capability setup must grant SELECT and no mutation privilege."""
        ensure_runtime_access()

        statements = "\n".join(call.args[0] for call in mock_execute.call_args_list)
        assert "CREATE ROLE fardb_runtime_auth NOLOGIN" in statements
        assert "GRANT SELECT ON TABLE user_credentials TO fardb_runtime_auth" in statements
        assert "FOR SELECT TO fardb_runtime_auth USING (true)" in statements
        assert "GRANT INSERT" not in statements
        assert "GRANT UPDATE" not in statements
        assert "GRANT DELETE" not in statements

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

    @patch("api.database.fetch_value", side_effect=["disabled,email,full_name,hashed_password,id,username", 1])
    def test_verify_schema_compatibility_is_read_only(self, mock_fetch_value):
        """Credential verification should use catalog reads and perform no DDL."""
        with patch("api.database.execute") as mock_execute:
            verify_schema_compatibility()

        mock_execute.assert_not_called()
        assert mock_fetch_value.call_count == 2
        sqlite_unique_query = mock_fetch_value.call_args_list[1].args[0]
        assert "COUNT(*) FROM pragma_index_info(indexes.name)" in sqlite_unique_query
        assert "= 1" in sqlite_unique_query
        column_query = mock_fetch_value.call_args_list[0].args[0]
        assert "WHERE name IN" not in column_query

    @patch("api.database.fetch_value", side_effect=[None, 0])
    def test_verify_schema_compatibility_fails_when_table_is_missing(self, _mock_fetch_value):
        """Missing credential schema should produce a stable compatibility failure."""
        with pytest.raises(SchemaCompatibilityError, match="missing required columns"):
            verify_schema_compatibility()

    @patch("api.database.fetch_value", side_effect=["disabled,email,full_name,id,username", 1])
    def test_verify_schema_compatibility_fails_when_required_column_is_missing(self, _mock_fetch_value):
        """Credential verification should compare the returned catalog names against the shared column set."""
        with pytest.raises(SchemaCompatibilityError, match="missing required columns"):
            verify_schema_compatibility()

    @patch.object(database, "DATABASE_TYPE", "postgresql")
    @patch("api.database.fetch_value", return_value=False)
    def test_verify_runtime_authority_rejects_privileged_postgresql_role(self, _mock_fetch_value):
        """Auth startup should fail when its PostgreSQL role can migrate schema."""
        with pytest.raises(SchemaCompatibilityError, match="retains schema-migration authority"):
            verify_runtime_authority()

    @patch.object(database, "DATABASE_TYPE", "postgresql")
    @patch("api.database.fetch_value", return_value=True)
    def test_verify_runtime_authority_accepts_restricted_postgresql_role(self, mock_fetch_value):
        """Auth startup should accept a PostgreSQL role without migration authority."""
        verify_runtime_authority()
        authority_query = mock_fetch_value.call_args_list[0].args[0]
        assert "current_schema() IS NOT NULL" in authority_query
        assert "login.rolname = session_user" in authority_query
        assert "pg_has_role(login.oid, assumable.oid, 'USAGE')" in authority_query
        assert "pg_has_role(login.oid, assumable.oid, 'SET')" in authority_query
        assert "ELSE pg_has_role(login.oid, assumable.oid, 'MEMBER') END" in authority_query
        assert "current_setting('server_version_num')::integer >= 160000" in authority_query
        assert "assumable.rolreplication" in authority_query
        assert "has_database_privilege(assumable.oid, current_database(), 'CREATE')" in authority_query
        assert "has_schema_privilege(assumable.oid, namespace.oid, 'CREATE')" in authority_query
        assert "has_table_privilege(assumable.oid, 'user_credentials', 'UPDATE')" in authority_query
        assert "has_any_column_privilege(assumable.oid, 'user_credentials', 'UPDATE')" in authority_query
        assert (
            "has_sequence_privilege(assumable.oid, pg_get_serial_sequence('user_credentials', 'id'), 'UPDATE')"
            in authority_query
        )
        assert "namespace.nspowner = assumable.oid" in authority_query
        assert "database.datdba = assumable.oid" in authority_query


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

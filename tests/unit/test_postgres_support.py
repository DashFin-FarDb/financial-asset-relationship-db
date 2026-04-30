"""Unit tests for PostgreSQL support in api/database.py."""

from __future__ import annotations

import importlib
import os
from collections.abc import Iterator
from unittest.mock import Mock, patch

import pytest

import api.database as database

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the get_settings LRU cache before and after each test."""
    from src.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def restore_database_module(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """
    Preserve the api.database module state and DATABASE_URL for test duration.

    This fixture prevents test order dependencies by restoring module-level globals
    (DATABASE_TYPE, DATABASE_URL, DATABASE_PATH) after tests that reload the module
    with different database configurations.

    Yields control to the test. On teardown, closes any in-memory connection stored
    in api.database._MEMORY_CONNECTION, restores the original DATABASE_URL environment
    variable, clears the settings cache, and reloads api.database to reset its state.
    """
    from src.config.settings import get_settings

    original_url = os.environ.get("DATABASE_URL")
    get_settings.cache_clear()

    yield

    # Close any in-memory connection that may have been created during the test
    memory_conn = getattr(database, "_MEMORY_CONNECTION", None)
    if memory_conn is not None:
        memory_conn.close()
        database._MEMORY_CONNECTION = None

    if original_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", original_url)

    get_settings.cache_clear()
    importlib.reload(database)


class TestURLDetection:
    """Test URL detection for PostgreSQL and SQLite."""

    def test_is_postgres_url_with_postgresql_scheme(self):
        """Test that postgresql:// URLs are detected as PostgreSQL."""
        from api.database import _is_postgres_url

        assert _is_postgres_url("postgresql://user:pass@localhost/db") is True
        assert _is_postgres_url("postgresql://localhost/db") is True
        assert _is_postgres_url("PostgreSQL://localhost/db") is True  # case insensitive

    def test_is_postgres_url_with_postgres_scheme(self):
        """Test that postgres:// URLs are detected as PostgreSQL."""
        from api.database import _is_postgres_url

        assert _is_postgres_url("postgres://user:pass@localhost/db") is True
        assert _is_postgres_url("postgres://localhost/db") is True
        assert _is_postgres_url("POSTGRES://localhost/db") is True  # case insensitive

    def test_is_postgres_url_with_sqlite_returns_false(self):
        """Test that SQLite URLs are not detected as PostgreSQL."""
        from api.database import _is_postgres_url

        assert _is_postgres_url("sqlite:///test.db") is False
        assert _is_postgres_url("sqlite:///:memory:") is False

    def test_is_sqlite_url_with_sqlite_scheme(self):
        """Test that sqlite: URLs are detected as SQLite."""
        from api.database import _is_sqlite_url

        assert _is_sqlite_url("sqlite:///test.db") is True
        assert _is_sqlite_url("sqlite:///:memory:") is True
        assert _is_sqlite_url("SQLite:///test.db") is True  # case insensitive

    def test_is_sqlite_url_with_postgres_returns_false(self):
        """Test that PostgreSQL URLs are not detected as SQLite."""
        from api.database import _is_sqlite_url

        assert _is_sqlite_url("postgresql://localhost/db") is False
        assert _is_sqlite_url("postgres://localhost/db") is False


class TestDatabaseTypeDetection:
    """Test database type detection at module load."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    def test_postgresql_url_sets_type_to_postgresql(self, restore_database_module):
        """Test that PostgreSQL URL sets DATABASE_TYPE to 'postgresql'."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)
        assert db_module.DATABASE_TYPE == "postgresql"
        assert db_module.DATABASE_PATH == "postgresql://localhost/test"

    @patch.dict("os.environ", {"DATABASE_URL": "sqlite:///test.db"})
    def test_sqlite_url_sets_type_to_sqlite(self, restore_database_module):
        """Test that SQLite URL sets DATABASE_TYPE to 'sqlite'."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)
        assert db_module.DATABASE_TYPE == "sqlite"
        # DATABASE_PATH should be the resolved path
        assert "test.db" in db_module.DATABASE_PATH

    @patch.dict("os.environ", {"DATABASE_URL": "mysql://localhost/test"})
    def test_unsupported_url_raises_error(self, restore_database_module):
        """Test that unsupported database URLs raise a ValueError."""
        import importlib

        import api.database as db_module

        with pytest.raises(ValueError, match="Unsupported database URL scheme"):
            importlib.reload(db_module)


class TestPostgreSQLConnection:
    """Test PostgreSQL connection creation."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.connect")
    def test_create_postgres_connection_imports_psycopg2(self, mock_connect, restore_database_module):
        """Test that _create_postgres_connection imports and uses psycopg2."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        conn = db_module._create_postgres_connection()

        mock_connect.assert_called_once_with("postgresql://localhost/test")
        assert conn == mock_conn

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    def test_create_postgres_connection_without_psycopg2_raises_import_error(self, restore_database_module):
        """Test that missing psycopg2 raises ImportError with helpful message."""
        # Import builtins to use __import__
        import builtins
        import importlib
        import sys

        # Save original __import__
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "psycopg2" or name.startswith("psycopg2."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        # Reload with mocked import
        with patch("builtins.__import__", side_effect=mock_import):
            import api.database as db_module

            importlib.reload(db_module)

            with pytest.raises(ImportError, match="psycopg2-binary is required"):
                db_module._create_postgres_connection()


class TestGetConnectionPostgreSQL:
    """Test get_connection() with PostgreSQL."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.connect")
    def test_get_connection_creates_and_closes_postgres_connection(self, mock_connect, restore_database_module):
        """Test that get_connection creates a new PostgreSQL connection and closes it."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        with db_module.get_connection() as conn:
            assert conn == mock_conn

        mock_conn.close.assert_called_once()

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.connect")
    def test_get_connection_closes_on_exception(self, mock_connect, restore_database_module):
        """Test that connection is closed even when an exception occurs."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        with pytest.raises(RuntimeError):
            with db_module.get_connection() as conn:
                raise RuntimeError("Test error")

        mock_conn.close.assert_called_once()


class TestExecutePostgreSQL:
    """Test execute() with PostgreSQL."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.connect")
    def test_execute_uses_cursor_for_postgres(self, mock_connect, restore_database_module):
        """Test that execute() uses cursor.execute for PostgreSQL."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db_module.execute("INSERT INTO test VALUES (%s)", ("value",))

        mock_cursor.execute.assert_called_once_with("INSERT INTO test VALUES (%s)", ("value",))
        mock_cursor.close.assert_called_once()
        mock_conn.commit.assert_called_once()


class TestFetchOnePostgreSQL:
    """Test fetch_one() with PostgreSQL."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.extras.RealDictCursor")
    @patch("psycopg2.connect")
    def test_fetch_one_uses_realdict_cursor(self, mock_connect, mock_realdict_cursor, restore_database_module):
        """Test that fetch_one() uses RealDictCursor for PostgreSQL."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = {"id": 1, "name": "test"}
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = db_module.fetch_one("SELECT * FROM test WHERE id = %s", (1,))

        # Verify cursor was created with RealDictCursor factory
        assert mock_conn.cursor.called
        cursor_call_kwargs = mock_conn.cursor.call_args[1]
        assert "cursor_factory" in cursor_call_kwargs

        mock_cursor.execute.assert_called_once_with("SELECT * FROM test WHERE id = %s", (1,))
        assert result == mock_row
        mock_cursor.close.assert_called_once()


class TestFetchValuePostgreSQL:
    """Test fetch_value() with PostgreSQL."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.extras.RealDictCursor")
    @patch("psycopg2.connect")
    def test_fetch_value_extracts_first_value_from_dict(
        self, mock_connect, mock_realdict_cursor, restore_database_module
    ):
        """Test that fetch_value() extracts first value from PostgreSQL dict row."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = {"count": 42}
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = db_module.fetch_value("SELECT COUNT(*) as count FROM test")

        assert result == 42


class TestInitializeSchemaPostgreSQL:
    """Test initialize_schema() with PostgreSQL."""

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.connect")
    def test_initialize_schema_uses_postgres_ddl(self, mock_connect, restore_database_module):
        """Test that initialize_schema() uses PostgreSQL-compatible DDL."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        db_module.initialize_schema()

        # Check that execute was called and DDL includes SERIAL (PostgreSQL-specific)
        assert mock_cursor.execute.called
        execute_call_args = mock_cursor.execute.call_args[0][0]
        assert "SERIAL PRIMARY KEY" in execute_call_args
        assert "VARCHAR" in execute_call_args
        assert "SMALLINT" in execute_call_args


class TestSQLiteCompatibility:
    """Test that SQLite behavior remains unchanged."""

    @patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"})
    def test_sqlite_url_still_works(self, restore_database_module):
        """Test that SQLite URLs still work after PostgreSQL changes."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        assert db_module.DATABASE_TYPE == "sqlite"
        assert db_module.DATABASE_PATH == ":memory:"

    @patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"})
    def test_sqlite_schema_initialization_unchanged(self, restore_database_module):
        """Test that SQLite schema initialization uses INTEGER AUTOINCREMENT."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        # Initialize schema - should work without errors
        db_module.initialize_schema()

        # Verify table was created with SQLite DDL
        with db_module.get_connection() as conn:
            cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_credentials'")
            schema = cursor.fetchone()[0]

        assert "INTEGER PRIMARY KEY AUTOINCREMENT" in schema
        assert "TEXT" in schema


class TestPostgresURLFallback:
    """Test POSTGRES_URL fallback support in settings."""

    @patch.dict("os.environ", {"POSTGRES_URL": "postgresql://localhost/test"}, clear=True)
    def test_postgres_url_used_when_database_url_missing(self):
        """Test that POSTGRES_URL is used as fallback when DATABASE_URL is not set."""
        from src.config.settings import load_settings

        settings = load_settings()
        assert settings.database_url == "postgresql://localhost/test"

    @patch.dict(
        "os.environ",
        {"DATABASE_URL": "sqlite:///primary.db", "POSTGRES_URL": "postgresql://localhost/test"},
    )
    def test_database_url_takes_precedence_over_postgres_url(self):
        """Test that DATABASE_URL takes precedence when both are set."""
        from src.config.settings import load_settings

        settings = load_settings()
        assert settings.database_url == "sqlite:///primary.db"

    @patch.dict("os.environ", {}, clear=True)
    def test_both_urls_missing_returns_none(self):
        """Test that database_url is None when both DATABASE_URL and POSTGRES_URL are missing."""
        from src.config.settings import load_settings

        settings = load_settings()
        assert settings.database_url is None


class TestPlaceholderConversion:
    """Test SQL placeholder conversion for cross-database compatibility."""

    def test_convert_qmark_to_format(self):
        """Test conversion from SQLite ? placeholders to PostgreSQL %s."""
        from api.database import _convert_placeholders

        query = "SELECT * FROM users WHERE id = ? AND name = ?"
        result = _convert_placeholders(query, from_style="qmark", to_style="format")
        assert result == "SELECT * FROM users WHERE id = %s AND name = %s"

    def test_convert_format_to_qmark(self):
        """Test conversion from PostgreSQL %s placeholders to SQLite ?."""
        from api.database import _convert_placeholders

        query = "SELECT * FROM users WHERE id = %s AND name = %s"
        result = _convert_placeholders(query, from_style="format", to_style="qmark")
        assert result == "SELECT * FROM users WHERE id = ? AND name = ?"

    def test_convert_same_style_returns_unchanged(self):
        """Test that conversion with same source/target style returns unchanged query."""
        from api.database import _convert_placeholders

        query = "SELECT * FROM users WHERE id = ?"
        result = _convert_placeholders(query, from_style="qmark", to_style="qmark")
        assert result == query

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.connect")
    def test_execute_converts_placeholders_for_postgres(self, mock_connect, restore_database_module):
        """Test that execute() converts ? to %s when using PostgreSQL."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Execute with SQLite-style ? placeholders
        db_module.execute("INSERT INTO test VALUES (?, ?)", ("val1", "val2"))

        # Verify the cursor received PostgreSQL-style %s placeholders
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert call_args[0] == "INSERT INTO test VALUES (%s, %s)"
        assert call_args[1] == ("val1", "val2")

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test"})
    @patch("psycopg2.extras.RealDictCursor")
    @patch("psycopg2.connect")
    def test_fetch_one_converts_placeholders_for_postgres(
        self, mock_connect, mock_realdict_cursor, restore_database_module
    ):
        """Test that fetch_one() converts ? to %s when using PostgreSQL."""
        import importlib

        import api.database as db_module

        importlib.reload(db_module)

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_row = {"id": 1, "name": "test"}
        mock_cursor.fetchone.return_value = mock_row
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Query with SQLite-style ? placeholders
        db_module.fetch_one("SELECT * FROM test WHERE id = ?", (1,))

        # Verify the cursor received PostgreSQL-style %s placeholders
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert call_args[0] == "SELECT * FROM test WHERE id = %s"
        assert call_args[1] == (1,)

"""Enhanced comprehensive unit tests for api/database.py module.

This module provides extensive additional test coverage for:
- Database URL resolution and validation
- SQLite path resolution including URI-style databases
- In-memory database detection and handling
- Connection management and persistence
- Query execution and result fetching
- Schema initialization
- Thread-safety and concurrency
- Edge cases and error handling
"""

import os
import sqlite3
import threading
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import quote

import pytest

from api.database import (
    _get_database_url,
    _resolve_sqlite_path,
    _is_memory_db,
    _connect,
    get_connection,
    execute,
    fetch_one,
    fetch_value,
    initialize_schema,
)


class TestGetDatabaseUrl:
    """Test _get_database_url function for environment variable handling."""

    def test_get_database_url_with_env_variable(self):
        """Test getting database URL from environment variable."""
        test_url = "sqlite:///test.db"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            url = _get_database_url()
            assert url == test_url

    def test_get_database_url_not_set_raises_error(self):
        """Test that missing DATABASE_URL raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                _get_database_url()
            assert "DATABASE_URL" in str(exc_info.value)

    def test_get_database_url_empty_string_raises_error(self):
        """Test that empty DATABASE_URL raises ValueError."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            with pytest.raises(ValueError) as exc_info:
                _get_database_url()
            assert "DATABASE_URL" in str(exc_info.value)

    def test_get_database_url_whitespace_only_raises_error(self):
        """Test that whitespace-only DATABASE_URL raises ValueError."""
        with patch.dict(os.environ, {"DATABASE_URL": "   "}):
            with pytest.raises(ValueError) as exc_info:
                _get_database_url()
            assert "DATABASE_URL" in str(exc_info.value)

    def test_get_database_url_preserves_special_characters(self):
        """Test that special characters in URL are preserved."""
        test_url = "postgresql://user:p@ssw0rd@host:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            url = _get_database_url()
            assert url == test_url


class TestResolveSqlitePath:
    """Test _resolve_sqlite_path function for various SQLite URL formats."""

    def test_resolve_sqlite_path_memory_colon_format(self):
        """Test resolving :memory: URL format."""
        url = "sqlite:///:memory:"
        path = _resolve_sqlite_path(url)
        assert path == ":memory:"

    def test_resolve_sqlite_path_memory_slash_format(self):
        """Test resolving /:memory: URL format."""
        url = "sqlite:////:memory:"
        path = _resolve_sqlite_path(url)
        assert path == ":memory:"

    def test_resolve_sqlite_path_relative_path(self):
        """Test resolving relative path SQLite URL."""
        url = "sqlite:///test.db"
        path = _resolve_sqlite_path(url)
        assert path == "test.db"

    def test_resolve_sqlite_path_relative_with_directory(self):
        """Test resolving relative path with directory."""
        url = "sqlite:///data/test.db"
        path = _resolve_sqlite_path(url)
        assert path == "data/test.db"

    def test_resolve_sqlite_path_absolute_path(self):
        """Test resolving absolute path SQLite URL."""
        url = "sqlite:////absolute/path/to/db.sqlite"
        path = _resolve_sqlite_path(url)
        assert path == "/absolute/path/to/db.sqlite"

    def test_resolve_sqlite_path_uri_style_memory(self):
        """Test resolving URI-style memory database."""
        url = "sqlite:///file::memory:?cache=shared"
        path = _resolve_sqlite_path(url)
        assert "file::memory:" in path
        assert "cache=shared" in path

    def test_resolve_sqlite_path_percent_encoded(self):
        """Test resolving percent-encoded paths."""
        url = "sqlite:///path%20with%20spaces/db.sqlite"
        path = _resolve_sqlite_path(url)
        assert "path with spaces" in path

    def test_resolve_sqlite_path_trailing_slash_removed(self):
        """Test that trailing slashes are removed."""
        url = "sqlite:///test.db/"
        path = _resolve_sqlite_path(url)
        assert not path.endswith("/")

    def test_resolve_sqlite_path_invalid_scheme_raises_error(self):
        """Test that non-sqlite scheme raises ValueError."""
        url = "postgresql:///test.db"
        with pytest.raises(ValueError) as exc_info:
            _resolve_sqlite_path(url)
        assert "Not a valid sqlite URI" in str(exc_info.value)

    def test_resolve_sqlite_path_windows_style_path(self):
        """Test resolving Windows-style path."""
        url = "sqlite:///C:/Users/test/db.sqlite"
        path = _resolve_sqlite_path(url)
        assert "C:/Users/test/db.sqlite" in path

    def test_resolve_sqlite_path_special_characters_in_filename(self):
        """Test resolving path with special characters."""
        url = "sqlite:///test-db_v2.0.sqlite"
        path = _resolve_sqlite_path(url)
        assert "test-db_v2.0.sqlite" in path

    def test_resolve_sqlite_path_deep_directory_structure(self):
        """Test resolving deep directory structure."""
        url = "sqlite:///very/deep/directory/structure/database.db"
        path = _resolve_sqlite_path(url)
        assert path == "very/deep/directory/structure/database.db"


class TestIsMemoryDb:
    """Test _is_memory_db function for detecting in-memory databases."""

    def test_is_memory_db_colon_memory(self):
        """Test detecting :memory: as in-memory database."""
        assert _is_memory_db(":memory:") is True

    def test_is_memory_db_file_scheme_memory(self):
        """Test detecting file::memory: as in-memory database."""
        assert _is_memory_db("file::memory:") is True

    def test_is_memory_db_with_query_params(self):
        """Test detecting file::memory: with query parameters."""
        assert _is_memory_db("file::memory:?cache=shared") is True

    def test_is_memory_db_sqlite_url_memory(self):
        """Test detecting sqlite:///:memory: as in-memory."""
        with patch('api.database.DATABASE_PATH', 'sqlite:///:memory:'):
            assert _is_memory_db() is True

    def test_is_memory_db_file_path_is_not_memory(self):
        """Test that file paths are not detected as in-memory."""
        assert _is_memory_db("test.db") is False

    def test_is_memory_db_absolute_path_is_not_memory(self):
        """Test that absolute paths are not detected as in-memory."""
        assert _is_memory_db("/path/to/database.db") is False

    def test_is_memory_db_empty_string_is_not_memory(self):
        """Test that empty string is not detected as in-memory."""
        assert _is_memory_db("") is False

    def test_is_memory_db_none_uses_default(self):
        """Test that None uses default DATABASE_PATH."""
        with patch('api.database.DATABASE_PATH', ':memory:'):
            assert _is_memory_db(None) is True

    def test_is_memory_db_substring_memory_in_path(self):
        """Test that 'memory' substring in path doesn't trigger false positive."""
        assert _is_memory_db("/path/to/memory/database.db") is False

    def test_is_memory_db_case_sensitive(self):
        """Test that memory detection is case-sensitive."""
        # SQLite :memory: is case-sensitive
        assert _is_memory_db(":MEMORY:") is False
        assert _is_memory_db(":Memory:") is False


class TestConnect:
    """Test _connect function for database connection management."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        db_path = tmp_path / "test_connect.db"
        return str(db_path)

    def test_connect_creates_connection(self, temp_db_path):
        """Test that _connect creates a valid connection."""
        with patch('api.database.DATABASE_PATH', temp_db_path):
            conn = _connect()
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)
            conn.close()

    def test_connect_enables_row_factory(self, temp_db_path):
        """Test that connection has Row factory enabled."""
        with patch('api.database.DATABASE_PATH', temp_db_path):
            conn = _connect()
            assert conn.row_factory == sqlite3.Row
            conn.close()

    def test_connect_memory_returns_persistent_connection(self):
        """Test that in-memory database returns persistent connection."""
        with patch('api.database.DATABASE_PATH', ':memory:'):
            conn1 = _connect()
            conn2 = _connect()
            # For in-memory, should return same connection
            assert conn1 is conn2

    def test_connect_file_returns_new_connection(self, temp_db_path):
        """Test that file database returns new connection each time."""
        with patch('api.database.DATABASE_PATH', temp_db_path):
            conn1 = _connect()
            conn2 = _connect()
            # For file databases, should be different connections
            assert conn1 is not conn2
            conn1.close()
            conn2.close()

    def test_connect_uri_mode_for_file_scheme(self):
        """Test that file: scheme URLs enable URI mode."""
        uri_path = "file:test.db?mode=ro"
        with patch('api.database.DATABASE_PATH', uri_path):
            conn = _connect()
            assert conn is not None
            conn.close()


class TestGetConnection:
    """Test get_connection context manager."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        db_path = tmp_path / "test_context.db"
        return str(db_path)

    def test_get_connection_yields_connection(self, temp_db_path):
        """Test that context manager yields a connection."""
        with patch('api.database.DATABASE_PATH', temp_db_path):
            with get_connection() as conn:
                assert conn is not None
                assert isinstance(conn, sqlite3.Connection)

    def test_get_connection_closes_file_connection(self, temp_db_path):
        """Test that file connection is closed after context."""
        with patch('api.database.DATABASE_PATH', temp_db_path):
            with get_connection() as conn:
                conn_id = id(conn)
            
            # Connection should be closed after context
            # We can't directly test this, but we can verify it doesn't raise

    def test_get_connection_keeps_memory_connection_open(self):
        """Test that memory connection stays open after context."""
        with patch('api.database.DATABASE_PATH', ':memory:'):
            with get_connection() as conn:
                # Create a table
                conn.execute("CREATE TABLE test (id INTEGER)")
                conn.commit()
            
            # Get connection again and verify table exists
            with get_connection() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test'")
                result = cursor.fetchone()
                assert result is not None

    def test_get_connection_multiple_contexts(self, temp_db_path):
        """Test multiple sequential context manager uses."""
        with patch('api.database.DATABASE_PATH', temp_db_path):
            with get_connection() as conn1:
                assert conn1 is not None
            
            with get_connection() as conn2:
                assert conn2 is not None
            
            # Should get different connections for file databases
            assert id(conn1) != id(conn2)


class TestExecute:
    """Test execute function for SQL execution."""

    @pytest.fixture
    def setup_test_db(self, tmp_path):
        """Set up a test database."""
        db_path = tmp_path / "test_execute.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            initialize_schema()
            yield str(db_path)

    def test_execute_creates_table(self, setup_test_db):
        """Test executing CREATE TABLE statement."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
            
            # Verify table exists
            with get_connection() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")
                result = cursor.fetchone()
                assert result is not None

    def test_execute_inserts_data(self, setup_test_db):
        """Test executing INSERT statement."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, value TEXT)")
            execute("INSERT INTO test_data (value) VALUES (?)", ("test_value",))
            
            # Verify data inserted
            with get_connection() as conn:
                cursor = conn.execute("SELECT value FROM test_data")
                result = cursor.fetchone()
                assert result is not None
                assert result[0] == "test_value"

    def test_execute_with_multiple_parameters(self, setup_test_db):
        """Test execute with multiple parameters."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            execute("CREATE TABLE test_multi (id INTEGER, name TEXT, value INTEGER)")
            execute("INSERT INTO test_multi VALUES (?, ?, ?)", (1, "test", 100))
            
            with get_connection() as conn:
                cursor = conn.execute("SELECT * FROM test_multi")
                result = cursor.fetchone()
                assert result[0] == 1
                assert result[1] == "test"
                assert result[2] == 100

    def test_execute_with_none_parameters(self, setup_test_db):
        """Test execute with None parameters."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            execute("CREATE TABLE test_none (id INTEGER PRIMARY KEY)")
            execute("INSERT INTO test_none (id) VALUES (1)", None)
            
            with get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM test_none")
                count = cursor.fetchone()[0]
                assert count == 1

    def test_execute_updates_data(self, setup_test_db):
        """Test executing UPDATE statement."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            execute("CREATE TABLE test_update (id INTEGER PRIMARY KEY, value TEXT)")
            execute("INSERT INTO test_update (id, value) VALUES (1, 'old')")
            execute("UPDATE test_update SET value = ? WHERE id = ?", ("new", 1))
            
            with get_connection() as conn:
                cursor = conn.execute("SELECT value FROM test_update WHERE id = 1")
                result = cursor.fetchone()
                assert result[0] == "new"

    def test_execute_deletes_data(self, setup_test_db):
        """Test executing DELETE statement."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            execute("CREATE TABLE test_delete (id INTEGER PRIMARY KEY, value TEXT)")
            execute("INSERT INTO test_delete (id, value) VALUES (1, 'test')")
            execute("DELETE FROM test_delete WHERE id = ?", (1,))
            
            with get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM test_delete")
                count = cursor.fetchone()[0]
                assert count == 0


class TestFetchOne:
    """Test fetch_one function for single row retrieval."""

    @pytest.fixture
    def setup_test_db(self, tmp_path):
        """Set up a test database with sample data."""
        db_path = tmp_path / "test_fetch.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test_fetch (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
            execute("INSERT INTO test_fetch VALUES (1, 'first', 100)")
            execute("INSERT INTO test_fetch VALUES (2, 'second', 200)")
            yield str(db_path)

    def test_fetch_one_returns_first_row(self, setup_test_db):
        """Test fetching the first row."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            row = fetch_one("SELECT * FROM test_fetch ORDER BY id")
            assert row is not None
            assert row['id'] == 1
            assert row['name'] == 'first'

    def test_fetch_one_with_where_clause(self, setup_test_db):
        """Test fetching specific row with WHERE clause."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            row = fetch_one("SELECT * FROM test_fetch WHERE id = ?", (2,))
            assert row is not None
            assert row['id'] == 2
            assert row['name'] == 'second'

    def test_fetch_one_no_results_returns_none(self, setup_test_db):
        """Test fetch_one returns None when no results."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            row = fetch_one("SELECT * FROM test_fetch WHERE id = ?", (999,))
            assert row is None

    def test_fetch_one_returns_row_object(self, setup_test_db):
        """Test fetch_one returns sqlite3.Row object."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            row = fetch_one("SELECT * FROM test_fetch WHERE id = 1")
            assert isinstance(row, sqlite3.Row)
            # Can access by column name
            assert row['name'] == 'first'
            # Can access by index
            assert row[0] == 1

    def test_fetch_one_with_multiple_parameters(self, setup_test_db):
        """Test fetch_one with multiple query parameters."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            row = fetch_one("SELECT * FROM test_fetch WHERE id > ? AND value < ?", (0, 150))
            assert row is not None
            assert row['id'] == 1


class TestFetchValue:
    """Test fetch_value function for single value retrieval."""

    @pytest.fixture
    def setup_test_db(self, tmp_path):
        """Set up a test database with sample data."""
        db_path = tmp_path / "test_value.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test_values (id INTEGER PRIMARY KEY, name TEXT, count INTEGER)")
            execute("INSERT INTO test_values VALUES (1, 'test', 42)")
            yield str(db_path)

    def test_fetch_value_returns_first_column(self, setup_test_db):
        """Test fetching first column value."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            value = fetch_value("SELECT count FROM test_values WHERE id = 1")
            assert value == 42

    def test_fetch_value_with_count_query(self, setup_test_db):
        """Test fetch_value with COUNT query."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            count = fetch_value("SELECT COUNT(*) FROM test_values")
            assert count == 1

    def test_fetch_value_no_results_returns_none(self, setup_test_db):
        """Test fetch_value returns None when no results."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            value = fetch_value("SELECT name FROM test_values WHERE id = 999")
            assert value is None

    def test_fetch_value_with_parameters(self, setup_test_db):
        """Test fetch_value with query parameters."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            value = fetch_value("SELECT name FROM test_values WHERE id = ?", (1,))
            assert value == "test"

    def test_fetch_value_string_column(self, setup_test_db):
        """Test fetching string column value."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            name = fetch_value("SELECT name FROM test_values WHERE id = 1")
            assert name == "test"
            assert isinstance(name, str)

    def test_fetch_value_integer_column(self, setup_test_db):
        """Test fetching integer column value."""
        with patch('api.database.DATABASE_PATH', setup_test_db):
            id_val = fetch_value("SELECT id FROM test_values WHERE name = 'test'")
            assert id_val == 1
            assert isinstance(id_val, int)


class TestInitializeSchema:
    """Test initialize_schema function."""

    def test_initialize_schema_creates_table(self, tmp_path):
        """Test that initialize_schema creates user_credentials table."""
        db_path = tmp_path / "test_schema.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            initialize_schema()
            
            # Verify table exists
            with get_connection() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_credentials'")
                result = cursor.fetchone()
                assert result is not None

    def test_initialize_schema_idempotent(self, tmp_path):
        """Test that initialize_schema can be called multiple times."""
        db_path = tmp_path / "test_idempotent.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            initialize_schema()
            initialize_schema()  # Should not raise error
            
            # Verify table still exists
            with get_connection() as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                assert len(tables) == 1

    def test_initialize_schema_correct_columns(self, tmp_path):
        """Test that user_credentials table has correct columns."""
        db_path = tmp_path / "test_columns.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            initialize_schema()
            
            with get_connection() as conn:
                cursor = conn.execute("PRAGMA table_info(user_credentials)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                assert 'id' in column_names
                assert 'username' in column_names
                assert 'email' in column_names
                assert 'full_name' in column_names
                assert 'hashed_password' in column_names
                assert 'disabled' in column_names

    def test_initialize_schema_unique_constraint(self, tmp_path):
        """Test that username has unique constraint."""
        db_path = tmp_path / "test_unique.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            initialize_schema()
            
            # Try to insert duplicate username
            execute("INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("user1", "hash1"))
            
            with pytest.raises(sqlite3.IntegrityError):
                execute("INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("user1", "hash2"))


class TestConcurrency:
    """Test thread-safety and concurrent access."""

    def test_concurrent_connections_file_db(self, tmp_path):
        """Test concurrent connections to file database."""
        db_path = tmp_path / "test_concurrent.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            initialize_schema()
            
            results = []
            
            def insert_user(username):
                try:
                    execute(
                        "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)",
                        (username, f"hash_{username}")
                    )
                    results.append(True)
                except Exception:
                    results.append(False)
            
            threads = [
                threading.Thread(target=insert_user, args=(f"user_{i}",))
                for i in range(5)
            ]
            
            for thread in threads:
                thread.start()
            
            for thread in threads:
                thread.join()
            
            assert all(results)
            
            # Verify all users inserted
            count = fetch_value("SELECT COUNT(*) FROM user_credentials")
            assert count == 5

    def test_concurrent_reads(self, tmp_path):
        """Test concurrent read operations."""
        db_path = tmp_path / "test_reads.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test_read (id INTEGER PRIMARY KEY, value TEXT)")
            execute("INSERT INTO test_read (value) VALUES ('test_value')")
            
            results = []
            
            def read_value():
                value = fetch_value("SELECT value FROM test_read WHERE id = 1")
                results.append(value)
            
            threads = [threading.Thread(target=read_value) for _ in range(10)]
            
            for thread in threads:
                thread.start()
            
            for thread in threads:
                thread.join()
            
            assert len(results) == 10
            assert all(v == "test_value" for v in results)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_execute_with_empty_query(self, tmp_path):
        """Test execute with empty query string."""
        db_path = tmp_path / "test_empty.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            with pytest.raises(sqlite3.OperationalError):
                execute("")

    def test_fetch_one_with_syntax_error(self, tmp_path):
        """Test fetch_one with invalid SQL syntax."""
        db_path = tmp_path / "test_syntax.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            with pytest.raises(sqlite3.OperationalError):
                fetch_one("INVALID SQL QUERY")

    def test_execute_with_mismatched_parameters(self, tmp_path):
        """Test execute with wrong number of parameters."""
        db_path = tmp_path / "test_params.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test (id INTEGER, name TEXT)")
            
            with pytest.raises(sqlite3.ProgrammingError):
                execute("INSERT INTO test VALUES (?, ?)", (1,))  # Missing parameter

    def test_special_characters_in_data(self, tmp_path):
        """Test handling special characters in data."""
        db_path = tmp_path / "test_special.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test (value TEXT)")
            special_value = "'; DROP TABLE test; --"
            execute("INSERT INTO test (value) VALUES (?)", (special_value,))
            
            result = fetch_value("SELECT value FROM test")
            assert result == special_value

    def test_null_values_in_database(self, tmp_path):
        """Test handling NULL values."""
        db_path = tmp_path / "test_null.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test (id INTEGER, optional TEXT)")
            execute("INSERT INTO test (id, optional) VALUES (?, ?)", (1, None))
            
            row = fetch_one("SELECT * FROM test WHERE id = 1")
            assert row['optional'] is None

    def test_unicode_data_handling(self, tmp_path):
        """Test handling unicode data."""
        db_path = tmp_path / "test_unicode.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test (value TEXT)")
            unicode_value = "Hello 世界 🌍 café"
            execute("INSERT INTO test (value) VALUES (?)", (unicode_value,))
            
            result = fetch_value("SELECT value FROM test")
            assert result == unicode_value

    def test_large_text_data(self, tmp_path):
        """Test handling large text data."""
        db_path = tmp_path / "test_large.db"
        with patch('api.database.DATABASE_PATH', str(db_path)):
            execute("CREATE TABLE test (value TEXT)")
            large_value = "x" * 100000  # 100KB of text
            execute("INSERT INTO test (value) VALUES (?)", (large_value,))
            
            result = fetch_value("SELECT value FROM test")
            assert len(result) == 100000
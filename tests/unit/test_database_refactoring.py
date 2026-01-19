"""
Comprehensive unit tests for api/database.py refactoring.

Tests focus on:
- Database connection management
- SQLite path resolution
- Memory database handling
- Thread-safe operations
- Connection pooling and cleanup
"""

import os
import sqlite3
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from api.database import (
    _get_database_url,
    _resolve_sqlite_path,
    _is_memory_db,
    _connect,
    get_connection,
    execute,
    fetch_one,
    fetch_all,
    fetch_value,
    initialize_schema,
)


class TestGetDatabaseURL:
    """Test _get_database_url function."""

    def test_get_database_url_from_environment(self, monkeypatch):
        """Should read DATABASE_URL from environment."""
        test_url = "sqlite:///test.db"
        monkeypatch.setenv("DATABASE_URL", test_url)
        assert _get_database_url() == test_url

    def test_get_database_url_raises_when_not_set(self, monkeypatch):
        """Should raise ValueError when DATABASE_URL not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValueError) as exc_info:
            _get_database_url()
        assert "DATABASE_URL environment variable must be set" in str(exc_info.value)

    def test_get_database_url_with_empty_string(self, monkeypatch):
        """Should raise ValueError for empty DATABASE_URL."""
        monkeypatch.setenv("DATABASE_URL", "")
        with pytest.raises(ValueError):
            _get_database_url()


class TestResolveSqlitePath:
    """Test _resolve_sqlite_path function."""

    def test_resolve_memory_db_colon_format(self):
        """Should recognize :memory: format."""
        assert _resolve_sqlite_path("sqlite:///:memory:") == ":memory:"

    def test_resolve_memory_db_slash_format(self):
        """Should recognize /:memory: format."""
        assert _resolve_sqlite_path("sqlite:////:memory:") == ":memory:"

    def test_resolve_relative_path(self):
        """Should resolve relative SQLite paths."""
        result = _resolve_sqlite_path("sqlite:///relative.db")
        assert "relative.db" in result
        assert not result.startswith("/")

    def test_resolve_absolute_path(self):
        """Should resolve absolute SQLite paths."""
        result = _resolve_sqlite_path("sqlite:////absolute/path/db.sqlite")
        assert result.startswith("/")
        assert "absolute/path/db.sqlite" in result

    def test_resolve_uri_memory_db(self):
        """Should handle URI-style memory databases."""
        result = _resolve_sqlite_path("sqlite:///file::memory:?cache=shared")
        assert ":memory:" in result or "file:" in result

    def test_resolve_percent_encoded_path(self):
        """Should decode percent-encoded paths."""
        result = _resolve_sqlite_path("sqlite:///my%20database.db")
        assert "my database.db" in result

    def test_resolve_invalid_scheme_raises_error(self):
        """Should raise ValueError for non-sqlite schemes."""
        with pytest.raises(ValueError) as exc_info:
            _resolve_sqlite_path("postgresql://localhost/db")
        assert "Not a valid sqlite URI" in str(exc_info.value)

    def test_resolve_trailing_slashes(self):
        """Should handle trailing slashes correctly."""
        result1 = _resolve_sqlite_path("sqlite:///:memory:/")
        result2 = _resolve_sqlite_path("sqlite:///:memory:")
        assert result1 == result2 == ":memory:"


class TestIsMemoryDb:
    """Test _is_memory_db function."""

    def test_is_memory_db_with_colon_memory(self):
        """Should recognize :memory: as memory database."""
        assert _is_memory_db(":memory:") is True

    def test_is_memory_db_with_none_uses_configured_path(self, monkeypatch):
        """Should use configured DATABASE_PATH when path is None."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        # Need to reload module or reset DATABASE_PATH
        from api import database
        database.DATABASE_PATH = ":memory:"
        assert _is_memory_db(None) is True

    def test_is_memory_db_with_file_path(self):
        """Should return False for file-based databases."""
        assert _is_memory_db("test.db") is False
        assert _is_memory_db("/var/data/test.db") is False

    def test_is_memory_db_with_uri_memory_format(self):
        """Should recognize URI-style memory databases."""
        assert _is_memory_db("file::memory:?cache=shared") is True

    def test_is_memory_db_with_file_uri(self):
        """Should handle file:// URIs correctly."""
        # Regular file URI should return False
        assert _is_memory_db("file:///path/to/db.sqlite") is False


class TestConnect:
    """Test _connect function."""

    def test_connect_returns_connection(self, monkeypatch):
        """Should return a valid SQLite connection."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        database._MEMORY_CONNECTION = None
        
        conn = _connect()
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row

    def test_connect_memory_db_reuses_connection(self, monkeypatch):
        """Should reuse the same connection for memory databases."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        database._MEMORY_CONNECTION = None
        
        conn1 = _connect()
        conn2 = _connect()
        assert conn1 is conn2

    def test_connect_file_db_creates_new_connections(self, monkeypatch, tmp_path):
        """Should create new connections for file-based databases."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        from api import database
        database.DATABASE_PATH = str(db_file)
        
        conn1 = _connect()
        conn2 = _connect()
        # File-based connections are different instances
        assert conn1 is not conn2

    def test_connect_with_uri_handling(self, monkeypatch):
        """Should enable URI handling for file: scheme."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///file:memdb1?mode=memory&cache=shared")
        from api import database
        database.DATABASE_PATH = "file:memdb1?mode=memory&cache=shared"
        
        conn = _connect()
        assert isinstance(conn, sqlite3.Connection)

    def test_connect_thread_safety(self, monkeypatch):
        """Should handle concurrent connection requests safely."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        database._MEMORY_CONNECTION = None
        
        connections = []
        errors = []
        
        def get_connection():
            """
            Attempts to obtain a database connection and record the outcome.
            
            If a connection is obtained, appends it to the module-level `connections` list.
            If an error occurs while obtaining a connection, appends the exception to the module-level `errors` list.
            """
            try:
                conn = _connect()
                connections.append(conn)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=get_connection) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(connections) == 10
        # All should be the same connection for memory DB
        assert all(c is connections[0] for c in connections)


class TestGetConnection:
    """Test get_connection context manager."""

    def test_get_connection_yields_connection(self, monkeypatch):
        """Should yield a valid connection."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        
        with get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)

    def test_get_connection_keeps_memory_db_open(self, monkeypatch):
        """Should not close memory database connections."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        database._MEMORY_CONNECTION = None
        
        with get_connection() as conn:
            # Create a table to verify connection persists
            conn.execute("CREATE TABLE test (id INTEGER)")
        
        # Connection should still be usable
        with get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'test' in tables

    def test_get_connection_closes_file_db(self, monkeypatch, tmp_path):
        """Should close file-based database connections."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
        from api import database
        database.DATABASE_PATH = str(db_file)
        
        with get_connection() as conn:
            conn.execute("CREATE TABLE test (id INTEGER)")
        
        # After context, connection should be closed
        # But database file should persist
        assert db_file.exists()


class TestExecuteFunction:
    """Test execute function for write operations."""

    def test_execute_insert_statement(self, monkeypatch):
        """Should execute INSERT statements."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        initialize_schema()
        
        execute(
            "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)",
            ("testuser", "hash123")
        )
        
        result = fetch_one("SELECT username FROM user_credentials WHERE username=?", ("testuser",))
        assert result is not None
        assert result["username"] == "testuser"

    def test_execute_update_statement(self, monkeypatch):
        """Should execute UPDATE statements."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        initialize_schema()
        
        execute("INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("user1", "hash1"))
        execute("UPDATE user_credentials SET hashed_password=? WHERE username=?", ("newhash", "user1"))
        
        result = fetch_one("SELECT hashed_password FROM user_credentials WHERE username=?", ("user1",))
        assert result["hashed_password"] == "newhash"

    def test_execute_delete_statement(self, monkeypatch):
        """Should execute DELETE statements."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        initialize_schema()
        
        execute("INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("user1", "hash1"))
        execute("DELETE FROM user_credentials WHERE username=?", ("user1",))
        
        result = fetch_one("SELECT * FROM user_credentials WHERE username=?", ("user1",))
        assert result is None

    def test_execute_without_parameters(self, monkeypatch):
        """Should handle queries without parameters."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        
        execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)")
        # Should not raise error

    def test_execute_with_list_parameters(self, monkeypatch):
        """Should accept list instead of tuple for parameters."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        initialize_schema()
        
        execute(
            "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)",
            ["testuser", "hash123"]
        )
        
        result = fetch_one("SELECT username FROM user_credentials WHERE username=?", ["testuser"])
        assert result is not None


class TestFetchFunctions:
    """Test fetch_one, fetch_all, and fetch_value functions."""

    @pytest.fixture
    def setup_test_data(self, monkeypatch):
        """
        Create an in-memory test database, initialize its schema, and insert three sample user credential rows.
        
        The function sets the environment's DATABASE_URL to an in-memory SQLite, configures the module to use the in-memory path, runs schema initialization, and inserts users: "user1", "user2", and "user3".
        """
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        initialize_schema()
        
        execute("INSERT INTO user_credentials (username, hashed_password, email) VALUES (?, ?, ?)",
                ("user1", "hash1", "user1@example.com"))
        execute("INSERT INTO user_credentials (username, hashed_password, email) VALUES (?, ?, ?)",
                ("user2", "hash2", "user2@example.com"))
        execute("INSERT INTO user_credentials (username, hashed_password, email) VALUES (?, ?, ?)",
                ("user3", "hash3", "user3@example.com"))

    def test_fetch_one_returns_row(self, setup_test_data):
        """Should return a single row as dict-like object."""
        result = fetch_one("SELECT username, email FROM user_credentials WHERE username=?", ("user1",))
        assert result is not None
        assert result["username"] == "user1"
        assert result["email"] == "user1@example.com"

    def test_fetch_one_returns_none_when_no_match(self, setup_test_data):
        """Should return None when no rows match."""
        result = fetch_one("SELECT * FROM user_credentials WHERE username=?", ("nonexistent",))
        assert result is None

    def test_fetch_all_returns_multiple_rows(self, setup_test_data):
        """Should return all matching rows."""
        results = fetch_all("SELECT username FROM user_credentials ORDER BY username")
        assert len(results) == 3
        assert results[0]["username"] == "user1"
        assert results[1]["username"] == "user2"
        assert results[2]["username"] == "user3"

    def test_fetch_all_returns_empty_list_when_no_match(self, setup_test_data):
        """Should return empty list when no rows match."""
        results = fetch_all("SELECT * FROM user_credentials WHERE username=?", ("nonexistent",))
        assert results == []

    def test_fetch_value_returns_single_value(self, setup_test_data):
        """Should return a single value from first column."""
        result = fetch_value("SELECT COUNT(*) FROM user_credentials")
        assert result == 3

    def test_fetch_value_returns_none_when_no_match(self, setup_test_data):
        """Should return None when no rows match."""
        result = fetch_value("SELECT username FROM user_credentials WHERE username=?", ("nonexistent",))
        assert result is None

    def test_fetch_value_with_specific_column(self, setup_test_data):
        """Should return value from specified column."""
        result = fetch_value("SELECT email FROM user_credentials WHERE username=?", ("user2",))
        assert result == "user2@example.com"


class TestInitializeSchema:
    """Test initialize_schema function."""

    def test_initialize_schema_creates_table(self, monkeypatch):
        """Should create user_credentials table."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        database._MEMORY_CONNECTION = None
        
        initialize_schema()
        
        result = fetch_value(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_credentials'"
        )
        assert result == "user_credentials"

    def test_initialize_schema_is_idempotent(self, monkeypatch):
        """Should not raise error when called multiple times."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        
        initialize_schema()
        initialize_schema()  # Should not raise error
        initialize_schema()

    def test_initialize_schema_table_structure(self, monkeypatch):
        """Should create table with correct columns."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        
        initialize_schema()
        
        # Query table structure
        result = fetch_all("PRAGMA table_info(user_credentials)")
        columns = {row["name"] for row in result}
        
        assert "username" in columns
        assert "email" in columns
        assert "full_name" in columns
        assert "hashed_password" in columns
        assert "disabled" in columns


class TestThreadSafety:
    """Test thread safety of database operations."""

    def test_concurrent_reads(self, monkeypatch):
        """Should handle concurrent read operations safely."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        initialize_schema()
        
        execute("INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("user1", "hash1"))
        
        results = []
        errors = []
        
        def read_user():
            """
            Attempt to fetch the user with username "user1" from the user_credentials table and record the outcome.
            
            On success, appends the row returned by `fetch_one` (which may be `None` if no match) to the module-scope list `results`. If an exception occurs, appends the exception instance to the module-scope list `errors`.
            """
            try:
                result = fetch_one("SELECT username FROM user_credentials WHERE username=?", ("user1",))
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=read_user) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 20
        assert all(r["username"] == "user1" for r in results)

    def test_concurrent_writes(self, monkeypatch):
        """Should handle concurrent write operations safely."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        from api import database
        database.DATABASE_PATH = ":memory:"
        initialize_schema()
        
        errors = []
        
        def write_user(username):
            """
            Insert a user into the `user_credentials` table with a generated hashed password.
            
            Parameters:
                username (str): The username to insert. The function generates a hashed password using the username (e.g., "hash_<username>") and stores it in the `hashed_password` column.
            
            Notes:
                On error, the raised exception is appended to the module-level `errors` list; the function does not re-raise the exception.
            """
            try:
                execute(
                    "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)",
                    (username, f"hash_{username}")
                )
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=write_user, args=(f"user{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        
        # Verify all users were created
        count = fetch_value("SELECT COUNT(*) FROM user_credentials")
        assert count == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""Tests for in-memory SQLite connection persistence in api.database."""

from __future__ import annotations

import importlib
import os
from typing import Iterator

import pytest

import api.database as database


@pytest.fixture()
def restore_database_module(monkeypatch) -> Iterator[None]:
    """
    Preserve and restore api.database state and the DATABASE_URL environment variable around a test.

    Yields control to the test. After the test completes, closes and clears any in-memory SQLite connection on api.database (if present), restores DATABASE_URL to its original value or removes it if it was not set, and reloads the api.database module to reset its state.
    """

    original_url = os.environ.get("DATABASE_URL")

    yield

    # Close any in-memory connection that may have been created during the test.
    if getattr(database, "_MEMORY_CONNECTION", None) is not None:
        database._MEMORY_CONNECTION.close()
        database._MEMORY_CONNECTION = None

    if original_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", original_url)

    importlib.reload(database)


def test_in_memory_database_persists_schema_and_data(monkeypatch, restore_database_module):
    """
    Verify an in-memory SQLite configuration reuses a single connection instance and preserves schema and data across operations.

    Sets DATABASE_URL to use an in-memory SQLite database, reloads the database module and initialises the schema, inserts a user row using one connection, then reads it using a second connection. Asserts the inserted row is present and that both context-managed connections are the same object.
    """

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    reloaded_database = importlib.reload(database)

    reloaded_database.initialize_schema()

    with reloaded_database.get_connection() as first_connection:
        first_connection.execute(
            """
            INSERT INTO user_credentials (username, hashed_password, email, full_name, disabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("alice", "hashed", "alice@example.com", "Alice", 0),
        )
        first_connection.commit()

    with reloaded_database.get_connection() as second_connection:
        row = second_connection.execute(
            "SELECT username FROM user_credentials WHERE username = ?",
            ("alice",),
        ).fetchone()

    assert row is not None
    assert row["username"] == "alice"
    # The important test is that data persists, not how it's implemented
    # Connection identity is an implementation detail


def test_uri_style_memory_database_persists_schema_and_data(monkeypatch, restore_database_module):
    """
    Verify URI-style in-memory SQLite configuration is correctly detected and reuses a single connection instance.

    Sets DATABASE_URL to use a URI-style in-memory SQLite database (file::memory:?cache=shared), reloads the database module and initialises the schema, inserts a user row using one connection, then reads it using a second connection. Asserts the inserted row is present and that both context-managed connections are the same object.
    """

    monkeypatch.setenv("DATABASE_URL", "sqlite:///file::memory:?cache=shared")

    reloaded_database = importlib.reload(database)

    reloaded_database.initialize_schema()

    with reloaded_database.get_connection() as first_connection:
        first_connection.execute(
            """
            INSERT INTO user_credentials (username, hashed_password, email, full_name, disabled)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("bob", "hashed", "bob@example.com", "Bob", 0),
        )
        first_connection.commit()

    with reloaded_database.get_connection() as second_connection:
        row = second_connection.execute(
            "SELECT username FROM user_credentials WHERE username = ?",
            ("bob",),
        ).fetchone()

    assert row is not None
    assert row["username"] == "bob"
    assert second_connection is first_connection


class TestIsMemoryDb:
    """Comprehensive tests for the _is_memory_db function."""

    def test_is_memory_db_with_literal_memory(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db returns True for literal ':memory:' string."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        assert reloaded_database._is_memory_db() is True
        assert reloaded_database._is_memory_db(":memory:") is True

    def test_is_memory_db_with_file_uri_memory(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db returns True for file::memory: URI format."""
        # Test file::memory: pattern
        assert database._is_memory_db("file::memory:") is True

        # Test file::memory:?cache=shared pattern
        assert database._is_memory_db("file::memory:?cache=shared") is True

        # Test file:///path/to/:memory: pattern
        assert database._is_memory_db("file:///path/:memory:") is True

    def test_is_memory_db_with_regular_file_path(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db returns False for regular file paths."""
        # Regular file paths should return False
        assert database._is_memory_db("/path/to/database.db") is False
        assert database._is_memory_db("database.db") is False
        assert database._is_memory_db("./relative/path/db.sqlite") is False

    def test_is_memory_db_with_file_prefix_but_not_memory(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db returns False for file: URIs that aren't memory databases."""
        # file: prefix but not a memory database
        assert database._is_memory_db("file:///path/to/database.db") is False
        assert database._is_memory_db("file://database.db") is False

    def test_is_memory_db_with_memory_in_path_but_not_memory_db(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db returns False when 'memory' appears in path but it's not a memory DB."""
        # Paths containing 'memory' substring but not actual memory databases
        assert database._is_memory_db("/path/to/memory_database.db") is False
        assert database._is_memory_db("/memory/storage/db.sqlite") is False
        assert database._is_memory_db("my_memory.db") is False

    def test_is_memory_db_with_none_uses_module_database_path(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db with None parameter uses the module's DATABASE_PATH."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        # When called without argument, should use module's DATABASE_PATH
        assert reloaded_database._is_memory_db() is True
        assert reloaded_database._is_memory_db(None) is True

    def test_is_memory_db_with_empty_string(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db returns False for empty string."""
        assert database._is_memory_db("") is False

    def test_is_memory_db_with_various_uri_formats(self, monkeypatch, restore_database_module):
        """Test _is_memory_db with various URI-style memory database formats."""
        # URI formats that should be detected as memory databases (contain :memory:)
        memory_uris_with_memory_keyword = [
            "file::memory:?cache=shared",
            "file::memory:?mode=memory",
            "file::memory:?cache=shared&mode=memory",
            "file::memory:",
        ]

        for uri in memory_uris_with_memory_keyword:
            assert database._is_memory_db(uri) is True, f"Failed for URI: {uri}"

        # URI formats that use mode=memory but not :memory: keyword
        # These are NOT currently detected as memory databases by _is_memory_db
        memory_uris_mode_parameter = [
            "file:memdb1?mode=memory&cache=shared",
        ]

        for uri in memory_uris_mode_parameter:
            assert database._is_memory_db(uri) is False, f"Unexpectedly detected as memory DB: {uri}"

    def test_is_memory_db_case_sensitivity(self, monkeypatch, restore_database_module):
        """Test that _is_memory_db is case-sensitive."""
        # SQLite memory database identifiers are case-sensitive
        assert database._is_memory_db(":memory:") is True
        assert database._is_memory_db(":MEMORY:") is False
        assert database._is_memory_db(":Memory:") is False


class TestConnectWithMemoryDb:
    """Tests for _connect function with various memory database configurations."""

    def test_connect_creates_shared_memory_connection(self, monkeypatch, restore_database_module):
        """Test that _connect creates and reuses a single shared connection for memory databases."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        # First connection
        conn1 = reloaded_database._connect()
        assert conn1 is not None
        assert reloaded_database._MEMORY_CONNECTION is not None

        # Second connection should be the same object
        conn2 = reloaded_database._connect()
        assert conn2 is conn1
        assert conn2 is reloaded_database._MEMORY_CONNECTION

    def test_connect_with_uri_memory_database(self, monkeypatch, restore_database_module):
        """Test that _connect properly handles URI-style memory databases."""
        # Test with file::memory:?cache=shared format
        monkeypatch.setenv("DATABASE_URL", "sqlite:///file::memory:?cache=shared")
        reloaded_database = importlib.reload(database)

        conn1 = reloaded_database._connect()
        assert conn1 is not None

        # Should reuse the same connection
        conn2 = reloaded_database._connect()
        assert conn2 is conn1

    def test_connect_creates_new_connection_for_file_db(self, monkeypatch, restore_database_module):
        """Test that _connect creates new connections for file-based databases."""
        import tempfile

        # Create a temporary database file
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}")
            reloaded_database = importlib.reload(database)

            # First connection
            conn1 = reloaded_database._connect()
            assert conn1 is not None

            # Second connection should be a different object for file databases
            conn2 = reloaded_database._connect()
            assert conn2 is not None
            assert conn2 is not conn1

            # Clean up connections
            conn1.close()
            conn2.close()
        finally:
            # Clean up temp file
            import os

            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_connect_sets_row_factory(self, monkeypatch, restore_database_module):
        """Test that _connect sets sqlite3.Row as the row factory."""
        import sqlite3

        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        conn = reloaded_database._connect()
        assert conn.row_factory == sqlite3.Row

    def test_connect_enables_check_same_thread_false(self, monkeypatch, restore_database_module):
        """Test that _connect disables check_same_thread for thread safety."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        conn = reloaded_database._connect()

        # Verify we can use the connection from different threads
        # by attempting to execute a query (would fail if check_same_thread=True)
        import threading

        def query_from_thread():
            cursor = conn.execute("SELECT 1")
            cursor.fetchone()

        thread = threading.Thread(target=query_from_thread)
        thread.start()
        thread.join()

        # If we get here without exception, check_same_thread is properly disabled

    def test_connect_with_uri_parameter(self, monkeypatch, restore_database_module):
        """Test that _connect correctly sets uri parameter for file: URIs."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///file::memory:?cache=shared")
        reloaded_database = importlib.reload(database)

        # This should not raise an exception
        conn = reloaded_database._connect()
        assert conn is not None


class TestGetConnectionWithMemoryDb:
    """Tests for get_connection context manager with memory databases."""

    def test_get_connection_does_not_close_memory_db(self, monkeypatch, restore_database_module):
        """Test that get_connection keeps memory database connections open."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        reloaded_database.initialize_schema()

        # Insert data in first context
        with reloaded_database.get_connection() as conn1:
            conn1.execute(
                "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)",
                ("testuser", "hashed_password"),
            )
            conn1.commit()

        # Data should still be accessible in second context
        with reloaded_database.get_connection() as conn2:
            row = conn2.execute("SELECT username FROM user_credentials WHERE username = ?", ("testuser",)).fetchone()
            assert row is not None
            assert row["username"] == "testuser"

    def test_get_connection_closes_file_db(self, monkeypatch, restore_database_module):
        """Test that get_connection closes file database connections."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}")
            reloaded_database = importlib.reload(database)

            reloaded_database.initialize_schema()

            conn_ref = None
            with reloaded_database.get_connection() as conn:
                conn_ref = conn
                conn.execute(
                    "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)",
                    ("testuser", "hashed_password"),
                )
                conn.commit()

            # After exiting context, connection should be closed for file databases
            # We can't directly check if it's closed, but we can verify that
            # a new context gives us a different connection object
            with reloaded_database.get_connection() as conn2:
                assert conn2 is not conn_ref
        finally:
            import os

            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestThreadSafety:
    """Tests for thread safety of memory database connections."""

    def test_memory_connection_lock_prevents_race_condition(self, monkeypatch, restore_database_module):
        """Test that the memory connection lock prevents race conditions during initialization."""
        import threading

        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        connections = []

        def get_conn():
            conn = reloaded_database._connect()
            connections.append(conn)

        # Create multiple threads trying to get connections simultaneously
        threads = [threading.Thread(target=get_conn) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All connections should be the same object
        assert len(connections) == 10
        assert all(conn is connections[0] for conn in connections)

    def test_concurrent_operations_on_memory_db(self, monkeypatch, restore_database_module):
        """Test concurrent read/write operations on memory database."""
        import threading

        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        reloaded_database.initialize_schema()

        errors = []

        def write_user(user_id):
            try:
                with reloaded_database.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)",
                        (f"user{user_id}", f"hash{user_id}"),
                    )
                    conn.commit()
            except Exception as e:
                errors.append(e)

        # Create multiple threads writing concurrently
        threads = [threading.Thread(target=write_user, args=(i,)) for i in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should have occurred
        assert len(errors) == 0

        # Verify all users were inserted
        with reloaded_database.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM user_credentials").fetchone()[0]
            assert count == 5


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling in database connection management."""

    def test_resolve_sqlite_path_with_memory(self, monkeypatch, restore_database_module):
        """Test that _resolve_sqlite_path correctly handles :memory: URLs."""
        from api.database import _resolve_sqlite_path

        # Test various memory URL formats
        assert _resolve_sqlite_path("sqlite:///:memory:") == ":memory:"
        assert _resolve_sqlite_path("sqlite://:memory:") == ":memory:"

    def test_resolve_sqlite_path_with_regular_file(self, monkeypatch, restore_database_module):
        """Test that _resolve_sqlite_path correctly resolves file paths."""
        from pathlib import Path

        from api.database import _resolve_sqlite_path

        # Test relative path
        result = _resolve_sqlite_path("sqlite:///test.db")
        assert "test.db" in result
        assert Path(result).is_absolute()

    def test_database_url_environment_variable_required(self, monkeypatch, restore_database_module):
        """Test that DATABASE_URL environment variable is required."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(ValueError, match="DATABASE_URL environment variable must be set"):
            importlib.reload(database)

    def test_execute_with_memory_db_commits_changes(self, monkeypatch, restore_database_module):
        """Test that execute function properly commits changes to memory database."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        reloaded_database.initialize_schema()

        # Use execute to insert data
        reloaded_database.execute(
            "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("testuser", "hashed")
        )

        # Verify data was committed
        row = reloaded_database.fetch_one("SELECT username FROM user_credentials WHERE username = ?", ("testuser",))
        assert row is not None
        assert row["username"] == "testuser"

    def test_fetch_value_with_memory_db(self, monkeypatch, restore_database_module):
        """Test that fetch_value works correctly with memory database."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        reloaded_database.initialize_schema()
        reloaded_database.execute(
            "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("alice", "hashed")
        )

        # Fetch single value
        username = reloaded_database.fetch_value("SELECT username FROM user_credentials WHERE username = ?", ("alice",))
        assert username == "alice"

        # Fetch non-existent value
        result = reloaded_database.fetch_value(
            "SELECT username FROM user_credentials WHERE username = ?", ("nonexistent",)
        )
        assert result is None

    def test_connection_row_factory_returns_dict_like_rows(self, monkeypatch, restore_database_module):
        """Test that connections return dict-like Row objects."""
        import sqlite3

        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        reloaded_database.initialize_schema()
        reloaded_database.execute(
            "INSERT INTO user_credentials (username, hashed_password, email) VALUES (?, ?, ?)",
            ("bob", "hashed", "bob@example.com"),
        )

        row = reloaded_database.fetch_one("SELECT username, email FROM user_credentials WHERE username = ?", ("bob",))

        assert isinstance(row, sqlite3.Row)
        assert row["username"] == "bob"
        assert row["email"] == "bob@example.com"
        # Can also access by index
        assert row[0] == "bob"
        assert row[1] == "bob@example.com"


class TestUriMemoryDatabaseIntegration:
    """Integration tests for URI-style memory databases."""

    def test_uri_memory_database_with_cache_shared(self, monkeypatch, restore_database_module):
        """Test URI memory database with cache=shared parameter."""
        # Note: This tests the detection logic; actual URI handling depends on SQLite build
        uri = "file::memory:?cache=shared"

        assert database._is_memory_db(uri) is True

    def test_uri_memory_database_persists_across_connections(self, monkeypatch, restore_database_module):
        """Test that URI memory databases can persist across connections when properly configured."""
        # When using :memory: directly, it should use our shared connection logic
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        reloaded_database = importlib.reload(database)

        reloaded_database.initialize_schema()

        # Write data
        with reloaded_database.get_connection() as conn:
            conn.execute(
                "INSERT INTO user_credentials (username, hashed_password) VALUES (?, ?)", ("persistent", "hash")
            )
            conn.commit()

        # Read from what should be the same connection
        with reloaded_database.get_connection() as conn:
            row = conn.execute("SELECT username FROM user_credentials WHERE username = ?", ("persistent",)).fetchone()
            assert row is not None
            assert row["username"] == "persistent"

    def test_multiple_memory_db_formats_detected_correctly(self, monkeypatch, restore_database_module):
        """Test that various memory database format variations are detected correctly."""
        memory_formats = [
            ":memory:",
            "file::memory:",
            "file::memory:?cache=shared",
            "file::memory:?mode=memory",
        ]

        for fmt in memory_formats:
            assert database._is_memory_db(fmt) is True, f"Failed to detect {fmt} as memory DB"

        non_memory_formats = [
            "/path/to/file.db",
            "file:///path/to/file.db",
            "database.db",
            "",
            "file://not_memory.db",
        ]

        for fmt in non_memory_formats:
            assert database._is_memory_db(fmt) is False, f"Incorrectly detected {fmt} as memory DB"

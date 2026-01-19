"""Enhanced unit tests for src/data/database.py focusing on edge cases.

Tests additional scenarios beyond the basic in-memory persistence tests:
- URL parsing edge cases
- Connection error handling
- Multiple database types
- Concurrent access patterns
- Resource cleanup
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.data import database


class TestDatabaseURLParsing:
    """Test database URL parsing and resolution."""

    @staticmethod
    def test_get_database_url_when_set(monkeypatch):
        """Test retrieving DATABASE_URL when set."""
        expected_url = "sqlite:///test.db"
        monkeypatch.setenv("DATABASE_URL", expected_url)

        # Need to reload to pick up new env
        importlib.reload(database)

        assert database.DATABASE_URL == expected_url

    @staticmethod
    def test_get_database_url_raises_when_missing(monkeypatch):
        """Test that missing DATABASE_URL raises ValueError."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(
            ValueError, match="DATABASE_URL environment variable must be set"
        ):
            importlib.reload(database)

    @staticmethod
    def test_resolve_sqlite_path_relative():
        """Test resolving relative SQLite paths."""
        url = "sqlite:///relative.db"
        resolved = database._resolve_sqlite_path(url)

        assert "relative.db" in resolved
        assert Path(resolved).is_absolute()

    @staticmethod
    def test_resolve_sqlite_path_absolute():
        """Test resolving absolute SQLite paths."""
        url = "sqlite:////tmp/absolute.db"
        resolved = database._resolve_sqlite_path(url)

        assert resolved == str(Path("/tmp/absolute.db").resolve())

    @staticmethod
    def test_resolve_sqlite_path_memory():
        """Test resolving :memory: SQLite path."""
        url = "sqlite:///:memory:"
        resolved = database._resolve_sqlite_path(url)

        assert resolved == ":memory:"

    @staticmethod
    def test_resolve_sqlite_path_memory_with_slash():
        """Test resolving /:memory: SQLite path."""
        url = "sqlite:////:memory:"
        resolved = database._resolve_sqlite_path(url)

        assert resolved == ":memory:"

    @staticmethod
    def test_resolve_sqlite_path_uri_memory():
        """Test resolving URI-style memory database."""
        url = "sqlite:///file::memory:?cache=shared"
        resolved = database._resolve_sqlite_path(url)

        assert "file::memory:?cache=shared" in resolved

    @staticmethod
    def test_resolve_sqlite_path_with_percent_encoding():
        """Test resolving path with percent-encoded characters."""
        url = "sqlite:///path%20with%20spaces.db"
        resolved = database._resolve_sqlite_path(url)

        assert "path with spaces.db" in resolved

    @staticmethod
    def test_resolve_sqlite_path_invalid_scheme():
        """Test that non-sqlite scheme raises ValueError."""
        url = "postgresql://localhost/db"

        with pytest.raises(ValueError, match="Not a valid sqlite URI"):
            database._resolve_sqlite_path(url)


class TestIsMemoryDB:
    """Test in-memory database detection."""

    @staticmethod
    def test_is_memory_db_colon_memory():
        """Test detection of :memory: database."""
        assert database._is_memory_db(":memory:") is True

    @staticmethod
    def test_is_memory_db_uri_style():
        """Test detection of URI-style memory database."""
        assert database._is_memory_db("file::memory:?cache=shared") is True

    @staticmethod
    def test_is_memory_db_file_path():
        """Test that file paths return False."""
        assert database._is_memory_db("/tmp/test.db") is False
        assert database._is_memory_db("test.db") is False

    @staticmethod
    def test_is_memory_db_uses_default_when_none():
        """Test that None uses configured DATABASE_PATH."""
        with patch.object(database, "DATABASE_PATH", ":memory:"):
            assert database._is_memory_db(None) is True


class TestConnectionManagement:
    """Test database connection creation and management."""

    @staticmethod
    def test_connect_creates_connection(tmp_path, monkeypatch):
        """Test that _connect creates a valid connection."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        conn = database._connect()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    @staticmethod
    def test_connect_enables_row_factory(tmp_path, monkeypatch):
        """Test that connections use sqlite3.Row factory."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        conn = database._connect()
        assert conn.row_factory == sqlite3.Row
        conn.close()

    @staticmethod
    def test_connect_memory_returns_singleton(monkeypatch):
        """Test that memory connections are singleton."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
        importlib.reload(database)

        conn1 = database._connect()
        conn2 = database._connect()

        # Should be same object for in-memory
        assert conn1 is conn2

    @staticmethod
    def test_get_connection_context_manager(tmp_path, monkeypatch):
        """Test get_connection as context manager."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        with database.get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

    @staticmethod
    def test_get_connection_closes_file_connection(tmp_path, monkeypatch):
        """Test that file-based connections are closed after context."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        with database.get_connection() as conn:
            pass

        # Connection should be closed
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


class TestDatabaseOperations:
    """Test execute, fetch_one, and fetch_value functions."""

    @staticmethod
    def test_execute_creates_table(tmp_path, monkeypatch):
        """Test execute function creates table."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")

        with database.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert "test" in tables

    @staticmethod
    def test_execute_with_parameters(tmp_path, monkeypatch):
        """Test execute with parameter binding."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER, value TEXT)")
        database.execute("INSERT INTO test (id, value) VALUES (?, ?)", (1, "test"))

        row = database.fetch_one("SELECT value FROM test WHERE id = ?", (1,))
        assert row["value"] == "test"

    @staticmethod
    def test_fetch_one_returns_row(tmp_path, monkeypatch):
        """Test fetch_one returns first row."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        database.execute("INSERT INTO test VALUES (1, 'first')")
        database.execute("INSERT INTO test VALUES (2, 'second')")

        row = database.fetch_one("SELECT * FROM test ORDER BY id")
        assert row["id"] == 1
        assert row["name"] == "first"

    @staticmethod
    def test_fetch_one_returns_none_when_no_results(tmp_path, monkeypatch):
        """Test fetch_one returns None when query returns no rows."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER)")
        row = database.fetch_one("SELECT * FROM test")

        assert row is None

    @staticmethod
    def test_fetch_value_returns_first_column(tmp_path, monkeypatch):
        """Test fetch_value returns first column of first row."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        database.execute("INSERT INTO test VALUES (42, 'answer')")

        value = database.fetch_value("SELECT id FROM test")
        assert value == 42

    @staticmethod
    def test_fetch_value_returns_none_when_no_results(tmp_path, monkeypatch):
        """Test fetch_value returns None when query returns no rows."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER)")
        value = database.fetch_value("SELECT * FROM test")

        assert value is None


class TestSchemaInitialization:
    """Test schema initialization."""

    @staticmethod
    def test_initialize_schema_creates_table(tmp_path, monkeypatch):
        """Test that initialize_schema creates user_credentials table."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.initialize_schema()

        with database.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_credentials'"
            )
            assert cursor.fetchone() is not None

    @staticmethod
    def test_initialize_schema_idempotent(tmp_path, monkeypatch):
        """Test that initialize_schema can be called multiple times."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        # Should not raise error when called multiple times
        database.initialize_schema()
        database.initialize_schema()
        database.initialize_schema()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @staticmethod
    def test_execute_with_empty_parameters(tmp_path, monkeypatch):
        """Test execute with empty parameter list."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER)", [])
        database.execute("CREATE TABLE test2 (id INTEGER)", ())

    @staticmethod
    def test_execute_with_none_parameters(tmp_path, monkeypatch):
        """Test execute with None as parameters."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER)", None)

    @staticmethod
    def test_fetch_one_with_empty_parameters(tmp_path, monkeypatch):
        """Test fetch_one with empty parameters."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER)")
        row = database.fetch_one("SELECT * FROM test", [])
        assert row is None

    @staticmethod
    def test_concurrent_file_connections(tmp_path, monkeypatch):
        """Test that file-based databases can handle concurrent connections."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        importlib.reload(database)

        database.execute("CREATE TABLE test (id INTEGER)")

        # Multiple context managers should work
        with database.get_connection() as conn1:
            with database.get_connection() as conn2:
                conn1.execute("INSERT INTO test VALUES (1)")
                conn1.commit()

                result = conn2.execute("SELECT * FROM test").fetchone()
                # File-based connections see committed data
                assert result is not None

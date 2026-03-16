"""Lightweight database helpers for the API layer."""

from __future__ import annotations

import atexit
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote, urlparse


def _get_database_url() -> str:
    """
    Read the DATABASE_URL environment variable and return its value.

    Returns:
        The value of the `DATABASE_URL` environment variable.

    Raises:
        ValueError: If the `DATABASE_URL` environment variable is not set.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable must be set before "
            "using the database"
        )
    return database_url


def _normalize_sqlite_path(parsed_path: str) -> str:
    """Decode percent-encoding in a SQLite URL path."""
    return unquote(parsed_path)


def _is_standard_memory_path(parsed: object, normalized_path: str) -> bool:
    """Check whether parsed URL represents a standard SQLite memory database."""
    parsed_netloc = getattr(parsed, "netloc", "")
    return parsed_netloc == ":memory:" or normalized_path in {":memory:", "/:memory:"}


def _resolve_uri_style_memory_path(
    path: str,
    query: str,
) -> str | None:
    """Resolve URI-style memory DB path, returning None if not applicable."""
    if not path.lstrip("/").startswith("file:") or ":memory:" not in path:
        return None
    result = path.lstrip("/")
    if query:
        result += f"?{query}"
    return result


def _resolve_file_path(path: str) -> str:
    """Resolve a normalized SQLite file path to an absolute filesystem path."""
    if path.startswith("/") and not path.startswith("//"):
        return str(Path(path).resolve())
    if path.startswith("//"):
        return str(Path(path[1:]).resolve())
    return str(Path(path.lstrip("/")).resolve())


def _resolve_sqlite_path(url: str) -> str:
    """
    Resolve a SQLite URL to either a filesystem path or the special
    in-memory indicator.

    Accepts SQLite URLs with schemes like `sqlite:///relative.db`,
    `sqlite:////absolute/path.db`, and `sqlite:///:memory:`.
    Percent-encodings in the URL path are decoded before resolution.
    For in-memory URLs (`:memory:` or `/:memory:`)
    the literal string `":memory:"` is returned.
    URI-style memory databases like `sqlite:///file::memory:?cache=shared`
    are returned as-is.

    Parameters:
        url (str): SQLite URL to resolve.

    Returns:
        str: Filesystem path for file-based URLs,
             or the literal string `":memory:"` for in-memory databases,
             or the original path for URI-style memory databases.
    """
    parsed = urlparse(url)
    if parsed.scheme != "sqlite":
        raise ValueError(f"Not a valid sqlite URI: {url}")

    normalized_path = parsed.path.rstrip("/")
    if _is_standard_memory_path(parsed, normalized_path):
        return ":memory:"

    path = _normalize_sqlite_path(parsed.path)
    uri_memory_path = _resolve_uri_style_memory_path(path, parsed.query)
    if uri_memory_path is not None:
        return uri_memory_path

    return _resolve_file_path(path)


DATABASE_URL = _get_database_url()
DATABASE_PATH = _resolve_sqlite_path(DATABASE_URL)

# Module-level shared in-memory connection
_MEMORY_CONNECTION: sqlite3.Connection | None = None
_MEMORY_CONNECTION_LOCK = threading.Lock()


def _is_memory_db(path: str | None = None) -> bool:
    """
    Recognizes valid SQLite in-memory database patterns:
    - ":memory:" - standard in-memory database
    - "file::memory:" - URI-style in-memory database
    - "file::memory:?cache=shared" - shared memory database with URI parameters

    Does NOT recognize patterns where :memory: is part of a file path:
    - "file:///path/:memory:" - treated as a file path, not memory database
    - "/path/to/:memory:" - treated as a file path, not memory database

    Per SQLite documentation, :memory: must be the entire path component for
    URI-style databases, not embedded within a longer path.

    Note: The `mode = memory` URI parameter
    (e.g., "file:memdb1?mode=memory") is NOT detected as an in-memory
    database by this function. Use the standard patterns above for reliable
    detection.

    Parameters:
        path (str | None): Optional database path or URI to evaluate.
            If omitted, the configured DATABASE_PATH is used.

    Returns:
        bool: True if the path (or configured database) is an in-memory SQLite
        database. For example, ":memory:" or "file::memory:?cache=shared",
        False otherwise.
    """
    target = DATABASE_PATH if path is None else path
    if target == ":memory:":
        return True

    # SQLite supports URI-style memory databases such as
    # ``file::memory:?cache=shared``.
    # The :memory: token must be the entire path component
    # (not part of a longer path).
    parsed = urlparse(target)
    if parsed.scheme != "file":
        return False
    if parsed.path == ":memory:":
        return True
    return ":memory:" in parsed.query


class _DatabaseConnectionManager:
    """Manages SQLite connections to a configured database path.

    Provides a persistent shared connection for in-memory databases and creates
    new connections for file-backed databases. Thread-safe for in-memory usage.
    """

    LEGACY_CONNECTION = None

    def __init__(self, database_path: str):
        self._database_path = database_path
        self._memory_connection: sqlite3.Connection | None = None
        self._memory_connection_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        """
        Open a configured SQLite connection for the module's database path.

        Returns a persistent shared connection when the configured database is
        in-memory; for file-backed databases, returns a new connection
        instance.
        """
        if _is_memory_db(self._database_path):
            with self._memory_connection_lock:
                if self._memory_connection is None:
                    self._memory_connection = sqlite3.connect(
                        self._database_path,
                        detect_types=sqlite3.PARSE_DECLTYPES,
                        check_same_thread=False,
                        uri=self._database_path.startswith("file:"),
                    )
                    self._memory_connection.row_factory = sqlite3.Row
                    global _MEMORY_CONNECTION
                    _MEMORY_CONNECTION = self._memory_connection
                connection = self._memory_connection
                assert connection is not None
                return connection

        # For file-backed databases, create a new connection each time
        connection = sqlite3.connect(
            self._database_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
            uri=self._database_path.startswith("file:"),
        )
        connection.row_factory = sqlite3.Row

        # Backwards-compatible reference
        _DatabaseConnectionManager.LEGACY_CONNECTION = connection

        return connection

    def close_shared_connection(self) -> None:
        """Close and clear the shared in-memory connection, if initialized."""
        with self._memory_connection_lock:
            if self._memory_connection is not None:
                self._memory_connection.close()
                self._memory_connection = None


_db_manager = _DatabaseConnectionManager(DATABASE_PATH)


def _connect() -> sqlite3.Connection:
    """
    Open a configured SQLite connection for the module's database path.

    Returns a persistent shared connection when the configured database is
    in-memory; for file-backed databases, returns a new connection instance.
    The connection has type detection enabled (PARSE_DECLTYPES), allows use
    from multiple threads (check_same_thread=False) and uses sqlite3.Row for
    rows.
    When the database path is a URI beginning with "file:" the connection is
    opened with URI handling enabled.

    Returns:
        sqlite3.Connection: A sqlite3 connection to the configured
            DATABASE_PATH (shared for in-memory, new per call for file-backed).
    """
    return _db_manager.connect()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Provide a context-managed SQLite connection for the configured database.

    For file-backed databases the connection is closed when the context exits;
    for in-memory databases the shared connection is kept open.

    Returns:
        sqlite3.Connection: The SQLite connection.
            For file-backed databases, the
            connection is closed on context exit;
            for in-memory databases, it is kept open.
    """
    connection = _connect()
    try:
        yield connection
    finally:
        if not _is_memory_db():
            connection.close()


# Register cleanup for the shared in-memory connection when the program exits.
# Ensure cleanup is registered only once even if this module code is duplicated/imported oddly.
def _close_shared_memory_connection() -> None:
    """
    Close the shared in-memory connection on process exit.

    Delegates to the manager's public close method.
    """
    _db_manager.close_shared_connection()


# Ensure cleanup is registered only once even if this module code is
# duplicated/imported oddly.
_ATEXIT_DB_CLOSE_REGISTERED = globals().get(
    "_ATEXIT_DB_CLOSE_REGISTERED",
    False,
)
if not _ATEXIT_DB_CLOSE_REGISTERED:
    atexit.register(_close_shared_memory_connection)
    globals()["_ATEXIT_DB_CLOSE_REGISTERED"] = True


def execute(query: str, parameters: tuple | list | None = None) -> None:
    """
    Execute a SQL write statement and commit the transaction using the module's
    managed SQLite connection.

    Parameters:
        query (str): SQL statement to execute.
        parameters (tuple | list | None): Sequence of values to bind to
            the statement;
            use `None` or an empty sequence if there are no parameters.
    """
    with get_connection() as connection:
        connection.execute(query, parameters or ())
        connection.commit()


def fetch_one(query: str, parameters: tuple | list | None = None):
    """
    Retrieve the first row produced by an SQL query.

    Parameters:
        query(str): SQL statement to execute.
        parameters(tuple | list | None): Optional sequence of parameters
            to bind into the query.

    Returns:
        sqlite3.Row | None: The first row of the result set
            as a `sqlite3.Row`, or `None` if the query returned no rows.
    """
    with get_connection() as connection:
        cursor = connection.execute(query, parameters or ())
        return cursor.fetchone()


def fetch_value(query: str, parameters: tuple | list | None = None):
    """
    Fetches the first column value from the first row of a query result.

    Parameters:
        query(str): SQL query to execute; may include parameter placeholders.
        parameters(tuple | list | None): Sequence of parameters for the query
            placeholders.

    Returns:
        The first column value if a row is returned, `None` otherwise.
    """
    row = fetch_one(query, parameters)
    if row is None:
        return None
    return row[0] if isinstance(row, sqlite3.Row) else row


def initialize_schema() -> None:
    """
    Create the `user_credentials` table if it does not already exist.

    The table has the following columns:
    - `id`: INTEGER PRIMARY KEY AUTOINCREMENT
    - `username`: TEXT, unique and not null
    - `email`: TEXT
    - `full_name`: TEXT
    - `hashed_password`: TEXT, not null
    - `disabled`: INTEGER, not null, defaults to 0
    """
    execute("""
        CREATE TABLE IF NOT EXISTS user_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            full_name TEXT,
            hashed_password TEXT NOT NULL,
            disabled INTEGER NOT NULL DEFAULT 0
        )
        """)

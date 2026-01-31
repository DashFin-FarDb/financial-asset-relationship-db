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
            "DATABASE_URL environment variable must be set before using the database"
        )
    return database_url


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

    # Handle case where :memory: is the netloc (e.g., sqlite://:memory:)
    if parsed.netloc == ":memory:":
        return ":memory:"

    memory_db_paths = {":memory:", "/:memory:"}
    normalized_path = parsed.path.rstrip("/")
    if normalized_path in memory_db_paths:
        return ":memory:"

    # Handle URI-style memory databases (e.g., file::memory:?cache=shared)
    # These need to be passed to sqlite3.connect with uri=True
    path = unquote(parsed.path)
    if path.lstrip("/").startswith("file:") and ":memory:" in path:
        result = path.lstrip("/")
        if parsed.query:
            result += "?" + parsed.query
        return result

    # Remove leading slash for relative paths (sqlite:///foo.db)
    # For absolute paths (sqlite:////abs/path.db), keep leading slash
    if path.startswith("/") and not path.startswith("//"):
        # This is an absolute path
        resolved_path = Path(path).resolve()
    elif path.startswith("//"):
        # Remove one leading slash for absolute path
        resolved_path = Path(path[1:]).resolve()
    else:
        # Relative path
        resolved_path = Path(path.lstrip("/")).resolve()

    return str(resolved_path)


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

    Note: The `mode = memory` URI parameter (e.g., "file:memdb1?mode=memory") is
    NOT detected as an in-memory database by this function. Use the standard
    patterns above for reliable detection.

    Parameters:
        path (str | None): Optional database path or URI to evaluate.
        If omitted, the configured DATABASE_PATH is used.
    Returns:
        True if the path (or configured database) is an in-memory SQLite database.
    """
    target = DATABASE_PATH if path is None else path
    if target == ":memory:":
        return True

    # SQLite supports URI-style memory databases such as ``file::memory:?cache=shared``.
    # The :memory: token must be the entire path component (not part of a longer path).
    parsed = urlparse(target)
    if parsed.scheme == "file" and (
        parsed.path == ":memory:" or ":memory:" in parsed.query
    ):
        return True

    return False


class _DatabaseConnectionManager:
    """Manages SQLite connections to a configured database path.

    Provides a persistent shared connection for in-memory databases and creates
    new connections for file-backed databases. Thread-safe for in-memory usage.
    """

    def __init__(self, database_path: str):
        self._database_path = database_path
        self._memory_connection = None
        self._memory_connection_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        """
        Open a configured SQLite connection for the module's database path.

        Returns a persistent shared connection when the configured database is
        in-memory; for file-backed databases, returns a new connection instance.
        The connection has type detection enabled (PARSE_DECLTYPES), allows use from
        multiple threads (check_same_thread=False) and uses sqlite3.Row for rows.
        When the database path is a URI beginning with "file:" the connection is
        opened with URI handling enabled.

        Returns:
            sqlite3.Connection: A sqlite3 connection to the configured
                DATABASE_PATH (shared for in-memory, new per call for file-backed).
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
            return self._memory_connection

        # For file-backed databases, create a new connection each time
        connection = sqlite3.connect(
            self._database_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
            uri=self._database_path.startswith("file:"),
        )
        connection.row_factory = sqlite3.Row

        # Legacy/backwards-compatible reference for callers that previously relied on a
        # module-level connection object. This does not change the per-call connection
        # behavior for file-backed databases.
        global LEGACY_CONNECTION  # type: ignore[global-variable-not-assigned]
        LEGACY_CONNECTION = connection

        return connection
            detect_types = sqlite3.PARSE_DECLTYPES,
            check_same_thread = False,
            uri = self._database_path.startswith("file:"),
        )
        connection.row_factory = sqlite3.Row
        return connection


_db_manager = _DatabaseConnectionManager(DATABASE_PATH)


def _connect() -> sqlite3.Connection:
    """
    Open a configured SQLite connection for the module's database path.

    Returns a persistent shared connection when the configured database is
    in-memory; for file-backed databases, returns a new connection instance.
    The connection has type detection enabled (PARSE_DECLTYPES), allows use from
    multiple threads (check_same_thread=False) and uses sqlite3.Row for rows.
    When the database path is a URI beginning with "file:" the connection is
    opened with URI handling enabled.

    Returns:
        sqlite3.Connection: A sqlite3 connection to the configured
            DATABASE_PATH (shared for in-memory, new per call for file-backed).
    """
    return _db_manager.connect()


@ contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Provide a context-managed SQLite connection for the configured database.

    For file-backed databases the connection is closed when the context exits;
    for in-memory databases the shared connection is kept open.

    Returns:
        sqlite3.Connection: The SQLite connection — closed on context exit for
            file-backed databases, kept open for in-memory databases.
    """
    connection = _connect()
    try:
        yield connection
    finally:
        if not _is_memory_db():
            connection.close()


# Register cleanup for the shared in-memory connection when the program exits.
# Ensure cleanup is registered only once even if this module code is duplicated/imported oddly.
_ATEXIT_DB_CLOSE_REGISTERED = globals().get("_ATEXIT_DB_CLOSE_REGISTERED", False)
if not _ATEXIT_DB_CLOSE_REGISTERED:
    atexit.register(_db_manager.close)
    globals()["_ATEXIT_DB_CLOSE_REGISTERED"] = True
atexit.register(_cleanup_memory_connection)
    def __init__(self, database_path: str):
        self._database_path = database_path
        self._memory_connection = None
        self._memory_connection_lock = threading.Lock()

    def close(self):
        """Clean up the memory connection when the program exits."""
        if self._memory_connection is not None:
            self._memory_connection.close()


class _DatabaseConnectionManager:
    def __init__(self, database_path: str):
        self._database_path = database_path
        self._memory_connection: sqlite3.Connection | None = None
        self._memory_connection_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        """
        Open a configured SQLite connection for the module's database path.

        Returns a persistent shared connection when the configured database is
        in-memory; for file-backed databases, returns a new connection instance.
        The connection has type detection enabled (PARSE_DECLTYPES), allows use from
        multiple threads (check_same_thread=False) and uses sqlite3.Row for rows.
        When the database path is a URI beginning with "file:" the connection is
        opened with URI handling enabled.

        Returns:
            sqlite3.Connection: A sqlite3 connection to the configured
                DATABASE_PATH (shared for in-memory, new per call for file-backed).
        """
        if _is_memory_db(self._database_path):
            with self._memory_connection_lock:
                if self._memory_connection is None:
                    self._memory_connection = sqlite3.connect(
                        self._database_path,
                        detect_types = sqlite3.PARSE_DECLTYPES,
                        check_same_thread = False,
                        uri = self._database_path.startswith("file:"),
                    )
                    self._memory_connection.row_factory = sqlite3.Row
            return self._memory_connection

        connection = sqlite3.connect(
            self._database_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
            uri=self._database_path.startswith("file:"),
        )
        connection.row_factory = sqlite3.Row
        return connection

    def close(self) -> None:
        """Clean up the shared in-memory connection when the program exits."""
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None


_db_manager = _DatabaseConnectionManager(DATABASE_PATH)
atexit.register(_db_manager.close)
    def __init__(self, database_path: str):
        self._database_path = database_path
        self._memory_connection = None
        self._memory_connection_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        """
        Open a configured SQLite connection for the module's database path.

        Returns a persistent shared connection when the configured database is
        in-memory; for file-backed databases, returns a new connection instance.
        The connection has type detection enabled (PARSE_DECLTYPES), allows use from
        multiple threads (check_same_thread=False) and uses sqlite3.Row for rows.
        When the database path is a URI beginning with "file:" the connection is
        opened with URI handling enabled.

        Returns:
            sqlite3.Connection: A sqlite3 connection to the configured
                DATABASE_PATH (shared for in-memory, new per call for file-backed).
        """
        if _is_memory_db(self._database_path):
            with self._memory_connection_lock:
                if self._memory_connection is None:
                    self._memory_connection = sqlite3.connect(
                        self._database_path,
                        detect_types = sqlite3.PARSE_DECLTYPES,
                        check_same_thread = False,
                        uri = self._database_path.startswith("file:"),
                    )
                    self._memory_connection.row_factory = sqlite3.Row
            return self._memory_connection

        # For file-backed databases, create a new connection each time
        connection = sqlite3.connect(
            self._database_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
            uri=self._database_path.startswith("file:"),
        )
        connection.row_factory = sqlite3.Row
        return connection

    def close(self) -> None:
        """Clean up the shared in-memory connection when the program exits."""
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None


_db_manager = _DatabaseConnectionManager(DATABASE_PATH)
atexit.register(_db_manager.close)
_db_manager = _DatabaseConnectionManager(DATABASE_PATH)
atexit.register(_db_manager.close)

def _cleanup_memory_connection() -> None:
    """Clean up the shared in-memory connection when the program exits."""
    connection = getattr(_db_manager, "_memory_connection", None)
    if connection is not None:
        connection.close()


atexit.register(_cleanup_memory_connection)


def execute(query: str, parameters: tuple | list | None=None) -> None:
    """
    Execute a SQL write statement and commit the transaction using the module's
    managed SQLite connection.

    Parameters:
        query (str): SQL statement to execute.
        parameters (tuple | list | None): Sequence of values to bind to the statement;
            use `None` or an empty sequence if there are no parameters.
    """
    with get_connection() as connection:
        connection.execute(query, parameters or ())
        connection.commit()


def fetch_one(query: str, parameters: tuple | list | None=None):
    """
    Retrieve the first row produced by an SQL query.

    Parameters:
        query (str): SQL statement to execute.
        parameters (tuple | list | None): Optional sequence of parameters
            to bind into the query.

    Returns:
        sqlite3.Row | None: The first row of the result set
            as a `sqlite3.Row`, or `None` if the query returned no rows.
    """
    with get_connection() as connection:
        cursor = connection.execute(query, parameters or ())
        return cursor.fetchone()


def fetch_value(query: str, parameters: tuple | list | None=None):
    """
    Fetches the first column value from the first row of a query result.

    Parameters:
        query (str): SQL query to execute; may include parameter placeholders.
        parameters (tuple | list | None): Sequence of parameters for the query
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
    execute(
        """
        CREATE TABLE IF NOT EXISTS user_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            full_name TEXT,
            hashed_password TEXT NOT NULL,
            disabled INTEGER NOT NULL DEFAULT 0
        )
        """
    )

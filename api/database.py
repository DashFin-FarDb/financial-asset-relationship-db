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
    """Retrieve the DATABASE_URL environment variable."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set before using the database")
    return database_url


def _resolve_sqlite_path(url: str) -> str:
    """Resolve a SQLite URL to a filesystem path or the in-memory indicator.

    This function accepts SQLite URLs with various schemes, including
    `sqlite:///relative.db`, `sqlite:////absolute/path.db`, and
    `sqlite:///:memory:`. It decodes percent-encodings in the URL path  before
    resolution. For in-memory URLs, it returns the string  `":memory:"`, while URI-
    style memory databases are returned as-is.  The function also handles the
    normalization of paths based on their  leading slashes to determine if they are
    absolute or relative.

    Args:
        url (str): SQLite URL to resolve.
    """
    parsed = urlparse(url)
    if parsed.scheme != "sqlite":
        raise ValueError(f"Not a valid sqlite URI: {url}")

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
    """Determine if the specified database is an in-memory SQLite database.

    This function checks whether the provided database path or the configured
    DATABASE_PATH refers to an in-memory SQLite database. It evaluates the  path
    against the literal ":memory:" and also supports URI-style memory  databases,
    such as "file::memory:?cache=shared", by parsing the URI  and checking its
    scheme and query parameters.

    Args:
        path (str | None): Optional database path or URI to evaluate.
    """
    target = DATABASE_PATH if path is None else path
    if target == ":memory:":
        return True

    # SQLite supports URI-style memory databases such as ``file::memory:?cache=shared``.
    parsed = urlparse(target)
    if parsed.scheme == "file" and (parsed.path == ":memory:" or ":memory:" in parsed.query):
        return True

    return False


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
    global _MEMORY_CONNECTION

    if _is_memory_db():
        with _MEMORY_CONNECTION_LOCK:
            if _MEMORY_CONNECTION is None:
                _MEMORY_CONNECTION = sqlite3.connect(
                    DATABASE_PATH,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                    check_same_thread=False,
                    uri=DATABASE_PATH.startswith("file:"),
                )
                _MEMORY_CONNECTION.row_factory = sqlite3.Row
        return _MEMORY_CONNECTION

    # For file-backed databases, create a new connection each time
    connection = sqlite3.connect(
        DATABASE_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        uri=DATABASE_PATH.startswith("file:"),
    )
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Provide a context-managed SQLite connection for the configured database."""
    connection = _connect()
    try:
        yield connection
    finally:
        if not _is_memory_db():
            connection.close()


def _cleanup_memory_connection():
    """Clean up the global memory connection."""
    global _MEMORY_CONNECTION
    if _MEMORY_CONNECTION is not None:
        _MEMORY_CONNECTION.close()
        _MEMORY_CONNECTION = None


atexit.register(_cleanup_memory_connection)


def execute(query: str, parameters: tuple | list | None = None) -> None:
    """Execute a SQL write statement and commit the transaction.

    Args:
        query (str): SQL statement to execute.
        parameters (tuple | list | None): Sequence of values to bind to the statement;
            use `None` or an empty sequence if there are no parameters.
    """
    with get_connection() as connection:
        connection.execute(query, parameters or ())
        connection.commit()


def fetch_one(query: str, parameters: tuple | list | None = None):
    """Retrieve the first row produced by an SQL query.

    Args:
        query (str): SQL statement to execute.
        parameters (tuple | list | None): Optional sequence of parameters to bind into the query.

    Returns:
        sqlite3.Row | None: The first row of the result set as a `sqlite3.Row`, or
            `None` if the query returned no rows.
    """
    with get_connection() as connection:
        cursor = connection.execute(query, parameters or ())
        return cursor.fetchone()


def fetch_value(query: str, parameters: tuple | list | None = None):
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
    """Create the user_credentials table if it does not exist."""
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

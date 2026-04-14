"""Lightweight database helpers for the API layer."""

from __future__ import annotations

import atexit
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
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
        raise ValueError("DATABASE_URL environment variable must be set before using the database")
    return database_url


def _normalize_sqlite_path(parsed_path: str) -> str:
    """
    Decode percent-encoding in a SQLite URL path.

    Parameters:
        parsed_path (str): The raw path component extracted from a parsed SQLite URL, possibly containing percent-encoded characters.

    Returns:
        str: The path with percent-encoded sequences decoded.
    """
    return unquote(parsed_path)


def _is_standard_memory_path(parsed: object, normalized_path: str) -> bool:
    """
    Determine whether a parsed SQLite URL refers to the standard SQLite in-memory database.

    Parameters:
        parsed (object): Result of urllib.parse.urlparse (or similar) whose `netloc` may be ":memory:".
        normalized_path (str): Percent-decoded path component of the URL.

    Returns:
        bool: `True` if `parsed.netloc == ":memory:"` or `normalized_path` is `":memory:"` or `"/:memory:"`, `False` otherwise.
    """
    parsed_netloc = getattr(parsed, "netloc", "")
    return parsed_netloc == ":memory:" or normalized_path in {":memory:", "/:memory:"}


def _resolve_uri_style_memory_path(
    path: str,
    query: str,
) -> str | None:
    """
    Detects and returns a URI-style SQLite in-memory path (e.g. "file::memory:") extracted from a URL path component.

    If `path` represents a URI-style in-memory database (after removing leading slashes and beginning with `file:` and containing `:memory:`), returns the normalized URI string; if `query` is non-empty it is appended prefixed with `?`.

    Parameters:
        path (str): URL path component that may include leading slashes and a `file:` URI indicating an in-memory database.
        query (str): Raw query string (without a leading '?') to append when present.

    Returns:
        str | None: The normalized URI-style memory path with `?{query}` appended if `query` is non-empty, or `None` if `path` is not a URI-style memory database.
    """
    if not path.lstrip("/").startswith("file:") or ":memory:" not in path:
        return None
    result = path.lstrip("/")
    if query:
        result += f"?{query}"
    return result


def _resolve_file_path(path: str) -> str:
    """
    Convert a normalized SQLite file path component into an absolute filesystem path.

    Handles three forms:
    - Absolute paths starting with a single leading slash (e.g., "/foo") are resolved as-is.
    - UNC-like paths starting with two leading slashes (e.g., "//server/path") drop the first slash and are resolved.
    - Rootless or relative-looking paths have any leading slashes removed and are resolved relative to the current working directory.

    Parameters:
        path (str): Normalized SQLite path component; may be absolute ("/..."), UNC-like ("//..."), or rootless.

    Returns:
        str: The resolved absolute filesystem path.
    """
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
    Determine whether a SQLite database path denotes an in-memory database.

    If `path` is omitted, the configured `DATABASE_PATH` is evaluated. The function treats the literal ":memory:" and file-style URIs whose path component is exactly ":memory:" (for example, "file::memory:" or "file::memory:?cache=shared") as in-memory targets. It does not treat file URIs where ":memory:" appears as part of a filesystem path or URIs that use `mode=memory` as in-memory.

    Parameters:
        path (str | None): Database path or URI to evaluate. If omitted, `DATABASE_PATH` is used.

    Returns:
        bool: `True` if the evaluated target denotes an in-memory SQLite database, `False` otherwise.
    """
    target = DATABASE_PATH if path is None else path
    if target == ":memory:":
        return True

    # SQLite supports URI-style memory databases such as
    # ``file::memory:?cache=shared``.
    # The :memory: token must be the entire path component
    # (not part of a longer path).
    parsed = urlparse(target)
    return parsed.scheme == "file" and (parsed.path == ":memory:" or ":memory:" in parsed.query)


class _DatabaseConnectionManager:
    """Manages SQLite connections to a configured database path.

    Provides a persistent shared connection for in-memory databases and creates
    new connections for file-backed databases. Thread-safe for in-memory usage.
    """

    LEGACY_CONNECTION = None

    def __init__(self, database_path: str):
        """
        Create a connection manager for the given resolved SQLite database path.

        Parameters:
            database_path (str): Resolved SQLite path that determines connection strategy — a filesystem path, the literal ":memory:", or a URI-style memory path (e.g. "file::memory:?cache=shared").
        """
        self._database_path = database_path
        self._memory_connection: sqlite3.Connection | None = None
        self._memory_connection_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        """
        Open a SQLite connection for the manager's configured database path.

        Returns:
            sqlite3.Connection: The shared in-memory connection when the configured path is an in-memory database; otherwise a new connection for a file-backed database. The returned connection has its row factory set to `sqlite3.Row`.
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
                if connection is None:
                    raise RuntimeError("Expected an initialized in-memory connection but found None.")
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
        """
        Close the manager's shared persistent in-memory SQLite connection, if present.

        If a shared in-memory connection exists, it is closed and cleared. This method is safe to call repeatedly and acquires the manager's internal lock while performing the close.
        """
        with self._memory_connection_lock:
            if self._memory_connection is not None:
                self._memory_connection.close()
                self._memory_connection = None


_db_manager = _DatabaseConnectionManager(DATABASE_PATH)


def _connect() -> sqlite3.Connection:
    """
    Return a SQLite connection for the configured database path.

    Returns:
        sqlite3.Connection: Connection to DATABASE_PATH — a shared persistent connection for in-memory databases, or a new connection instance for file-backed databases.
    """
    return _db_manager.connect()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Yield a context-managed SQLite connection for the configured database.

    For file-backed databases the yielded connection is closed when the context exits. For in-memory databases a shared persistent connection is yielded and remains open across calls (the context does not close it).

    Returns:
        sqlite3.Connection: An open SQLite connection for the configured database.
    """
    connection = _connect()
    is_memory = _is_memory_db()
    try:
        yield connection
    finally:
        if not is_memory:
            connection.close()


def _cleanup_memory_connection() -> None:
    """
    Close the module's shared in-memory SQLite connection if one exists.

    Closes and clears the cached shared in-memory connection; no action is taken when no shared connection is initialized. This does not affect file-backed connections.
    """
    _db_manager.close_shared_connection()


_close_shared_memory_connection = _cleanup_memory_connection

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


def fetch_value(query: str, parameters: tuple | list | None = None) -> object | None:
    """
    Return the first column value from the first row of a query result.

    If the query returns no rows, returns `None`. For any non-string indexable row
    (e.g. ``sqlite3.Row``, ``tuple``, ``list``, SQLAlchemy ``Row``, or a mock with
    ``__getitem__``), attempts to return ``row[0]``.  Returns ``None`` when the row
    is empty (i.e. ``row[0]`` raises ``IndexError``), and returns the row object
    unchanged only when indexing is not supported (``TypeError``).

    Parameters:
        query (str): SQL query to execute; may include parameter placeholders.
        parameters (tuple | list | None): Sequence of parameters for the query placeholders.

    Returns:
        The first column value from the first row, or `None` if no row is returned.
    """
    row = fetch_one(query, parameters)
    if row is None:
        return None
    if isinstance(row, (sqlite3.Row, tuple, list)):
        return row[0] if row else None
    try:
        return row[0]
    except IndexError:
        return None
    except TypeError:
        return row


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

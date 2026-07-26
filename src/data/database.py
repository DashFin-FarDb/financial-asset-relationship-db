"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.settings import get_settings

from .base import Base

# Canonical transaction helper lives in repository.py per tech spec.
# Re-export here for backward compatibility with older imports.
from .repository import session_scope  # noqa: F401, E402

DEFAULT_DATABASE_URL = "sqlite:///./asset_graph.db"
ASSET_GRAPH_DATABASE_URL_ENV_VAR = "ASSET_GRAPH_DATABASE_URL"


def _sqlite_translate(value: str | None, from_chars: str | None, to_chars: str | None) -> str | None:
    """PostgreSQL-compatible ``translate`` for SQLite CHECK constraints."""
    if value is None or from_chars is None or to_chars is None:
        return None
    mapped = {char: (to_chars[index] if index < len(to_chars) else None) for index, char in enumerate(from_chars)}
    pieces: list[str] = []
    for char in value:
        replacement = mapped.get(char, char)
        if replacement is None:
            continue
        pieces.append(replacement)
    return "".join(pieces)


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    """Enable FK enforcement and Postgres-compatible helpers on SQLite connects."""
    dbapi_connection.create_function("translate", 3, _sqlite_translate)
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def configure_sqlite_engine(engine: Engine) -> Engine:
    """Attach SQLite connection hooks required for GRAC FK + CHECK integrity.

    Registers a Postgres-compatible ``translate`` UDF and enables
    ``PRAGMA foreign_keys=ON`` on every new DB-API connection. File-backed
    engines dispose pooled connections so the next checkout picks up the hooks;
    in-memory engines configure the live connection in place so StaticPool
    state is preserved.
    """
    if event.contains(engine, "connect", _configure_sqlite_connection):
        return engine
    event.listen(engine, "connect", _configure_sqlite_connection)

    url = make_url(str(engine.url))
    database = url.database or ""
    query: dict = dict(url.query) if getattr(url, "query", None) else {}
    is_memory = database == ":memory:" or query.get("mode") == "memory"
    if is_memory:
        with engine.connect() as connection:
            dbapi_connection = connection.connection.dbapi_connection
            _configure_sqlite_connection(dbapi_connection, None)
    else:
        engine.dispose()
    return engine


# Backward-compatible private alias.
_configure_sqlite_engine = configure_sqlite_engine


def create_engine_from_url(url: str | None = None) -> Engine:
    """
    Resolve a database URL and create a SQLAlchemy Engine for the asset store.

    If ``url`` is None, reads ``settings.asset_graph_database_url`` and falls
    back to ``DEFAULT_DATABASE_URL`` when unset. An empty string forces the
    default file-based SQLite URL; otherwise the provided ``url`` is used.

    For SQLite in-memory databases (``database == ":memory:"`` or query
    ``mode=memory``), the engine uses ``check_same_thread=False`` and
    ``StaticPool``.

    Parameters:
        url: Optional database URL. None uses settings; empty string uses the
            default file-based SQLite URL.

    Returns:
        Engine configured for the resolved URL, including SQLite in-memory
        connection arguments and a static pool when applicable.

    Raises:
        ArgumentError: If an explicit ``url`` cannot be parsed as a SQLAlchemy URL.
    """
    is_explicit_url = url is not None and url != ""
    if url is None:
        settings = get_settings()
        resolved_url = settings.asset_graph_database_url or DEFAULT_DATABASE_URL
    elif url == "":
        resolved_url = DEFAULT_DATABASE_URL
    else:
        resolved_url = url

    try:
        parsed_url = make_url(resolved_url)
    except ArgumentError:
        if is_explicit_url:
            raise
        return _configure_sqlite_engine(create_engine(DEFAULT_DATABASE_URL, future=True))

    is_sqlite = parsed_url.get_backend_name() == "sqlite"
    database = parsed_url.database or ""
    query: dict = dict(parsed_url.query) if getattr(parsed_url, "query", None) else {}

    is_sqlite_memory = is_sqlite and (database == ":memory:" or query.get("mode") == "memory")

    if is_sqlite:
        connect_args = {"check_same_thread": False}
        if is_sqlite_memory:
            return _configure_sqlite_engine(
                create_engine(
                    resolved_url,
                    future=True,
                    connect_args=connect_args,
                    poolclass=StaticPool,
                )
            )
        return _configure_sqlite_engine(
            create_engine(
                resolved_url,
                future=True,
                connect_args=connect_args,
            )
        )

    return create_engine(resolved_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """
    Create a SQLAlchemy session factory bound to the provided engine.

    Produced sessions use autocommit disabled, autoflush disabled, and
    SQLAlchemy 2.0 ``future`` behavior.

    Parameters:
        engine: Engine to bind produced Session instances to.

    Returns:
        A sessionmaker that produces Session objects bound to ``engine``.
    """
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )


def init_db(engine: Engine) -> None:
    """
    Create database tables for all ORM models declared on Base.metadata.

    Creates any missing tables in the database referenced by the provided SQLAlchemy Engine.
    Also applies any pending SQL migrations to ensure schema is up-to-date, then installs
    GRAC v1 assertion immutability guards.

    Parameters:
        engine (Engine): SQLAlchemy Engine connected to the target database where tables will be created.
    """
    # Register GRAC ORM tables on Base.metadata before create_all.
    from . import relationship_assertion_db_models as _relationship_assertion_db_models  # noqa: F401
    from .migrations import apply_migrations, apply_postgresql_heartbeat_migration
    from .relationship_assertion_schema import ensure_relationship_assertion_schema

    # Apply SQL migrations (e.g., adding heartbeat columns to rebuild_jobs)
    # Extract database path from engine URL for SQLite databases
    # For non-SQLite or in-memory databases, skip migrations (they use create_all only)
    url = make_url(engine.url)
    backend = url.get_backend_name()
    query: dict = dict(url.query) if getattr(url, "query", None) else {}
    is_sqlite_memory = backend == "sqlite" and (url.database == ":memory:" or query.get("mode") == "memory")

    # GRAC CHECKs use translate(); attach UDF + FK pragma before create_all.
    if backend == "sqlite":
        configure_sqlite_engine(engine)

    Base.metadata.create_all(engine)

    if backend == "sqlite" and url.database and not is_sqlite_memory:
        apply_migrations(url.database)
    elif backend == "postgresql":
        apply_postgresql_heartbeat_migration(engine)

    ensure_relationship_assertion_schema(engine)

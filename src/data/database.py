"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

from sqlalchemy import create_engine
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


def create_engine_from_url(url: str | None = None) -> Engine:
    """
    Resolve a database URL and create a SQLAlchemy Engine configured for the asset relationship store.
    
    If `url` is None the function reads `settings.asset_graph_database_url` and falls back to DEFAULT_DATABASE_URL when unset; if `url` is an empty string it uses DEFAULT_DATABASE_URL; otherwise the provided `url` is used. For an SQLite in-memory database (database == ":memory:" or query param `mode=memory`) the returned engine is configured with `connect_args={"check_same_thread": False}` and `poolclass=StaticPool` to support in-memory usage.
    
    Parameters:
        url (str | None): Optional database URL to use; None selects the value from settings, empty string forces the default file-based SQLite URL.
    
    Returns:
        Engine: A SQLAlchemy Engine for the resolved URL. For SQLite in-memory URLs the engine is returned with connection arguments and a static pool suitable for in-memory operation.
    
    Raises:
        ArgumentError: If `url` is provided explicitly but cannot be parsed as a valid SQLAlchemy URL.
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
        return create_engine(DEFAULT_DATABASE_URL, future=True)

    is_sqlite = parsed_url.get_backend_name() == "sqlite"
    database = parsed_url.database or ""
    query = parsed_url.query or {}

    is_sqlite_memory = is_sqlite and (database == ":memory:" or query.get("mode") == "memory")

    if is_sqlite_memory:
        return create_engine(
            resolved_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    return create_engine(resolved_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """
    Create a SQLAlchemy session factory bound to the provided engine.

    The factory produces Session objects with autocommit disabled, autoflush disabled, and SQLAlchemy 2.0 `future` behavior enabled.

    Parameters:
        engine (Engine): Engine to bind produced Session instances to.

    Returns:
        session_factory (sessionmaker[Session]): A configured sessionmaker that produces Session objects bound to `engine`.
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

    Parameters:
        engine (Engine): SQLAlchemy Engine connected to the target database where tables will be created.
    """
    Base.metadata.create_all(engine)

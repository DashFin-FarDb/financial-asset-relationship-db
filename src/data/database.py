"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .base import Base

# Canonical transaction helper lives in repository.py per tech spec.
# Re-export here for backward compatibility with older imports.
from .repository import session_scope  # noqa: F401, E402

DEFAULT_DATABASE_URL = "sqlite:///./asset_graph.db"
ASSET_GRAPH_DATABASE_URL_ENV_VAR = "ASSET_GRAPH_DATABASE_URL"


def create_engine_from_url(url: str | None = None) -> Engine:
    """
    Create a SQLAlchemy Engine configured for the asset relationship store database.

    Parameters:
        url (str | None): Optional database URL. If None, uses ASSET_GRAPH_DATABASE_URL
            environment variable, falling back to DEFAULT_DATABASE_URL. Empty string
            falls back to DEFAULT_DATABASE_URL.

    Returns:
        Engine: A SQLAlchemy Engine for the resolved URL. If the URL refers to an
            in-memory SQLite database (contains ":memory:"), the engine is configured
            with connection arguments and a static pool appropriate for in-memory usage.
    """
    is_explicit_url = url is not None and url != ""
    if url is None:
        resolved_url = os.getenv(ASSET_GRAPH_DATABASE_URL_ENV_VAR) or DEFAULT_DATABASE_URL
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

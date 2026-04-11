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


def create_engine_from_url(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    if url is not None:
        resolved_url = url
    else:
        # Read at call time for runtime flexibility, but document the change.
        resolved_url = os.getenv("ASSET_GRAPH_DATABASE_URL", DEFAULT_DATABASE_URL)

    try:
        parsed_url = make_url(resolved_url)
    except ArgumentError:
        return create_engine(resolved_url, future=True)

    is_sqlite = parsed_url.get_backend_name() == "sqlite"
    database = parsed_url.database or ""
    query = parsed_url.query or {}

    is_sqlite_memory = is_sqlite and (
        database == ":memory:" or query.get("mode") == "memory"
    )

    if is_sqlite_memory:
        return create_engine(
            resolved_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    return create_engine(resolved_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured session factory bound to the supplied engine."""
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )


def init_db(engine: Engine) -> None:
    """Initialise database schema if it has not been created."""
    Base.metadata.create_all(engine)"""Database configuration helpers for the asset relationship store."""


# Canonical transaction helper lives in repository.py per tech spec.
# Re-export here for backward compatibility with older imports.
from .repository import session_scope  # noqa: F401, E402

DEFAULT_DATABASE_URL = "sqlite:///./asset_graph.db"


def create_engine_from_url(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    if url is not None:
        resolved_url = url
    else:
        # Read at call time for runtime flexibility, but document the change.
        resolved_url = os.getenv("ASSET_GRAPH_DATABASE_URL", DEFAULT_DATABASE_URL)

    try:
        parsed_url = make_url(resolved_url)
    except ArgumentError:
        return create_engine(resolved_url, future=True)

    is_sqlite = parsed_url.get_backend_name() == "sqlite"
    database = parsed_url.database or ""
    query = parsed_url.query or {}

    is_sqlite_memory = is_sqlite and (
        database == ":memory:" or query.get("mode") == "memory"
    )

    if is_sqlite_memory:
        return create_engine(
            resolved_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    return create_engine(resolved_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured session factory bound to the supplied engine."""
    return sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )


def init_db(engine: Engine) -> None:
    """Initialise database schema if it has not been created."""
    Base.metadata.create_all(engine)

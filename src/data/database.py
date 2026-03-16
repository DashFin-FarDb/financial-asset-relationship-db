"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from importlib import import_module

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()

DEFAULT_DATABASE_URL = os.getenv(
    "ASSET_GRAPH_DATABASE_URL",
    "sqlite:///./asset_graph.db",
)

__all__ = [
    "Base",
    "DEFAULT_DATABASE_URL",
    "create_engine_from_url",
    "create_session_factory",
    "init_db",
    "session_scope",
]


def create_engine_from_url(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    resolved_url = url or DEFAULT_DATABASE_URL

    if resolved_url.startswith("sqlite") and ":memory:" in resolved_url:
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


@contextmanager
def session_scope(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """Proxy to repository.session_scope while avoiding import-order lint issues."""
    # Keep compatibility for callers importing session_scope from this module.
    repository_session_scope = import_module(
        "src.data.repository"
    ).session_scope

    with repository_session_scope(session_factory) as session:
        yield session


def init_db(engine: Engine) -> None:
    """Initialise database schema if it has not been created."""
    Base.metadata.create_all(engine)

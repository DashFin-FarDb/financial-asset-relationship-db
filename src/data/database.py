"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()

__all__ = [
    "Base",
    "session_scope",
    "create_engine_from_url",
    "create_session_factory",
    "init_db",
]

DEFAULT_DATABASE_URL = os.getenv(
    "ASSET_GRAPH_DATABASE_URL",
    "sqlite:///./asset_graph.db",
)


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


def init_db(engine: Engine) -> None:
    """Initialise database schema if it has not been created."""
    Base.metadata.create_all(engine)


# Re-export session_scope from repository for backward compatibility
def __getattr__(name):
    """Lazy import to avoid circular dependency."""
    if name == "session_scope":
        from .repository import session_scope

        return session_scope
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

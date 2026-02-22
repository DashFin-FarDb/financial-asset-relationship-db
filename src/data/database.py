"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()

DEFAULT_DATABASE_URL = os.getenv(
    "ASSET_GRAPH_DATABASE_URL",
    "sqlite:///./asset_graph.db",
)


@contextmanager
def session_scope(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    This is the canonical transaction boundary helper for repository interactions.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_engine_from_url(url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database URL."""
    resolved_url = url or os.getenv("ASSET_GRAPH_DATABASE_URL", DEFAULT_DATABASE_URL)

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

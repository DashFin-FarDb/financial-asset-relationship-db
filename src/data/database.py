"""Database configuration helpers for the asset relationship store."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Callable, Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()


DEFAULT_DATABASE_URL = os.getenv(
    "ASSET_GRAPH_DATABASE_URL", "sqlite:///./asset_graph.db"
)


def create_engine_from_url(url: Optional[str] = None) -> Engine:
    """
    Create a SQLAlchemy Engine for the given database URL or the module default.

    If the resolved URL is an in-memory SQLite database (scheme starts with "sqlite" and contains ":memory:"), the engine is created with connect_args {"check_same_thread": False} and a StaticPool to allow cross-thread reuse. For any other URL, a standard engine is created with future=True.

    Parameters:
        url (Optional[str]): Database URL to use. If omitted, DEFAULT_DATABASE_URL is used.

    Returns:
        Engine: A configured SQLAlchemy Engine for the resolved URL.
    """
    resolved_url = url or DEFAULT_DATABASE_URL

    #

    if resolved_url.startswith("sqlite") and ":memory:" in resolved_url:
        return create_engine(
            resolved_url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(resolved_url, future=True)


def create_session_factory(engine: Engine) -> sessionmaker:
    """Create a configured session factory bound to the supplied engine."""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db(engine: Engine) -> None:
    """Initialise database schema if it has not been created."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

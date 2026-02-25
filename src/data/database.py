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
    Provide a transactional SQLAlchemy session scope for repository operations.

    Yields a Session obtained from session_factory, commits the transaction if the block exits normally, rolls back if an exception occurs, and always closes the session.

    Parameters:
        session_factory (Callable[[], Session]): Factory callable that produces a SQLAlchemy Session to use within the scope.

    Returns:
        Session: The session instance yielded to the caller for use within the transactional context.
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
    """
    Create a SQLAlchemy Engine configured for the asset graph database URL.

    If `url` is provided it is used verbatim; otherwise the `ASSET_GRAPH_DATABASE_URL`
    environment variable is read at call time and falls back to the module default.
    When the resolved URL refers to an in-memory SQLite database (scheme starts with
    "sqlite" and contains ":memory:"), the engine is created with connection args
    suitable for shared access across threads and an in-memory-safe pool.

    Parameters:
        url (str | None): Optional database URL to use instead of the environment variable.

    Returns:
        Engine: A configured SQLAlchemy Engine for the resolved database URL.
    """
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

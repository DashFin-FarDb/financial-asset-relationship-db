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
    """
    Create a SQLAlchemy Engine for the given database URL, using the module default when none is provided.

    If `url` is None, `DEFAULT_DATABASE_URL` is used. When the resolved URL is an in-memory SQLite database, the engine is configured with `connect_args={"check_same_thread": False}` and `poolclass=StaticPool` to allow connections to be shared appropriately; otherwise a standard engine is created.

    Parameters:
        url (str | None): Database URL to use; if None the module's `DEFAULT_DATABASE_URL` is used.

    Returns:
        Engine: A SQLAlchemy Engine bound to the resolved database URL.
    """
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


@contextmanager
def session_scope(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """
    Provide a context-managed database Session for use within a with-statement.

    Yields a Session produced by the provided session_factory and scoped to the context manager.

    Parameters:
        session_factory (Callable[[], Session]): Callable that returns a new Session instance.

    Returns:
        session (Session): Session instance yielded while the context is active.
    """
    # Keep compatibility for callers importing session_scope from this module.
    repository_session_scope = import_module("src.data.repository").session_scope

    with repository_session_scope(session_factory) as session:
        yield session


def init_db(engine: Engine) -> None:
    """
    Create database tables for all ORM models declared on Base.metadata.

    Creates any missing tables in the database referenced by the provided SQLAlchemy Engine.

    Parameters:
        engine (Engine): SQLAlchemy Engine connected to the target database where tables will be created.
    """
    Base.metadata.create_all(engine)

"""Boundary providers for graph lifecycle initialization."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select  # pylint: disable=import-error
from sqlalchemy.engine import make_url  # pylint: disable=import-error
from sqlalchemy.exc import ArgumentError  # pylint: disable=import-error
from sqlalchemy.orm import Session  # pylint: disable=import-error

from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import AssetORM
from src.data.repository import AssetGraphRepository
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)

GraphRebuildSource = Literal["cache", "real_data", "sample"]


@dataclass(frozen=True)
class GraphLifecycleSettings:
    """Settings needed by graph lifecycle initialization."""

    asset_graph_database_url: str | None
    graph_cache_path: str | None
    real_data_cache_path: str | None
    use_real_data_fetcher: bool


class GraphPersistenceNotConfiguredError(RuntimeError):
    """Raised when durable graph persistence is not explicitly configured."""


class GraphPersistenceNonDurableError(RuntimeError):
    """Raised when graph persistence is configured with a non-durable target."""


class GraphPersistenceSaveError(RuntimeError):
    """Raised when a rebuilt graph could not be persisted."""


class GraphRebuildSourceError(RuntimeError):
    """Raised when a fresh rebuild graph could not be constructed."""


def get_graph_lifecycle_settings() -> GraphLifecycleSettings:
    """Construct a GraphLifecycleSettings instance from the application settings."""
    settings = get_settings()
    return GraphLifecycleSettings(
        asset_graph_database_url=settings.asset_graph_database_url,
        graph_cache_path=settings.graph_cache_path,
        real_data_cache_path=settings.real_data_cache_path,
        use_real_data_fetcher=settings.use_real_data_fetcher,
    )


def clear_graph_lifecycle_settings_cache() -> None:
    """Clear cached settings used by graph lifecycle initialization."""
    get_settings.cache_clear()


def load_persisted_graph_if_available(
    database_url: str | None,
) -> AssetRelationshipGraph | None:
    """Load persisted graph truth from a configured durable store."""
    resolved_url = _resolve_persistence_database_url(database_url)
    if resolved_url is None:
        return None

    if _is_in_memory_sqlite_url(resolved_url):
        _log_in_memory_sqlite_persistence_skip()
        return None

    try:
        return _load_persisted_graph_from_configured_store(resolved_url)
    except Exception as exc:
        logger.error(
            "Failed to load persisted graph during startup: %s",
            exc.__class__.__name__,
        )
        raise RuntimeError("Failed to load persisted graph during startup") from None


def load_graph_from_cache_path(
    cache_path: str,
    *,
    enable_network: bool,
) -> AssetRelationshipGraph:
    """Load a graph through the real-data cache path."""
    from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error,import-outside-toplevel

    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=enable_network)
    return fetcher.create_real_database()


def load_graph_from_real_data_fetcher(
    cache_path: str | None,
) -> AssetRelationshipGraph:
    """Load a graph from the real-data fetcher with network access."""
    from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error,import-outside-toplevel

    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=True)
    return fetcher.create_real_database()


def create_sample_graph() -> AssetRelationshipGraph:
    """
    Create a graph populated with the default sample dataset.

    Returns:
        AssetRelationshipGraph: An asset relationship graph populated with the module's default sample data.
    """
    return create_sample_database()


def resolve_durable_graph_persistence_url(database_url: str | None) -> str:
    """
    Resolve and validate a durable graph persistence database URL.

    Raises:
        GraphPersistenceNotConfiguredError: when the URL is unset or blank.
        GraphPersistenceNonDurableError: when the URL points to in-memory SQLite.
    """
    resolved_url = _resolve_persistence_database_url(database_url)
    if resolved_url is None:
        raise GraphPersistenceNotConfiguredError("Graph persistence is not configured.")
    if _is_in_memory_sqlite_url(resolved_url):
        raise GraphPersistenceNonDurableError("Graph persistence must use a durable database.")
    return resolved_url


def build_rebuild_graph(settings: GraphLifecycleSettings) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """
    Build a fresh graph from the configured rebuild source and report that source.

    Rebuild intentionally excludes persisted-load because this path creates the
    replacement snapshot that will be persisted.
    """
    try:
        if settings.graph_cache_path:
            return (
                load_graph_from_cache_path(
                    settings.graph_cache_path,
                    enable_network=settings.use_real_data_fetcher,
                ),
                "cache",
            )
        if settings.use_real_data_fetcher:
            return (
                load_graph_from_real_data_fetcher(settings.real_data_cache_path),
                "real_data",
            )
        return (create_sample_graph(), "sample")
    except Exception as exc:
        logger.error("Failed to build rebuild graph: %s", exc.__class__.__name__)
        raise GraphRebuildSourceError("Failed to build rebuild graph.") from None


def save_graph_to_persistence(
    database_url: str | None,
    graph: AssetRelationshipGraph,
) -> None:
    """
    Persist graph truth to a durable graph store using a short-lived session.

    The URL is validated defensively so callers can pass either raw settings
    values or a previously resolved URL.
    """
    resolved_url = resolve_durable_graph_persistence_url(database_url)
    try:
        engine = create_engine_from_url(resolved_url)
    except Exception as exc:
        logger.error("Failed to prepare graph persistence engine: %s", exc.__class__.__name__)
        raise GraphPersistenceSaveError("Failed to persist rebuilt graph.") from None

    try:
        try:
            session_factory = create_session_factory(engine)
            session = session_factory()
            try:
                AssetGraphRepository(session).save_graph(graph)
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.error("Failed to persist rebuilt graph: %s", exc.__class__.__name__)
                raise GraphPersistenceSaveError("Failed to persist rebuilt graph.") from None
            finally:
                session.close()
        except GraphPersistenceSaveError:
            raise
        except Exception as exc:
            logger.error("Failed to prepare graph persistence session: %s", exc.__class__.__name__)
            raise GraphPersistenceSaveError("Failed to persist rebuilt graph.") from None
    finally:
        engine.dispose()


def _resolve_persistence_database_url(database_url: str | None) -> str | None:
    """
    Resolve and normalize a persistence database URL.

    Returns:
        The trimmed URL string if non-empty, otherwise None.
    """
    resolved_url = (database_url or "").strip()
    return resolved_url or None


def _log_in_memory_sqlite_persistence_skip() -> None:
    """
    Emit a warning that an in-memory SQLite database URL was detected and persisted graph
    loading will be skipped because in-memory SQLite is not durable.
    """
    logger.warning(
        "ASSET_GRAPH_DATABASE_URL points to an in-memory SQLite database; "
        "startup persistence loading requires a file-based or network database. "
        "Skipping persisted graph load."
    )


def _load_persisted_graph_from_configured_store(
    database_url: str,
) -> AssetRelationshipGraph | None:
    """
    Load an AssetRelationshipGraph from the persistent store identified by database_url.

    If the persistent store contains no persisted graph rows, returns None.

    Parameters:
        database_url (str): Database connection URL for the persistent store.

    Returns:
        AssetRelationshipGraph | None: The loaded graph, or `None` when no persisted graph rows exist.
    """
    engine = create_engine_from_url(database_url)
    try:
        session_factory = create_session_factory(engine)
        session = session_factory()
        try:
            if not _has_persisted_graph_rows(session):
                return None
            return AssetGraphRepository(session).load_graph()
        finally:
            session.close()
    finally:
        engine.dispose()


def _has_persisted_graph_rows(session: Session) -> bool:
    """
    Determine whether the persistence store contains at least one persisted asset row.

    Returns:
        `True` if the store contains at least one persisted `AssetORM` row, `False` otherwise.
    """
    return session.execute(select(AssetORM.id).limit(1)).scalar_one_or_none() is not None


def _is_in_memory_sqlite_url(url: str) -> bool:
    """Return whether a SQLAlchemy URL points to in-memory SQLite."""
    try:
        parsed = make_url(url)
    except ArgumentError:
        return False

    if parsed.get_backend_name() != "sqlite":
        return False

    database = parsed.database or ""
    mode = parsed.query.get("mode")
    is_memory_mode = mode == "memory" or (
        isinstance(mode, tuple) and "memory" in mode
    )

    if database in {"", ":memory:"}:
        return True
    if database.startswith("file::memory:"):
        return True
    return database.startswith("file:") and is_memory_mode

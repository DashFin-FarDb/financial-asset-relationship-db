"""Boundary providers for graph lifecycle initialization."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Tuple

from sqlalchemy import select  # pylint: disable=import-error
from sqlalchemy.engine import Engine, make_url  # pylint: disable=import-error
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
    """
    Create a GraphLifecycleSettings populated from the application's settings.

    Returns:
        GraphLifecycleSettings: Instance with values taken from get_settings(): `asset_graph_database_url`, `graph_cache_path`, `real_data_cache_path`, and `use_real_data_fetcher`.
    """
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
    Create a graph populated with the module's default sample dataset.

    Returns:
        AssetRelationshipGraph: An asset relationship graph seeded with the module's default sample data.
    """
    return create_sample_database()


def resolve_durable_graph_persistence_url(database_url: str | None) -> str:
    """
    Validate and return a durable database URL suitable for graph persistence.

    Returns:
        The resolved durable database URL.

    Raises:
        GraphPersistenceNotConfiguredError: If the provided URL is unset or blank.
        GraphPersistenceNonDurableError: If the resolved URL refers to an in-memory SQLite database.
    """
    resolved_url = _resolve_persistence_database_url(database_url)
    if resolved_url is None:
        raise GraphPersistenceNotConfiguredError("Graph persistence is not configured.")
    if _is_in_memory_sqlite_url(resolved_url):
        raise GraphPersistenceNonDurableError("Graph persistence must use a durable database.")
    return resolved_url


def build_rebuild_graph(settings: GraphLifecycleSettings) -> Tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """
    Build a fresh AssetRelationshipGraph from the configured rebuild source and return it with the source identifier.

    If a graph cache path exists on disk, the graph is loaded from that cache and the source is "cache". If no cache is present and real-data fetching is enabled, the graph is constructed from real data and the source is "real_data". Otherwise a sample graph is created and the source is "sample". This function intentionally does not attempt to load a persisted graph; it produces the replacement snapshot that may later be persisted.

    Parameters:
        settings (GraphLifecycleSettings): Configuration that controls cache paths and whether the real-data fetcher is used.

    Returns:
        tuple[AssetRelationshipGraph, GraphRebuildSource]: The rebuilt graph and a literal source identifier: `"cache"`, `"real_data"`, or `"sample"`.

    Raises:
        GraphRebuildSourceError: If any error occurs while constructing the rebuild graph.
    """
    try:
        if settings.graph_cache_path and Path(settings.graph_cache_path).exists():
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
    Persist an AssetRelationshipGraph to a durable database.

    Parameters:
        database_url (str | None): URL of the persistence database; may be None to use configured defaults.
        graph (AssetRelationshipGraph): Graph to persist.

    Raises:
        GraphPersistenceNotConfiguredError: If no persistence URL is configured.
        GraphPersistenceNonDurableError: If the configured URL points to a non-durable (in-memory) store.
        GraphPersistenceSaveError: If saving the graph or creating the persistence engine/session fails.
    """
    resolved_url = resolve_durable_graph_persistence_url(database_url)
    engine = _create_graph_persistence_engine(resolved_url)
    try:
        _save_graph_with_engine(engine, graph)
    finally:
        engine.dispose()


def _create_graph_persistence_engine(database_url: str) -> Engine:
    """
    Create a SQLAlchemy engine for graph persistence.

    Returns:
        engine (Engine): Engine configured for the provided database URL.

    Raises:
        GraphPersistenceSaveError: If the engine cannot be created for the given URL.
    """
    try:
        return create_engine_from_url(database_url)
    except Exception as exc:
        logger.error("Failed to prepare graph persistence engine: %s", exc.__class__.__name__)
        raise GraphPersistenceSaveError("Failed to persist rebuilt graph.") from None


def _save_graph_with_engine(engine: Engine, graph: AssetRelationshipGraph) -> None:
    """
    Persist the provided asset relationship graph using a short-lived database session.

    Parameters:
        engine (Engine): SQLAlchemy engine configured for the persistence store.
        graph (AssetRelationshipGraph): Graph to be persisted.

    Raises:
        GraphPersistenceSaveError: If preparing the persistence session fails or if saving the graph fails.
    """
    try:
        session_factory = create_session_factory(engine)
        session = session_factory()
    except Exception as exc:
        logger.error("Failed to prepare graph persistence session: %s", exc.__class__.__name__)
        raise GraphPersistenceSaveError("Failed to persist rebuilt graph.") from None

    try:
        _save_graph_with_session(session, graph)
    finally:
        session.close()


def _save_graph_with_session(session: Session, graph: AssetRelationshipGraph) -> None:
    """
    Persist the given AssetRelationshipGraph using the provided SQLAlchemy session and commit the transaction.

    Parameters:
        session (Session): Active SQLAlchemy session used to persist the graph.
        graph (AssetRelationshipGraph): Graph to persist.

    Raises:
        GraphPersistenceSaveError: If saving or committing the graph fails; the session will be rolled back.
    """
    try:
        AssetGraphRepository(session).save_graph(graph)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.error("Failed to persist rebuilt graph: %s", exc.__class__.__name__)
        raise GraphPersistenceSaveError("Failed to persist rebuilt graph.") from None


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
    """
    Determine whether a SQLAlchemy database URL refers to an in-memory SQLite database.

    Parameters:
        url (str): SQLAlchemy database URL to evaluate.

    Returns:
        bool: `True` if the URL targets an in-memory SQLite database (empty database component, `:memory:`,
        `file::memory:`, or `file:` with query mode set to memory), `False` otherwise.
    """
    try:
        parsed = make_url(url)
    except ArgumentError:
        return False

    if parsed.get_backend_name() != "sqlite":
        return False

    database = parsed.database or ""
    if database in {"", ":memory:"}:
        return True
    if database.startswith("file::memory:"):
        return True
    return database.startswith("file:") and _query_mode_is_memory(parsed.query.get("mode"))


def _query_mode_is_memory(mode: object) -> bool:
    """
    Determine whether a parsed SQLAlchemy URL query `mode` requests an in-memory database.

    Parameters:
        mode (object): The parsed `mode` query value from a SQLAlchemy URL; typically a string or a tuple of strings.

    Returns:
        True if `mode` is the string `"memory"` or a tuple containing `"memory"`, False otherwise.
    """
    return mode == "memory" or (isinstance(mode, tuple) and "memory" in mode)

"""Boundary providers for graph lifecycle initialization."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select  # pylint: disable=import-error
from sqlalchemy.engine import make_url  # pylint: disable=import-error
from sqlalchemy.exc import ArgumentError  # pylint: disable=import-error
from sqlalchemy.orm import Session  # pylint: disable=import-error

from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import AssetORM
from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error
from src.data.repository import AssetGraphRepository
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GraphLifecycleSettings:
    """Settings needed by graph lifecycle initialization."""

    asset_graph_database_url: str | None
    graph_cache_path: str | None
    real_data_cache_path: str | None
    use_real_data_fetcher: bool


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
    """
    Attempt to load an AssetRelationshipGraph from the configured persistence store.
    
    If `database_url` is unset/blank or refers to an in-memory SQLite database, no durable load is attempted and `None` is returned. Otherwise the function attempts to load a persisted graph from the configured store.
    
    Parameters:
        database_url (str | None): Optional persistence database URL; blank or whitespace-only values are treated as unset.
    
    Returns:
        AssetRelationshipGraph | None: The loaded persisted graph when available, `None` if no durable persistence is configured or an in-memory SQLite URL is provided.
    
    Raises:
        RuntimeError: If a durable persistence URL is configured but loading fails; the exception message includes the original exception class name.
    """
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
        raise RuntimeError(f"Failed to load persisted graph during startup: {exc.__class__.__name__}") from None


def load_graph_from_cache_path(
    cache_path: str,
    *,
    enable_network: bool,
) -> AssetRelationshipGraph:
    """
    Load an AssetRelationshipGraph using a RealDataFetcher configured with the given cache path.
    
    Parameters:
    	cache_path (str): Filesystem path used by the fetcher to read/write cached real-data artifacts.
    	enable_network (bool): Whether the fetcher may access network resources to populate or refresh the cache.
    
    Returns:
    	asset_graph (AssetRelationshipGraph): Graph constructed from the real-data cache (and network if enabled).
    """
    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=enable_network)
    return fetcher.create_real_database()


def load_graph_from_real_data_fetcher(
    cache_path: str | None,
) -> AssetRelationshipGraph:
    """
    Create an AssetRelationshipGraph using the real-data fetcher with network access enabled.
    
    Parameters:
        cache_path (str | None): Optional path to a local cache used by the fetcher; if `None`, the fetcher uses its default cache location.
    
    Returns:
        AssetRelationshipGraph: Graph constructed from fetched real-world data.
    """
    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=True)
    return fetcher.create_real_database()


def create_sample_graph() -> AssetRelationshipGraph:
    """
    Create a graph populated with the default sample dataset.
    
    Returns:
        AssetRelationshipGraph: An asset relationship graph populated with the module's default sample data.
    """
    return create_sample_database()


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
    Emit a warning that an in-memory SQLite database URL was detected and persisted graph loading will be skipped because in-memory SQLite is not durable.
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
        url (str): The database URL to inspect (SQLAlchemy URL string).
    
    Returns:
        bool: `True` if the URL denotes an in-memory SQLite database (database == ":memory:" or query `mode=memory`), `False` otherwise. Parsing errors are treated as non-matching and return `False`.
    """
    try:
        parsed = make_url(url)
    except ArgumentError:
        return False
    if parsed.get_backend_name() != "sqlite":
        return False
    database = parsed.database or ""
    query = parsed.query or {}
    return database == ":memory:" or query.get("mode") == "memory"

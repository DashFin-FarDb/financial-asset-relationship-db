"""Boundary providers for graph lifecycle initialization."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import AssetORM
from src.data.real_data_fetcher import RealDataFetcher
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
    """
    Constructs a GraphLifecycleSettings instance populated from the application's settings.
    
    Returns:
        GraphLifecycleSettings: Configuration containing `asset_graph_database_url`, `graph_cache_path`, `real_data_cache_path`, and `use_real_data_fetcher` taken from the global application settings.
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
    """
    Attempt to load a persisted AssetRelationshipGraph from the given database URL if the URL is configured and the store contains at least one persisted asset.
    
    Parameters:
        database_url (str | None): Database URL for the persisted asset graph; when None or empty (after trimming) no load is attempted.
    
    Returns:
        AssetRelationshipGraph | None: The loaded persisted graph if the configured store is reachable and contains persisted asset rows, otherwise `None`.
    
    Raises:
        RuntimeError: If a configured load is attempted but fails (errors during engine/session creation, row-check, or graph load).
    """
    resolved_database_url = (database_url or "").strip()
    if not resolved_database_url:
        return None

    engine = None
    session = None
    load_error: RuntimeError | None = None
    persisted_graph: AssetRelationshipGraph | None = None
    try:
        engine = create_engine_from_url(resolved_database_url)
        session_factory = create_session_factory(engine)
        session = session_factory()
        if not _has_persisted_graph_rows(session):
            return None
        persisted_graph = AssetGraphRepository(session).load_graph()
    except Exception as exc:
        logger.error(
            "Failed to load persisted graph during startup: %s",
            exc.__class__.__name__,
        )
        load_error = RuntimeError("Failed to load persisted graph during startup")
    finally:
        if session is not None:
            session.close()
        if engine is not None:
            engine.dispose()

    if load_error is not None:
        raise load_error

    return persisted_graph


def create_real_data_graph(
    cache_path: str | None,
    *,
    enable_network: bool,
) -> AssetRelationshipGraph:
    """
    Create an AssetRelationshipGraph using the real-data fetcher.
    
    Parameters:
    	cache_path (str | None): Optional filesystem path for caching fetched real data.
    	enable_network (bool): Whether the fetcher is allowed to access the network.
    
    Returns:
    	AssetRelationshipGraph: Graph constructed from the fetched real data.
    """
    fetcher = RealDataFetcher(
        cache_path=cache_path,
        enable_network=enable_network,
    )
    return fetcher.create_real_database()


def create_sample_graph() -> AssetRelationshipGraph:
    """
    Create an asset relationship graph populated with the default sample dataset.
    
    Returns:
        AssetRelationshipGraph: A graph populated with the module's default sample data.
    """
    return create_sample_database()


def _has_persisted_graph_rows(session: Session) -> bool:
    """
    Determine whether the asset graph store contains at least one persisted asset row.
    
    Returns:
        True if the store has at least one asset row, False otherwise.
    """
    return session.execute(select(AssetORM.id).limit(1)).scalar_one_or_none() is not None

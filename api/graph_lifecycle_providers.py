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
    """Return settings required by graph lifecycle initialization."""
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
    Load a persisted graph when graph persistence is explicitly configured.

    Returns ``None`` only when graph persistence is not configured or when the
    configured store is reachable and schema-ready but has no persisted asset
    rows. Configured load failures are raised so startup does not silently fall
    back to sample or cache data.
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
    """Create a graph through the configured real-data fetcher."""
    fetcher = RealDataFetcher(
        cache_path=cache_path,
        enable_network=enable_network,
    )
    return fetcher.create_real_database()


def create_sample_graph() -> AssetRelationshipGraph:
    """Create the default sample graph."""
    return create_sample_database()


def _has_persisted_graph_rows(session: Session) -> bool:
    """Return whether the asset graph store contains at least one asset row."""
    return session.execute(select(AssetORM.id).limit(1)).scalar_one_or_none() is not None

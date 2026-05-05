"""Graph lifecycle management for the Financial Asset Relationship API.

This module provides thread-safe initialization and management of the global
AssetRelationshipGraph instance used by the API.
"""

import logging
import threading
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import Settings, get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import AssetORM
from src.data.real_data_fetcher import RealDataFetcher
from src.data.repository import AssetGraphRepository
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)

# Global graph instance with thread-safe initialization and configurable
# factory.


class _GraphState:
    """Mutable container for module graph lifecycle state."""

    def __init__(self) -> None:
        """
        Create a container to manage a global AssetRelationshipGraph and an optional factory for its lazy initialization.

        Attributes:
            graph: Cached AssetRelationshipGraph instance or `None` if not yet initialized.
            graph_factory: Optional callable that returns an AssetRelationshipGraph; when set, it will be used to construct `graph`.
        """
        self.graph: AssetRelationshipGraph | None = None
        self.graph_factory: Callable[[], AssetRelationshipGraph] | None = None


graph_state = _GraphState()
graph_lock = threading.Lock()


def get_graph() -> AssetRelationshipGraph:
    """
    Get the module-global AssetRelationshipGraph, initializing it if necessary.

    If the graph is not yet set, it is created via a thread-safe lazy initialization. If initialization fails and the graph remains unset, an exception is raised.

    Returns:
        AssetRelationshipGraph: The initialized global asset relationship graph.

    Raises:
        RuntimeError: If the global graph could not be initialized and remains None.
    """
    if graph_state.graph is None:
        with graph_lock:
            if graph_state.graph is None:
                graph_state.graph = _initialize_graph()
                logger.info("Graph initialized successfully")
    if graph_state.graph is None:
        raise RuntimeError("Global graph initialization failed; graph is None.")
    return graph_state.graph


def set_graph(graph_instance: AssetRelationshipGraph) -> None:
    """
    Register a global AssetRelationshipGraph instance to be returned by get_graph().

    Stores the provided graph as the canonical global instance and clears any configured graph factory so subsequent get_graph() calls return this instance until changed or reset.

    Parameters:
        graph_instance (AssetRelationshipGraph): The AssetRelationshipGraph to register as the global instance.
    """
    with graph_lock:
        graph_state.graph = graph_instance
        graph_state.graph_factory = None


def set_graph_factory(
    factory: Callable[[], AssetRelationshipGraph] | None,
) -> None:
    """
    Configure the callable used to construct the global AssetRelationshipGraph and clear any existing graph so it will be recreated on next access.

    Parameters:
        factory (Optional[Callable[[], AssetRelationshipGraph]]): A zero-argument callable that returns a new AssetRelationshipGraph instance. If `None`, any configured factory is cleared and the graph will be reinitialized using settings-driven defaults or a sample database on next access.
    """
    with graph_lock:
        graph_state.graph_factory = factory
        graph_state.graph = None


def reset_graph() -> None:
    """
    Reset module-level graph state so the graph will be recreated on next access.

    Clears the cached graph instance, any configured graph factory, and the
    settings cache to ensure environment variable changes are observed on the
    next initialization.
    """
    # Clear settings cache to preserve reset semantics: environment variable
    # changes made after reset should be picked up on next initialization.
    get_settings.cache_clear()
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """
    Initialize the global AssetRelationshipGraph using the configured factory or settings-driven data sources.

    Initialization order:
        - If `graph_state.graph_factory` is set, return the factory result.
        - If `settings.graph_cache_path` is set, create a `RealDataFetcher`
          with that path. Network access is enabled when
          `settings.use_real_data_fetcher` is enabled.
        - If `settings.graph_cache_path` is not set, but
          `settings.use_real_data_fetcher` is enabled, create a
          `RealDataFetcher` using `settings.real_data_cache_path` with network
          access enabled.
        - Otherwise, return the sample in-memory graph.

    Returns:
        AssetRelationshipGraph: The initialized graph instance.
    """
    if graph_state.graph_factory is not None:
        return graph_state.graph_factory()

    settings = get_settings()
    persisted_graph = _load_persisted_graph_if_available(settings)
    if persisted_graph is not None:
        return persisted_graph

    cache_path = settings.graph_cache_path
    use_real_data = settings.use_real_data_fetcher

    if cache_path:
        fetcher = RealDataFetcher(
            cache_path=cache_path,
            enable_network=use_real_data,
        )
        return fetcher.create_real_database()

    if use_real_data:
        real_data_cache_path = settings.real_data_cache_path
        fetcher = RealDataFetcher(
            cache_path=real_data_cache_path,
            enable_network=True,
        )
        return fetcher.create_real_database()

    return create_sample_database()


def _load_persisted_graph_if_available(
    settings: Settings,
) -> AssetRelationshipGraph | None:
    """
    Load a persisted graph when graph persistence is explicitly configured.

    Returns ``None`` only when graph persistence is not configured or when the
    configured store is reachable and schema-ready but has no persisted asset
    rows. Configured load failures are raised so startup does not silently fall
    back to sample or cache data.
    """
    database_url = (settings.asset_graph_database_url or "").strip()
    if not database_url:
        return None

    engine = None
    session = None
    try:
        engine = create_engine_from_url(database_url)
        session_factory = create_session_factory(engine)
        session = session_factory()
        if not _has_persisted_graph_rows(session):
            return None
        return AssetGraphRepository(session).load_graph()
except Exception:
        logger.error("Failed to load persisted graph during startup (sanitized)")
        raise RuntimeError("Failed to load persisted graph during startup")
    finally:
        if session is not None:
            session.close()
        if engine is not None:
            engine.dispose()


def _has_persisted_graph_rows(session: Session) -> bool:
    """Return whether the asset graph store contains at least one asset row."""
    return session.execute(select(AssetORM.id).limit(1)).scalar_one_or_none() is not None

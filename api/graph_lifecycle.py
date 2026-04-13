"""Graph lifecycle management for the Financial Asset Relationship API.

This module provides thread-safe initialization and management of the global
AssetRelationshipGraph instance used by the API.
"""

import logging
import os
import threading
from typing import Callable, Optional

from src.data.real_data_fetcher import RealDataFetcher
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
        self.graph: Optional[AssetRelationshipGraph] = None
        self.graph_factory: Optional[Callable[[], AssetRelationshipGraph]] = None


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
    factory: Optional[Callable[[], AssetRelationshipGraph]],
) -> None:
    """
    Configure the callable used to construct the global AssetRelationshipGraph and clear any existing graph so it will be recreated on next access.

    Parameters:
        factory (Optional[Callable[[], AssetRelationshipGraph]]): A zero-argument callable that returns a new AssetRelationshipGraph instance. If `None`, any configured factory is cleared and the graph will be reinitialized using environment-backed defaults or a sample database on next access.
    """
    with graph_lock:
        graph_state.graph_factory = factory
        graph_state.graph = None


def reset_graph() -> None:
    """
    Reset module-level graph state so the graph will be recreated on next access.
    
    Clears the cached graph instance and any configured graph factory.
    """
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """
    Initialize the global AssetRelationshipGraph using the configured factory or environment-backed data sources.
    
    If a factory is set on graph_state, its result is returned. Otherwise, if the environment variable GRAPH_CACHE_PATH is set a RealDataFetcher is created with that path (network access enabled when USE_REAL_DATA_FETCHER is enabled) and its real database is returned. If GRAPH_CACHE_PATH is not set but USE_REAL_DATA_FETCHER is enabled, REAL_DATA_CACHE_PATH is used to create a RealDataFetcher with network access and its real database is returned. If none of those conditions apply, a sample in-memory graph is returned.
    
    Returns:
        AssetRelationshipGraph: The initialized graph instance.
    """
    if graph_state.graph_factory is not None:
        return graph_state.graph_factory()

    cache_path = os.getenv("GRAPH_CACHE_PATH")
    use_real_data = _should_use_real_data_fetcher()

    if cache_path:
        fetcher = RealDataFetcher(
            cache_path=cache_path,
            enable_network=use_real_data,
        )
        return fetcher.create_real_database()

    if use_real_data:
        cache_path_env = os.getenv("REAL_DATA_CACHE_PATH")
        fetcher = RealDataFetcher(
            cache_path=cache_path_env,
            enable_network=True,
        )
        return fetcher.create_real_database()

    return create_sample_database()


def _should_use_real_data_fetcher() -> bool:
    """
    Determine whether to use the real data fetcher based on the USE_REAL_DATA_FETCHER environment variable.

    Treats the values "1", "true", "yes", and "on" (case-insensitive, surrounding whitespace ignored) as enabled.

    Returns:
        bool: `True` if USE_REAL_DATA_FETCHER is set to one of the enabled values, `False` otherwise.
    """
    flag = os.getenv("USE_REAL_DATA_FETCHER", "false")
    return flag.strip().lower() in {"1", "true", "yes", "on"}

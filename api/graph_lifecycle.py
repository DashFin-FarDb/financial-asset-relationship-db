"""Graph lifecycle management for the Financial Asset Relationship API.

This module provides thread-safe initialization and management of the global
AssetRelationshipGraph instance used by the API.
"""

import logging
import os
import threading
from typing import Callable, Optional

from src.data.real_data_fetcher import RealDataFetcher
from src.logic.asset_graph import AssetRelationshipGraph

logger = logging.getLogger(__name__)

# Global graph instance with thread-safe initialization and configurable factory
graph: Optional[AssetRelationshipGraph] = None
graph_factory: Optional[Callable[[], AssetRelationshipGraph]] = None
graph_lock = threading.Lock()


def get_graph() -> AssetRelationshipGraph:
    """Return the global AssetRelationshipGraph, initializing it if necessary."""
    global graph
    if graph is None:
        with graph_lock:
            if graph is None:
                graph = _initialize_graph()
                logger.info("Graph initialized successfully")
    return graph


def set_graph(graph_instance: AssetRelationshipGraph) -> None:
    """Set the global graph to the provided AssetRelationshipGraph."""
    global graph, graph_factory
    with graph_lock:
        graph = graph_instance
        graph_factory = None


def set_graph_factory(factory: Optional[Callable[[], AssetRelationshipGraph]]) -> None:
    """Set the callable used to construct the global AssetRelationshipGraph."""
    global graph, graph_factory
    with graph_lock:
        graph_factory = factory
        graph = None


def reset_graph() -> None:
    """
    Clear the global graph and any configured factory so the graph will be reinitialised on next access.

    This removes any existing graph instance and clears the graph factory.
    """
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """
    Construct the asset relationship graph using the configured factory or environment-backed data sources.

    If a `graph_factory` is configured it is invoked. Otherwise, if `GRAPH_CACHE_PATH` is set a real-data graph is created (network access enabled when `USE_REAL_DATA_FETCHER` indicates real data should be used). If `GRAPH_CACHE_PATH` is not set but `USE_REAL_DATA_FETCHER` is true, `REAL_DATA_CACHE_PATH` is consulted to create a real-data graph. If neither real-data path nor real-data mode is available, a sample database graph is returned.

    Returns:
        AssetRelationshipGraph: The initialized graph instance.
    """
    if graph_factory is not None:
        return graph_factory()

    cache_path = os.getenv("GRAPH_CACHE_PATH")
    use_real_data = _should_use_real_data_fetcher()

    if cache_path:
        fetcher = RealDataFetcher(cache_path=cache_path, enable_network=use_real_data)
        return fetcher.create_real_database()

    if use_real_data:
        cache_path_env = os.getenv("REAL_DATA_CACHE_PATH")
        fetcher = RealDataFetcher(cache_path=cache_path_env, enable_network=True)
        return fetcher.create_real_database()

    from src.data.sample_data import create_sample_database

    return create_sample_database()


def _should_use_real_data_fetcher() -> bool:
    """
    Decides whether the application should use the real data fetcher based on the `USE_REAL_DATA_FETCHER` environment variable.

    Returns:
        `True` if `USE_REAL_DATA_FETCHER` is set to a truthy value (`1`, `true`, `yes`, `on`), `False` otherwise.
    """
    flag = os.getenv("USE_REAL_DATA_FETCHER", "false")
    return flag.strip().lower() in {"1", "true", "yes", "on"}

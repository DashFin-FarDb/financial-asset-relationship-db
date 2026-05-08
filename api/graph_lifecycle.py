"""Graph lifecycle management for the Financial Asset Relationship API.

This module provides thread-safe initialization and management of the global
AssetRelationshipGraph instance used by the API.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable

from src.logic.asset_graph import AssetRelationshipGraph

from . import graph_lifecycle_providers
from .api_models import GraphStartupSource

logger = logging.getLogger(__name__)

# Global graph instance with thread-safe initialization and configurable
# factory.


class _GraphState:
    """Mutable container for module graph lifecycle state."""

    def __init__(self) -> None:
        """Create empty graph lifecycle state."""
        self.graph: AssetRelationshipGraph | None = None
        self.graph_factory: Callable[[], AssetRelationshipGraph] | None = None
        self.startup_source: GraphStartupSource | None = None


graph_state = _GraphState()
graph_lock = threading.Lock()


def get_graph() -> AssetRelationshipGraph:
    """Get the module-global graph, initializing it when needed."""
    graph, _startup_source = get_graph_with_startup_source()
    return graph


def get_graph_with_startup_source() -> tuple[AssetRelationshipGraph, GraphStartupSource | None]:
    """Return the module-global graph and its tracked startup source atomically."""
    with graph_lock:
        if graph_state.graph is None:
            graph, startup_source = _initialize_graph_with_source()
            graph_state.graph = graph
            graph_state.startup_source = startup_source
            logger.info("Graph initialized successfully")

        if graph_state.graph is None:
            raise RuntimeError("Global graph initialization failed; graph is None.")

        return graph_state.graph, graph_state.startup_source


def set_graph(graph_instance: AssetRelationshipGraph) -> None:
    """Register a global graph instance returned by get_graph()."""
    with graph_lock:
        graph_state.graph = graph_instance
        graph_state.graph_factory = None
        graph_state.startup_source = "unknown"


def synchronize_runtime_graph(graph_instance: AssetRelationshipGraph) -> None:
    """Set graph lifecycle state and mirror it into legacy api.main."""
    with graph_lock:
        graph_state.graph = graph_instance
        graph_state.graph_factory = None
        graph_state.startup_source = "unknown"

        api_main = sys.modules.get("api.main")
        if api_main is not None and hasattr(api_main, "graph"):
            api_main.graph = graph_instance


def set_graph_factory(
    factory: Callable[[], AssetRelationshipGraph] | None,
) -> None:
    """Configure the callable used to lazily construct the global graph."""
    with graph_lock:
        graph_state.graph_factory = factory
        graph_state.graph = None
        graph_state.startup_source = None


def reset_graph() -> None:
    """
    Reset module-level graph state so the graph will be recreated on next access.

    Clears the cached graph instance, any configured graph factory, and the
    settings cache to ensure environment variable changes are observed on the
    next initialization.
    """
    # Clear settings cache to preserve reset semantics: environment variable
    # changes made after reset should be picked up on next initialization.
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """Initialize and return a graph without mutating lifecycle state."""
    graph, _startup_source = _initialize_graph_with_source()
    return graph


def _initialize_graph_with_source() -> tuple[AssetRelationshipGraph, GraphStartupSource]:
    """
    Initialize a graph and return the selected startup source.

    Precedence:
    1. custom graph factory;
    2. persisted graph when durable persistence is configured and populated;
    3. graph cache path;
    4. real-data fetcher;
    5. sample graph.

    Configured persistence failures raise RuntimeError.
    """
    if graph_state.graph_factory is not None:
        return graph_state.graph_factory(), "explicit_factory"

    settings = graph_lifecycle_providers.get_graph_lifecycle_settings()
    persisted_graph = graph_lifecycle_providers.load_persisted_graph_if_available(settings.asset_graph_database_url)
    if persisted_graph is not None:
        logger.info("Graph startup source: persisted_graph_store")
        return persisted_graph, "persisted_graph_store"

    cache_path = settings.graph_cache_path
    use_real_data = settings.use_real_data_fetcher

    if cache_path:
        graph = graph_lifecycle_providers.load_graph_from_cache_path(
            cache_path,
            enable_network=use_real_data,
        )
        return graph, "cache"

    if use_real_data:
        real_data_cache_path = settings.real_data_cache_path
        graph = graph_lifecycle_providers.load_graph_from_real_data_fetcher(
            real_data_cache_path,
        )
        return graph, "real_data"

    logger.info("Graph startup source: sample_graph")
    return graph_lifecycle_providers.create_sample_graph(), "sample_graph"

"""Graph lifecycle management for the Financial Asset Relationship API.

This module provides thread-safe initialization and management of the global
AssetRelationshipGraph instance used by the API.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

from src.logic.asset_graph import AssetRelationshipGraph

from . import graph_lifecycle_providers

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


def synchronize_runtime_graph(graph_instance: AssetRelationshipGraph) -> None:
    """
    Set the module-wide AssetRelationshipGraph and mirror it into the legacy api.main if present.

    This registers the provided graph as the global lifecycle graph (clearing any configured factory so subsequent retrievals return this instance). If a loaded module named `api.main` exposes a `graph` attribute, that attribute is updated to the same instance to maintain compatibility with older callers that import `api.main`.

    Parameters:
        graph_instance (AssetRelationshipGraph): The graph instance to register as the global lifecycle graph and to mirror to `api.main.graph` when available.
    """
    with graph_lock:
        graph_state.graph = graph_instance
        graph_state.graph_factory = None

        api_main = sys.modules.get("api.main")
        if api_main is not None and hasattr(api_main, "graph"):
            setattr(api_main, "graph", graph_instance)


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
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
    set_graph_factory(None)


def _initialize_graph() -> AssetRelationshipGraph:
    """
    Initialize the graph from the configured startup source.

    Precedence:
    1. custom graph factory;
    2. persisted graph when durable persistence is configured and populated;
    3. graph cache path;
    4. real-data fetcher;
    5. sample graph.

    Configured persistence failures raise RuntimeError.
    """
    if graph_state.graph_factory is not None:
        return graph_state.graph_factory()

    settings = graph_lifecycle_providers.get_graph_lifecycle_settings()
    persisted_graph = graph_lifecycle_providers.load_persisted_graph_if_available(settings.asset_graph_database_url)
    if persisted_graph is not None:
        return persisted_graph

    cache_path = settings.graph_cache_path
    use_real_data = settings.use_real_data_fetcher

    if cache_path:
        return graph_lifecycle_providers.load_graph_from_cache_path(
            cache_path,
            enable_network=use_real_data,
        )

    if use_real_data:
        real_data_cache_path = settings.real_data_cache_path
        return graph_lifecycle_providers.load_graph_from_real_data_fetcher(
            real_data_cache_path,
        )

    return graph_lifecycle_providers.create_sample_graph()

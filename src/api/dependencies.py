"""Shared FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph


@lru_cache(maxsize=1)
def _get_cached_graph() -> AssetRelationshipGraph:
    """
    Create and return the application's single shared AssetRelationshipGraph instance cached across calls.

    The first invocation initializes and caches the graph; subsequent calls return the cached instance.

    Returns:
        AssetRelationshipGraph: The shared AssetRelationshipGraph instance.
    """
    return create_sample_database()


def get_graph() -> AssetRelationshipGraph:
    """
    Return the module's shared AssetRelationshipGraph.

    Returns:
        AssetRelationshipGraph: The shared cached graph instance.
    """
    return _get_cached_graph()

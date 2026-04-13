"""Shared FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph


@lru_cache(maxsize=1)
def _get_cached_graph() -> AssetRelationshipGraph:
    """
    Create and cache a single shared AssetRelationshipGraph instance for the application.
    
    The first call initializes the graph; subsequent calls return the same cached instance.
    
    Returns:
        AssetRelationshipGraph: The shared AssetRelationshipGraph instance.
    """
    return create_sample_database()


def get_graph() -> AssetRelationshipGraph:
    """
    Provide access to the module's shared AssetRelationshipGraph.
    
    Returns:
        AssetRelationshipGraph: The shared cached graph instance created on first call.
    """
    return _get_cached_graph()

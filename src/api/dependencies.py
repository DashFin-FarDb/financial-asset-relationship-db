"""Shared FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph


@lru_cache(maxsize=1)
def _get_cached_graph() -> AssetRelationshipGraph:
    """
    Create and cache a single shared AssetRelationshipGraph instance.
    
    Returns:
        AssetRelationshipGraph: The cached graph instance returned on subsequent calls.
    """
    return create_sample_database()


def get_graph() -> AssetRelationshipGraph:
    """
    Provide the module's shared AssetRelationshipGraph instance.
    
    Returns:
        graph (AssetRelationshipGraph): The cached shared graph instance; created and cached on first call.
    """
    return _get_cached_graph()

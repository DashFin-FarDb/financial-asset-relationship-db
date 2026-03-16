"""Shared FastAPI dependency providers."""

from __future__ import annotations

from functools import lru_cache

from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph


@lru_cache(maxsize=1)
def _get_cached_graph() -> AssetRelationshipGraph:
    """Create and cache a single shared graph instance."""
    return create_sample_database()


def get_graph() -> AssetRelationshipGraph:
    """Return the shared graph, initializing it once on first call."""
    return _get_cached_graph()

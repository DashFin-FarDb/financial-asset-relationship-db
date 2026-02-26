"""Shared FastAPI dependency providers."""

from __future__ import annotations

from typing import Optional

from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph

_graph: Optional[AssetRelationshipGraph] = None


def get_graph() -> AssetRelationshipGraph:
    """Return the shared AssetRelationshipGraph, initialising it once on first call."""
    global _graph
    if _graph is None:
        _graph = create_sample_database()
    return _graph

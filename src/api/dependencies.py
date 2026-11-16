"""Shared FastAPI dependency providers."""

from __future__ import annotations

from api.graph_lifecycle import get_graph as get_lifecycle_graph
from src.logic.asset_graph import AssetRelationshipGraph


def get_graph() -> AssetRelationshipGraph:
    """Return the authoritative lifecycle AssetRelationshipGraph.

    Returns:
        AssetRelationshipGraph: The active lifecycle graph instance.

    Raises:
        AuthoritativeGraphUnavailableError: If no authoritative published graph is available.
    """
    return get_lifecycle_graph()

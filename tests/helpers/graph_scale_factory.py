"""Deterministic representative-scale graph factory for integration tests."""

from __future__ import annotations

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


def build_scale_graph(*, asset_count: int, relationship_count: int, prefix: str = "SCALE") -> AssetRelationshipGraph:
    """Build a deterministic graph with unique directed relationships."""
    if asset_count <= 0:
        raise ValueError("asset_count must

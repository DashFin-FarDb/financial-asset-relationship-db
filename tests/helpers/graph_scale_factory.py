"""Deterministic representative-scale graph factory for integration tests."""

from __future__ import annotations

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


def build_scale_graph(
    *,
    asset_count: int,
    relationship_count: int,
    prefix: str = "SCALE",
) -> AssetRelationshipGraph:
    """Build a deterministic graph with unique directed relationships."""
    if asset_count < 2:
        raise ValueError("asset_count must be at least 2")
    if relationship_count > asset_count * (asset_count - 1):
        raise ValueError("relationship_count exceeds the unique directed-pair capacity")

    graph = AssetRelationshipGraph()

    for index in range(asset_count):
        asset_id = f"{prefix}_ASSET_{index:05d}"
        graph.add_asset(
            Equity(
                id=asset_id,
                symbol=f"{prefix}{index}",
                name=f"{prefix} Equity {index}",
                asset_class=AssetClass.EQUITY,
                sector="Technology" if index % 2 == 0 else "Financials",
                price=100.0 + index,
            )
        )

    for index in range(relationship_count):
        source_index = index % asset_count
        offset = (index // asset_count) + 1
        target_index = (source_index + offset) % asset_count
        if target_index == source_index:
            target_index = (target_index + 1) % asset_count

        graph.add_relationship(
            f"{prefix}_ASSET_{source_index:05d}",
            f"{prefix}_ASSET_{target_index:05d}",
            "scale_test_link",
            ((index % 100) + 1) / 100,
        )

    return graph

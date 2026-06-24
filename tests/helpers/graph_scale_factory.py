"""Deterministic representative-scale graph factory used by integration tests."""

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


def build_scale_graph(*, asset_count: int, relationship_count: int, prefix: str = "SCALE") -> AssetRelationshipGraph:
    """Build a deterministic graph with an exact number of directed relationships for scale validation."""
    if asset_count <= 0:
        raise ValueError("asset_count must be greater than zero")
    if relationship_count < 0:
        raise ValueError("relationship_count must be non-negative")

    capacity = asset_count * (asset_count - 1)
    if relationship_count > capacity:
        raise ValueError("relationship_count exceeds unique directed relationship capacity")

    graph = AssetRelationshipGraph()

    for index in range(asset_count):
        asset_id = f"{prefix}_ASSET_{index:05d}"
        graph.add_asset(
            Equity(
                id=asset_id,
                symbol=f"{prefix}{index}",
                name=f"{prefix} Equity {index}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + index,
            )
        )

    edge_index = 0
    for offset in range(1, asset_count):
        for source_index in range(asset_count):
            if edge_index == relationship_count:
                return graph
            source = f"{prefix}_ASSET_{source_index:05d}"
            target = f"{prefix}_ASSET_{(source_index + offset) % asset_count:05d}"
            strength = ((edge_index % 100) + 1) / 100
            graph.add_relationship(source, target, ("scale_test_link", strength))
            edge_index += 1

    return graph

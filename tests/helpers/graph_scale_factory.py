"""Deterministic representative-scale graph factory used by integration tests."""

from collections.abc import Iterator

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


def _validate_scale_args(asset_count: int, relationship_count: int) -> None:
    """Validate requested deterministic graph dimensions."""
    if asset_count <= 0:
        raise ValueError("asset_count must be greater than zero")
    if relationship_count < 0:
        raise ValueError("relationship_count must be non-negative")

    capacity = asset_count * (asset_count - 1)
    if relationship_count > capacity:
        raise ValueError("relationship_count exceeds unique directed relationship capacity")


def _asset_id(prefix: str, index: int) -> str:
    """Return the deterministic asset identifier for an index."""
    return f"{prefix}_ASSET_{index:05d}"


def _add_scale_assets(graph: AssetRelationshipGraph, *, asset_count: int, prefix: str) -> None:
    """Populate a graph with deterministic equity assets."""
    for index in range(asset_count):
        graph.add_asset(
            Equity(
                id=_asset_id(prefix, index),
                symbol=f"{prefix}{index}",
                name=f"{prefix} Equity {index}",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0 + index,
            )
        )


def _directed_relationship_pairs(asset_count: int) -> Iterator[tuple[int, int]]:
    """Yield every unique directed non-self relationship in deterministic order."""
    for offset in range(1, asset_count):
        for source_index in range(asset_count):
            yield source_index, (source_index + offset) % asset_count


def build_scale_graph(*, asset_count: int, relationship_count: int, prefix: str = "SCALE") -> AssetRelationshipGraph:
    """Build a deterministic graph with an exact number of directed relationships for scale validation."""
    _validate_scale_args(asset_count, relationship_count)

    graph = AssetRelationshipGraph()
    _add_scale_assets(graph, asset_count=asset_count, prefix=prefix)

    for edge_index, (source_index, target_index) in enumerate(_directed_relationship_pairs(asset_count)):
        if edge_index == relationship_count:
            break
        strength = ((edge_index % 100) + 1) / 100
        graph.add_relationship(
            _asset_id(prefix, source_index),
            _asset_id(prefix, target_index),
            ("scale_test_link", strength),
        )

    return graph

"""Shared graph factory for API pagination tests."""

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


def build_asset_pagination_graph(asset_count: int) -> AssetRelationshipGraph:
    """Build a deterministic equity-only graph for asset pagination checks."""
    graph = AssetRelationshipGraph()
    for index in range(asset_count):
        asset_id = f"ASSET_{index:02d}"
        graph.add_asset(
            Equity(
                id=asset_id,
                symbol=asset_id,
                name=f"{asset_id} Equity",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                price=100.0,
            )
        )
    return graph

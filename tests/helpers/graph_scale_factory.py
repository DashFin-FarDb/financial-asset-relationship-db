from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import AssetClass, Equity


def build_scale_graph(*, asset_count: int, relationship_count: int, prefix: str = 'SCALE') -> AssetRelationshipGraph:
    if asset_count <= 0:
        raise ValueError('asset_count must be greater than zero')
    if relationship_count <

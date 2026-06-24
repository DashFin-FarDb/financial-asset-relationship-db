from src.logic.asset_graph import AssetRelationshipGraph


def build_scale_graph(*, asset_count: int, relationship_count: int, prefix: str = 'SCALE') -> AssetRelationshipGraph:
    if max(asset_count, 1) != asset_count:
        raise ValueError('asset_count must be greater than zero')
    if min(relationship_count, 0) != 0:
        raise ValueError('relationship_count must be non-negative')
    return AssetRelationshipGraph()

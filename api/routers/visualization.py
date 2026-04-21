import math
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.logic.asset_graph import AssetRelationshipGraph

from ..api_models import VisualizationDataResponse
from ..router_helpers import (
    _ASSET_CLASS_COLORS,
    _DEFAULT_COLOR,
    get_graph,
    logger,
)

router = APIRouter()


def _calculate_node_degrees(g: AssetRelationshipGraph) -> Dict[str, int]:
    degree: Dict[str, int] = {asset_id: 0 for asset_id in g.assets.keys()}
    for source_id, rels in g.relationships.items():
        degree[source_id] = degree.get(source_id, 0) + len(rels)
    return degree


def _compute_fibonacci_position(
    idx: int,
    total_nodes: int,
    golden_ratio: float,
) -> tuple[float, float, float]:
    if total_nodes <= 1:
        return 0.0, 0.0, 0.0
    theta = math.acos(1 - 2 * (idx + 0.5) / total_nodes)
    phi = 2 * math.pi * idx / golden_ratio
    x = math.sin(theta) * math.cos(phi)
    y = math.sin(theta) * math.sin(phi)
    z = math.cos(theta)
    return x, y, z


def _build_visualization_nodes(
    g: AssetRelationshipGraph,
    asset_ids: List[str],
) -> List[Dict[str, Any]]:
    degree = _calculate_node_degrees(g)
    total_nodes = len(asset_ids)
    golden_ratio = (1 + math.sqrt(5)) / 2
    nodes: List[Dict[str, Any]] = []
    for idx, asset_id in enumerate(asset_ids):
        asset = g.assets[asset_id]
        x, y, z = _compute_fibonacci_position(idx, total_nodes, golden_ratio)
        asset_class_val = asset.asset_class.value
        nodes.append(
            {
                "id": asset_id,
                "symbol": asset.symbol,
                "name": asset.name,
                "asset_class": asset_class_val,
                "x": round(x, 6),
                "y": round(y, 6),
                "z": round(z, 6),
                "color": _ASSET_CLASS_COLORS.get(asset_class_val, _DEFAULT_COLOR),
                "size": max(5, min(20, 5 + degree.get(asset_id, 0) * 2)),
            }
        )
    return nodes


def _build_visualization_edges(g: AssetRelationshipGraph) -> List[Dict[str, Any]]:
    return [
        {
            "source": source_id,
            "target": target_id,
            "relationship_type": rel_type,
            "strength": strength,
        }
        for source_id, rels in g.relationships.items()
        for target_id, rel_type, strength in rels
    ]


@router.get("/api/visualization", response_model=VisualizationDataResponse)
async def get_visualization_data() -> VisualizationDataResponse:
    try:
        g = get_graph()
        asset_ids = list(g.assets.keys())
        nodes = _build_visualization_nodes(g, asset_ids)
        edges = _build_visualization_edges(g)
        return VisualizationDataResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.exception("Error getting visualization data:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

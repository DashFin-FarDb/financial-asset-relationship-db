"""Graph, metrics, and visualization API endpoints."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from api.graph_lifecycle import get_graph
from api.models import MetricsResponse, RelationshipResponse, VisualizationDataResponse
from src.models.financial_models import AssetClass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["graph"])


@router.get(
    "/relationships",
    response_model=List[RelationshipResponse],
    responses={
        500: {
            "description": "Internal server error while listing relationships.",
            "content": {
                "application/json": {"example": {"detail": ("An internal error occurred. Please try again later.")}}
            },
        },
    },
)
async def get_all_relationships():
    """
    List all directed relationships in the initialized asset graph.

    Returns:
        List[RelationshipResponse]: List of relationships where each item
        contains `source_id`, `target_id`, `relationship_type`, and
        `strength`.
    """
    try:
        g = get_graph()
        relationships: List[RelationshipResponse] = []

        for source_id, rels in g.relationships.items():
            for target_id, rel_type, strength in rels:
                relationships.append(
                    RelationshipResponse(
                        source_id=source_id,
                        target_id=target_id,
                        relationship_type=rel_type,
                        strength=strength,
                    )
                )
    except Exception as e:  # noqa: BLE001
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting relationships:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e
    else:
        return relationships


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    responses={
        500: {
            "description": "Internal server error while computing metrics.",
            "content": {
                "application/json": {"example": {"detail": ("An internal error occurred. Please try again later.")}}
            },
        },
    },
)
async def get_metrics():
    """
    Aggregate network metrics and counts of assets by asset class.

    Returns:
        MetricsResponse: Aggregated metrics including:
            - total_assets: total number of assets.
            - total_relationships: total number of directed relationships.
            - asset_classes: dict mapping asset class name (str) to asset
              count (int).
            - avg_degree: average node degree (float).
            - max_degree: maximum node degree (int).
            - network_density: network density (float).
            - relationship_density: relationship density (float).

    Raises:
        HTTPException: with status code 500 if metrics cannot be obtained.
    """
    try:
        g = get_graph()
        metrics = g.calculate_metrics()

        # Count assets by class
        asset_classes: Dict[str, int] = {}
        for asset in g.assets.values():
            class_name = asset.asset_class.value
            asset_classes[class_name] = asset_classes.get(class_name, 0) + 1

        total_assets = metrics.get("total_assets", 0)
        total_relationships = metrics.get("total_relationships", 0)
        relationship_density = metrics.get("relationship_density", 0.0)

        # Compute degree metrics from graph data directly
        degrees = {src: len(rels) for src, rels in g.relationships.items()}
        avg_degree = total_relationships / total_assets if total_assets > 0 else 0.0
        max_degree = max(degrees.values()) if degrees else 0

        return MetricsResponse(
            total_assets=total_assets,
            total_relationships=total_relationships,
            asset_classes=asset_classes,
            avg_degree=avg_degree,
            max_degree=max_degree,
            network_density=relationship_density / 100.0,
            relationship_density=relationship_density / 100.0,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Error getting metrics:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e


@router.get(
    "/visualization",
    response_model=VisualizationDataResponse,
    responses={
        500: {
            "description": ("Internal server error while building visualization data."),
            "content": {
                "application/json": {"example": {"detail": ("An internal error occurred. Please try again later.")}}
            },
        },
    },
)
async def get_visualization_data():
    """
    Provide nodes and edges prepared for 3D visualization of the asset graph.

    Builds a list of node dictionaries (each with id, name, symbol,
    asset_class, x, y, z, color, size) and a list of edge dictionaries
    (each with source, target, relationship_type, strength) suitable for
    the API response.

    Returns:
        VisualizationDataResponse: An object with `nodes` (list of node
        dicts) and `edges` (list of edge dicts).

    Raises:
        HTTPException: If visualization data cannot be retrieved or
        processed; results in a 500 status with the error detail.
    """
    try:
        g = get_graph()
        # get_3d_visualization_data_enhanced returns:
        # (positions, asset_ids, colors, hover_texts)
        positions, asset_ids, asset_colors, _ = g.get_3d_visualization_data_enhanced()
        nodes: List[Dict[str, Any]] = []
        for i, asset_id in enumerate(asset_ids):
            asset = g.assets[asset_id]
            nodes.append(
                {
                    "id": asset_id,
                    "name": asset.name,
                    "symbol": asset.symbol,
                    "asset_class": asset.asset_class.value,
                    "x": float(positions[i, 0]),
                    "y": float(positions[i, 1]),
                    "z": float(positions[i, 2]),
                    "color": asset_colors[i],
                    "size": 5,
                }
            )

        edges: List[Dict[str, Any]] = []
        # Build edges directly from graph.relationships to avoid rebuilding
        # from intermediate data structures. Only include edges where both
        # source and target are in the asset_ids list.
        asset_id_set = set(asset_ids)
        for source_id in g.relationships:
            if source_id not in asset_id_set:
                continue
            for target_id, rel_type, strength in g.relationships[source_id]:
                if target_id in asset_id_set:
                    edges.append(
                        {
                            "source": source_id,
                            "target": target_id,
                            "relationship_type": rel_type,
                            "strength": float(strength),
                        }
                    )

        return VisualizationDataResponse(nodes=nodes, edges=edges)
    except Exception as e:  # noqa: BLE001
        logger.exception("Error getting visualization data:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e


@router.get(
    "/asset-classes",
    responses={
        200: {
            "description": "List of available asset classes.",
        },
    },
)
async def get_asset_classes():
    """
    List available asset classes.

    Returns:
        Dict[str, List[str]]: A mapping with key "asset_classes" whose
        value is a list of asset class string values.
    """
    return {"asset_classes": [ac.value for ac in AssetClass]}


@router.get(
    "/sectors",
    responses={
        200: {
            "description": "List of unique sector names.",
        },
        500: {
            "description": ("Internal server error while retrieving sectors."),
            "content": {
                "application/json": {"example": {"detail": ("An internal error occurred. Please try again later.")}}
            },
        },
    },
)
async def get_sectors():
    """
    List unique sector names present in the global asset graph in sorted
    order.

    Returns:
        Dict[str, List[str]]: Mapping with key "sectors" to a sorted list
        of unique sector names.

    Raises:
        HTTPException: Raised with status code 500 if an unexpected error
        occurs while retrieving sectors.
    """
    try:
        g = get_graph()
        sectors = {asset.sector for asset in g.assets.values() if asset.sector}
        return {"sectors": sorted(sectors)}
    except Exception as e:  # noqa: BLE001
        logger.exception("Error getting sectors:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

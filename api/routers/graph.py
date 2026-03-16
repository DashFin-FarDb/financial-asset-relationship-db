"""Graph, metrics, and visualization API endpoints."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from api.graph_lifecycle import get_graph
from api.models import MetricsResponse, RelationshipResponse, VisualizationDataResponse
from src.models.financial_models import AssetClass

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["graph"])


def _build_visualization_nodes(
    graph: Any,
    positions: Any,
    asset_ids: List[str],
    asset_colors: List[str],
) -> List[Dict[str, Any]]:
    """
    Construct visualization node payloads for the given assets.

    Each node dictionary contains:
    - `id`: asset identifier string
    - `name`: asset display name
    - `symbol`: asset ticker or symbol
    - `asset_class`: asset class name string
    - `x`, `y`, `z`: 3D coordinates as floats
    - `color`: color string for the node
    - `size`: node size (fixed at 5)

    Parameters:
        graph: Object providing access to assets via `graph.assets[asset_id]`.
        positions: Array-like of shape (N, 3) with 3D coordinates corresponding to `asset_ids`.
        asset_ids (List[str]): Ordered list of asset ids to include in the visualization.
        asset_colors (List[str]): Color strings aligned with `asset_ids`.

    Returns:
        List[Dict[str, Any]]: List of node dictionaries suitable for the visualization response.
    """
    nodes: List[Dict[str, Any]] = []
    for i, asset_id in enumerate(asset_ids):
        asset = graph.assets[asset_id]
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
    return nodes


def _build_visualization_edges(
    relationships: Dict[str, List[Any]],
    allowed_asset_ids: set[str],
) -> List[Dict[str, Any]]:
    """
    Constructs visualization edge dictionaries for relationships whose source and target are both in the allowed asset set.

    Parameters:
        relationships (Dict[str, List[Any]]): Mapping from source asset id to a list of relationship tuples of the form (target_id, relationship_type, strength).
        allowed_asset_ids (set[str]): Set of asset ids that should be included as nodes in the visualization.

    Returns:
        List[Dict[str, Any]]: List of edge dictionaries with keys `source`, `target`, `relationship_type`, and `strength` (float).
    """
    edges: List[Dict[str, Any]] = []
    for source_id, rels in relationships.items():
        if source_id in allowed_asset_ids:
            _append_allowed_edges(
                edges=edges,
                source_id=source_id,
                rels=rels,
                allowed_asset_ids=allowed_asset_ids,
            )
    return edges


def _append_allowed_edges(
    *,
    edges: List[Dict[str, Any]],
    source_id: str,
    rels: List[Any],
    allowed_asset_ids: set[str],
) -> None:
    """
    Append edges for a source to `edges` only when the target is in `allowed_asset_ids`.

    Iterates over `rels`, and for each (target_id, rel_type, strength) tuple whose target is allowed,
    appends a dictionary with keys `source`, `target`, `relationship_type`, and `strength` to the
    provided `edges` list. The `strength` value is converted to a `float`. This function mutates
    `edges` in place.

    Parameters:
        edges (List[Dict[str, Any]]): The list to append edge dictionaries to.
        source_id (str): The source asset identifier for all appended edges.
        rels (List[Any]): An iterable of relationship tuples in the form (target_id, rel_type, strength).
        allowed_asset_ids (set[str]): Set of asset ids that are permitted as edge targets.
    """
    for target_id, rel_type, strength in rels:
        if target_id in allowed_asset_ids:
            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "relationship_type": rel_type,
                    "strength": float(strength),
                }
            )


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
async def get_all_relationships() -> List[RelationshipResponse]:
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
async def get_metrics() -> MetricsResponse:
    """
    Aggregate graph metrics and counts of assets by asset class.

    Returns:
        MetricsResponse: Object with the following fields:
            - total_assets: total number of assets.
            - total_relationships: total number of directed relationships.
            - asset_classes: dict mapping asset class name (str) to asset count (int).
            - avg_degree: average node degree (float).
            - max_degree: maximum node degree (int).
            - network_density: network density as a fraction (float).
            - relationship_density: relationship density as a fraction (float).

    Raises:
        HTTPException: If metrics cannot be obtained (results in a 500 internal server error).
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
async def get_visualization_data() -> VisualizationDataResponse:
    """
    Provides node and edge payloads for 3D visualization of the asset graph.

    Returns:
        VisualizationDataResponse: Response containing `nodes` (list of node dicts with keys `id`, `name`, `symbol`, `asset_class`, `x`, `y`, `z`, `color`, `size`) and `edges` (list of edge dicts with keys `source`, `target`, `relationship_type`, `strength`).

    Raises:
        HTTPException: If an internal error occurs while retrieving or processing visualization data (results in a 500 status).
    """
    try:
        g = get_graph()
        positions, asset_ids, asset_colors, _ = g.get_3d_visualization_data_enhanced()
        nodes = _build_visualization_nodes(g, positions, asset_ids, asset_colors)
        edges = _build_visualization_edges(g.relationships, set(asset_ids))

        return VisualizationDataResponse(
            nodes=nodes,
            edges=edges,
        )
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
async def get_asset_classes() -> Dict[str, List[str]]:
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
async def get_sectors() -> Dict[str, List[str]]:
    """
    Return the unique sector names present in the global asset graph, sorted alphabetically.

    Returns:
        Dict[str, List[str]]: A mapping with the key "sectors" to a sorted list of unique sector names.

    Raises:
        HTTPException: With status code 500 if an unexpected error occurs while retrieving sectors.
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

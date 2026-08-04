"""Visualization API routes."""

from __future__ import annotations

import hashlib
import json
import logging
import math

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError as PydanticValidationError

from src.governance.relationship_assertion import ValidationError
from src.logic.asset_graph import AssetRelationshipGraph, calculate_graph_density
from src.observability.facade import ObservabilityEvent, log_event

from ..api_models import VisualizationDataResponse, VisualizationEdge, VisualizationNode
from ..assertion_models import PublishedProjectionContextResponse
from ..router_helpers import (
    _ASSET_CLASS_COLORS,
    _DEFAULT_COLOR,
    get_graph,
    logger,
)
from ..services.relationship_index import (
    PublishedProjectionContext,
    PublishedRelationshipSnapshot,
    load_governed_relationship_snapshot,
)

router = APIRouter()


def _calculate_node_degrees(g: AssetRelationshipGraph) -> dict[str, int]:
    """Return outgoing relationship counts for every graph asset."""
    degree: dict[str, int] = dict.fromkeys(g.assets.keys(), 0)
    for source_id, rels in g.relationships.items():
        degree[source_id] = degree.get(source_id, 0) + len(rels)
    return degree


def _compute_fibonacci_position(
    idx: int,
    total_nodes: int,
    golden_ratio: float,
) -> tuple[float, float, float]:
    """Return a deterministic Fibonacci-sphere position for one node."""
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
    asset_ids: list[str],
) -> list[VisualizationNode]:
    """Build visualization nodes with deterministic positions and degree sizes."""
    degree = _calculate_node_degrees(g)
    total_nodes = len(asset_ids)
    golden_ratio = (1 + math.sqrt(5)) / 2
    nodes: list[VisualizationNode] = []
    for idx, asset_id in enumerate(asset_ids):
        asset = g.assets[asset_id]
        x, y, z = _compute_fibonacci_position(idx, total_nodes, golden_ratio)
        asset_class_val = asset.asset_class.value
        nodes.append(
            VisualizationNode(
                id=asset_id,
                symbol=asset.symbol,
                name=asset.name,
                asset_class=asset_class_val,
                x=round(x, 6),
                y=round(y, 6),
                z=round(z, 6),
                color=_ASSET_CLASS_COLORS.get(asset_class_val, _DEFAULT_COLOR),
                size=max(5, min(20, 5 + degree.get(asset_id, 0) * 2)),
            )
        )
    return nodes


def _build_visualization_edges(
    g: AssetRelationshipGraph,
    snapshot: PublishedRelationshipSnapshot,
) -> list[VisualizationEdge]:
    """Build visualization edges with optional published governance metadata."""
    governed_index = snapshot.governance_index
    publication = snapshot.publication
    projection_bindings = snapshot.projection_bindings
    edges: list[VisualizationEdge] = []
    for source_id, rels in g.relationships.items():
        for target_id, rel_type, strength in rels:
            relationship_key = (source_id, target_id, rel_type)
            payload: dict[str, object] = {
                "source": source_id,
                "target": target_id,
                "relationship_type": rel_type,
                "strength": strength,
            }
            metadata = governed_index.get(relationship_key)
            if metadata is not None:
                binding = projection_bindings.get(relationship_key)
                if publication is None or binding is None:
                    raise HTTPException(
                        status_code=503,
                        detail="Graph publication metadata is inconsistent",
                    )
                payload.update(metadata)
                payload["projection_edge_id"] = binding.projection_edge_id
                payload["edge_id"] = (
                    f"published:{publication.publication_id}:edge:{binding.projection_edge_id}:{binding.orientation}"
                )
            else:
                payload["edge_id"] = _legacy_edge_id(source_id, target_id, rel_type)
            edges.append(VisualizationEdge.model_validate(payload))
    return edges


def _legacy_edge_id(source_id: str, target_id: str, relationship_type: str) -> str:
    """Return a deterministic, direction-sensitive legacy edge identifier."""
    payload = json.dumps([source_id, target_id, relationship_type], separators=(",", ":"), ensure_ascii=False)
    return f"legacy:{hashlib.sha256(payload.encode('utf-8')).hexdigest().lower()}"


def _publication_response(
    publication: PublishedProjectionContext | None,
) -> PublishedProjectionContextResponse | None:
    """Convert publication snapshot context into API response shape."""
    if publication is None:
        return None
    return PublishedProjectionContextResponse.from_source(publication)


@router.get(
    "/api/visualization",
    response_model_exclude_none=True,
    responses={503: {"description": "Graph publication metadata is inconsistent or database is unavailable"}},
)
async def get_visualization_data() -> VisualizationDataResponse:
    """
    Produce visualization nodes and edges for the current asset relationship graph.

    Returns:
        VisualizationDataResponse: Object containing `nodes` (list of node dictionaries)
            and `edges` (list of edge dictionaries).

    Raises:
        HTTPException: Raised with status code 500 when an internal error prevents assembling the visualization data.
    """
    try:
        g = get_graph()
        asset_ids = list(g.assets.keys())
        nodes = _build_visualization_nodes(g, asset_ids)
        snapshot = load_governed_relationship_snapshot(g)
        edges = _build_visualization_edges(g, snapshot)
        effective_assets_count = len(asset_ids)
        network_density = calculate_graph_density(effective_assets_count, len(edges))
        return VisualizationDataResponse(
            nodes=nodes,
            edges=edges,
            network_density=network_density,
            publication=_publication_response(snapshot.publication),
        )
    except HTTPException:
        raise
    except (ValidationError, PydanticValidationError, ValueError) as e:
        raise HTTPException(
            status_code=503,
            detail="Graph publication metadata is inconsistent",
        ) from e
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="api_get_visualization_data_failed",
                message=f"Error getting visualization data: {type(e).__name__}",
                metadata={"error": type(e).__name__},
            ),
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

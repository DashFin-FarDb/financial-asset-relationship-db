"""Visualization API routes."""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, HTTPException

from src.data.database import create_engine_from_url, create_session_factory
from src.data.relationship_assertion_repository import RelationshipAssertionRepository
from src.data.repository import session_scope
from src.governance.relationship_assertion_contract import load_contract_bundle
from src.logic.asset_graph import AssetRelationshipGraph, calculate_graph_density
from src.observability.facade import ObservabilityEvent, log_event

from ..api_models import VisualizationDataResponse, VisualizationEdge, VisualizationNode
from ..graph_lifecycle_providers import (
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    resolve_hosted_graph_database_url,
)
from ..router_helpers import (
    _ASSET_CLASS_COLORS,
    _DEFAULT_COLOR,
    get_graph,
    logger,
)

router = APIRouter()
_GRAC_CURRENT_PURPOSE = "financial_graph_current_view"


def _governed_edge_index() -> dict[tuple[str, str, str], dict[str, object]]:
    settings = get_graph_lifecycle_settings()
    engine = None
    try:
        hosted_url = resolve_hosted_graph_database_url(settings)
        fallback_url = getattr(settings, "database_url", None)
        persistence_url = resolve_durable_graph_persistence_url(hosted_url or fallback_url)
        engine = create_engine_from_url(persistence_url)
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            repository = RelationshipAssertionRepository(session)
            published = repository.latest_published_projection(_GRAC_CURRENT_PURPOSE)
            if published is None:
                return {}
            _contract, predicates, _transitions = load_contract_bundle()
            edge_type_scopes: dict[str, list[str]] = {}
            for scope in published.revision.governed_scopes:
                predicate = next((item for item in predicates.predicates if item.id == scope.predicate_id), None)
                if predicate is None:
                    continue
                edge_type_scopes.setdefault(predicate.projection.edge_type, []).append(scope.predicate_id)
            index: dict[tuple[str, str, str], dict[str, object]] = {}
            for edge in published.revision.edges:
                index[(edge.source_id, edge.target_id, edge.edge_type)] = {
                    "assertion_id": edge.assertion_id,
                    "governance_status": "governed",
                    "revision_id": published.revision_id,
                    "scope_refs": sorted(set(edge_type_scopes.get(edge.edge_type, []))),
                }
            return index
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
        return {}
    finally:
        if engine is not None:
            engine.dispose()


def _calculate_node_degrees(g: AssetRelationshipGraph) -> dict[str, int]:
    degree: dict[str, int] = dict.fromkeys(g.assets.keys(), 0)
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
    asset_ids: list[str],
) -> list[VisualizationNode]:
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
    governed_index: dict[tuple[str, str, str], dict[str, object]],
) -> list[VisualizationEdge]:
    return [
        VisualizationEdge(
            source=source_id,
            target=target_id,
            relationship_type=rel_type,
            strength=strength,
            assertion_id=(governed_index.get((source_id, target_id, rel_type)) or {}).get("assertion_id"),  # type: ignore[arg-type]
            governance_status=(governed_index.get((source_id, target_id, rel_type)) or {}).get("governance_status"),  # type: ignore[arg-type]
            revision_id=(governed_index.get((source_id, target_id, rel_type)) or {}).get("revision_id"),  # type: ignore[arg-type]
            scope_refs=(governed_index.get((source_id, target_id, rel_type)) or {}).get("scope_refs"),  # type: ignore[arg-type]
        )
        for source_id, rels in g.relationships.items()
        for target_id, rel_type, strength in rels
    ]


@router.get("/api/visualization", response_model=VisualizationDataResponse, response_model_exclude_none=True)
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
        edges = _build_visualization_edges(g, _governed_edge_index())
        effective_assets_count = len(asset_ids)
        network_density = calculate_graph_density(effective_assets_count, len(edges))
        return VisualizationDataResponse(nodes=nodes, edges=edges, network_density=network_density)
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

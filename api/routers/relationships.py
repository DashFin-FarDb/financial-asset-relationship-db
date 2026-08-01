"""Relationship API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.data.database import create_engine_from_url, create_session_factory
from src.data.relationship_assertion_repository import RelationshipAssertionRepository
from src.data.repository import session_scope
from src.governance.relationship_assertion_contract import load_contract_bundle
from src.observability.facade import ObservabilityEvent, log_event

from ..api_models import RelationshipResponse
from ..graph_lifecycle_providers import (
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    resolve_hosted_graph_database_url,
)
from ..router_helpers import get_graph, logger, raise_asset_not_found

router = APIRouter()
_GRAC_CURRENT_PURPOSE = "financial_graph_current_view"


def _governed_relationship_index() -> dict[tuple[str, str, str], dict[str, object]]:
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


@router.get("/api/assets/{asset_id}/relationships", response_model_exclude_none=True)
async def get_asset_relationships(asset_id: str) -> list[RelationshipResponse]:
    """
    Return outgoing relationships for the specified asset.

    Returns:
        list[RelationshipResponse]: A list of relationship objects where each item has `source_id`
            set to the provided `asset_id` and includes `target_id`, `relationship_type`, and `strength`.

    Raises:
        HTTPException: If the asset does not exist (404) or an internal error occurs (500).
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)
        governed_index = _governed_relationship_index()
        return [
            RelationshipResponse(
                source_id=asset_id,
                target_id=target_id,
                relationship_type=rel_type,
                strength=strength,
                assertion_id=(governed_index.get((asset_id, target_id, rel_type)) or {}).get("assertion_id"),  # type: ignore[arg-type]
                governance_status=(governed_index.get((asset_id, target_id, rel_type)) or {}).get("governance_status"),  # type: ignore[arg-type]
                revision_id=(governed_index.get((asset_id, target_id, rel_type)) or {}).get("revision_id"),  # type: ignore[arg-type]
                scope_refs=(governed_index.get((asset_id, target_id, rel_type)) or {}).get("scope_refs"),  # type: ignore[arg-type]
            )
            for target_id, rel_type, strength in g.relationships.get(asset_id, [])
        ]
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="api_get_asset_relationships_failed",
                message=f"Error getting asset relationships: {type(e).__name__}",
                metadata={"asset_id": asset_id, "error": type(e).__name__},
            ),
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e


@router.get("/api/relationships", response_model_exclude_none=True)
async def get_all_relationships() -> list[RelationshipResponse]:
    """
    Retrieve all relationships from the shared graph.

    Each relationship is serialized to a RelationshipResponse with

    `source_id`, `target_id`, `relationship_type`, and `strength`.

    Returns:
        list[RelationshipResponse]: All relationships present in the graph.

    Raises:
        HTTPException: Raised with status code 500 if an internal error occurs while retrieving relationships.
    """
    try:
        g = get_graph()
        governed_index = _governed_relationship_index()
        return [
            RelationshipResponse(
                source_id=source_id,
                target_id=target_id,
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
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="api_get_all_relationships_failed",
                message=f"Error getting all relationships: {type(e).__name__}",
                metadata={"error": type(e).__name__},
            ),
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

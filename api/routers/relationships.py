"""Relationship API routes."""

from __future__ import annotations

import logging
from typing import Literal, TypeAlias, TypedDict

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.engine import Engine

from src.data.database import create_engine_from_url, create_session_factory
from src.data.relationship_assertion_repository import RelationshipAssertionRepository
from src.data.relationship_projection_persistence import PersistedProjectionRevision
from src.data.repository import session_scope
from src.governance.relationship_assertion_contract import PredicatesDocument, load_contract_bundle
from src.logic.relationship_projection import ProjectionEdge
from src.observability.facade import ObservabilityEvent, log_event

from ..api_models import RelationshipResponse
from ..graph_lifecycle_providers import (
    GraphPersistenceInvalidUrlError,
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    resolve_hosted_graph_database_url,
)
from ..router_helpers import get_graph, logger, raise_asset_not_found

router = APIRouter()
_GRAC_CURRENT_PURPOSE = "financial_graph_current_view"


class GovernanceMetadata(TypedDict):
    """Strict governance fields attached to one published relationship edge."""

    assertion_id: str
    governance_status: Literal["governed"]
    revision_id: str
    scope_refs: list[str]


GovernedRelationshipIndex: TypeAlias = dict[tuple[str, str, str], GovernanceMetadata]
GraphRelationship: TypeAlias = tuple[str, str, float]


def _dispose_engine(engine: Engine | None) -> None:
    """Dispose an optional governance persistence engine after each bounded read."""
    if engine is not None:
        engine.dispose()


def _scope_refs_by_edge_type(
    published: PersistedProjectionRevision,
    predicates: PredicatesDocument,
) -> dict[str, list[str]]:
    """Index the published governed predicate scopes by projected edge type."""
    predicates_by_id = {predicate.id: predicate for predicate in predicates.predicates}
    edge_type_scopes: dict[str, list[str]] = {}
    for scope in published.revision.governed_scopes:
        predicate = predicates_by_id.get(scope.predicate_id)
        if predicate is not None:
            edge_type_scopes.setdefault(predicate.projection.edge_type, []).append(scope.predicate_id)
    return edge_type_scopes


def _add_governed_edge(
    index: GovernedRelationshipIndex,
    edge: ProjectionEdge,
    metadata: GovernanceMetadata,
) -> None:
    """Add forward and, when governed as bidirectional, reverse index entries."""
    index[(edge.source_id, edge.target_id, edge.edge_type)] = metadata
    if edge.direction == "bidirectional":
        index[(edge.target_id, edge.source_id, edge.edge_type)] = metadata


def _published_relationship_index(
    published: PersistedProjectionRevision,
    predicates: PredicatesDocument,
) -> GovernedRelationshipIndex:
    """Build governance response metadata for one published projection revision."""
    edge_type_scopes = _scope_refs_by_edge_type(published, predicates)
    index: GovernedRelationshipIndex = {}
    for edge in published.revision.edges:
        metadata: GovernanceMetadata = {
            "assertion_id": edge.assertion_id,
            "governance_status": "governed",
            "revision_id": published.revision_id,
            "scope_refs": sorted(set(edge_type_scopes.get(edge.edge_type, []))),
        }
        _add_governed_edge(index, edge, metadata)
    return index


def load_governed_relationship_index() -> GovernedRelationshipIndex:
    """Load metadata for the latest published governed relationship projection."""
    settings = get_graph_lifecycle_settings()
    engine: Engine | None = None
    try:
        hosted_url = resolve_hosted_graph_database_url(settings)
        legacy_url = (
            getattr(settings, "database_url", None) if not hasattr(settings, "asset_graph_database_url") else None
        )
        persistence_url = resolve_durable_graph_persistence_url(hosted_url or legacy_url)
        engine = create_engine_from_url(persistence_url)
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            repository = RelationshipAssertionRepository(session)
            published = repository.latest_published_projection(_GRAC_CURRENT_PURPOSE)
            if published is None:
                return {}
            _contract, predicates, _transitions = load_contract_bundle()
            return _published_relationship_index(published, predicates)
    except GraphPersistenceInvalidUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database is misconfigured",
        ) from exc
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
        return {}
    finally:
        _dispose_engine(engine)


def _relationship_response(
    source_id: str,
    relationship: GraphRelationship,
    governed_index: GovernedRelationshipIndex,
) -> RelationshipResponse:
    """Build one relationship response with at most one governance-index lookup."""
    target_id, relationship_type, strength = relationship
    payload: dict[str, object] = {
        "source_id": source_id,
        "target_id": target_id,
        "relationship_type": relationship_type,
        "strength": strength,
    }
    metadata = governed_index.get((source_id, target_id, relationship_type))
    if metadata is not None:
        payload.update(metadata)
    return RelationshipResponse.model_validate(payload)


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
        governed_index = load_governed_relationship_index()
        return [
            _relationship_response(asset_id, relationship, governed_index)
            for relationship in g.relationships.get(asset_id, [])
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
        governed_index = load_governed_relationship_index()
        return [
            _relationship_response(source_id, relationship, governed_index)
            for source_id, rels in g.relationships.items()
            for relationship in rels
        ]
    except HTTPException:
        raise
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

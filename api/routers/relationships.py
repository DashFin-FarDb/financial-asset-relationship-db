"""Relationship API routes."""

from __future__ import annotations

import logging
from typing import TypeAlias

from fastapi import APIRouter, HTTPException

from src.observability.facade import ObservabilityEvent, log_event

from ..api_models import RelationshipResponse
from ..router_helpers import get_graph, logger, raise_asset_not_found
from ..services.relationship_index import (
    GovernedRelationshipIndex,
    load_governed_relationship_index,
)

router = APIRouter()
GraphRelationship: TypeAlias = tuple[str, str, float]


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
        governed_index = load_governed_relationship_index(g)
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
        governed_index = load_governed_relationship_index(g)
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

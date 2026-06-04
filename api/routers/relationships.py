"""Relationship API routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

from ..api_models import RelationshipResponse
from ..router_helpers import get_graph, logger, raise_asset_not_found

router = APIRouter()


@router.get("/api/assets/{asset_id}/relationships")
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
        return [
            RelationshipResponse(
                source_id=asset_id,
                target_id=target_id,
                relationship_type=rel_type,
                strength=strength,
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


@router.get("/api/relationships")
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
        return [
            RelationshipResponse(
                source_id=source_id,
                target_id=target_id,
                relationship_type=rel_type,
                strength=strength,
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

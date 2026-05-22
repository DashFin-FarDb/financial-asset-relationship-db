"""Relationship API routes."""

from fastapi import APIRouter, HTTPException

from ..api_models import RelationshipResponse
from ..router_helpers import get_graph, logger, raise_asset_not_found

router = APIRouter()


@router.get("/api/assets/{asset_id}/relationships")
async def get_asset_relationships(asset_id: str) -> list[RelationshipResponse]:
    """Return outgoing relationships for a single asset."""
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
        logger.exception("Error getting asset relationships:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e


@router.get("/api/relationships")
async def get_all_relationships() -> list[RelationshipResponse]:
    """Return all graph relationships."""
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
        logger.exception("Error getting all relationships:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

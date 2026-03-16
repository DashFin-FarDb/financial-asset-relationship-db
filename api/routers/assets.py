"""Asset-related API endpoints."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from api.graph_lifecycle import get_graph
from api.models import AssetResponse, RelationshipResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["assets"])


def raise_asset_not_found(asset_id: str, resource_type: str = "Asset") -> None:
    """
    Raise HTTPException for missing resources.

    Args:
        asset_id (str): ID of the asset that was not found.
        resource_type (str): Type of resource (default: "Asset").
    """
    raise HTTPException(
        status_code=404,
        detail=f"{resource_type} {asset_id} not found",
    )


def serialize_asset(asset: Any, include_issuer: bool = False) -> Dict[str, Any]:
    """
    Serialize an Asset object to a dictionary representation.

    Args:
        asset: Asset object to serialize
        include_issuer: Whether to include issuer_id field (for detail views)

    Returns:
        Dictionary containing asset data with additional_fields
    """
    asset_dict = {
        "id": asset.id,
        "symbol": asset.symbol,
        "name": asset.name,
        "asset_class": asset.asset_class.name,
        "sector": asset.sector,
        "price": asset.price,
        "market_cap": asset.market_cap,
        "currency": asset.currency,
        "additional_fields": {},
    }

    # Define field list
    fields = [
        "pe_ratio",
        "dividend_yield",
        "earnings_per_share",
        "book_value",
        "yield_to_maturity",
        "coupon_rate",
        "maturity_date",
        "credit_rating",
        "contract_size",
        "delivery_date",
        "volatility",
        "exchange_rate",
        "country",
        "central_bank_rate",
    ]

    if include_issuer:
        fields.append("issuer_id")

    # Add asset-specific fields
    for field in fields:
        if hasattr(asset, field):
            value = getattr(asset, field)
            if value is not None:
                asset_dict["additional_fields"][field] = value

    return asset_dict


def _matches_filters(
    asset: Any,
    *,
    asset_class_upper: Optional[str],
    sector: Optional[str],
) -> bool:
    """Return whether an asset passes optional class and sector filters."""
    if asset_class_upper:
        asset_class_name = asset.asset_class.name
        asset_class_value = asset.asset_class.value.upper()
        if asset_class_name != asset_class_upper and asset_class_value != asset_class_upper:
            return False

    if sector and asset.sector != sector:
        return False

    return True


def _build_filtered_asset_responses(
    graph: Any,
    *,
    asset_class: Optional[str],
    sector: Optional[str],
) -> List[AssetResponse]:
    """Build serialized AssetResponse list for assets matching filters."""
    asset_class_upper = asset_class.upper() if asset_class else None
    responses: List[AssetResponse] = []
    for asset in graph.assets.values():
        if not _matches_filters(
            asset,
            asset_class_upper=asset_class_upper,
            sector=sector,
        ):
            continue
        responses.append(AssetResponse(**serialize_asset(asset)))
    return responses


@router.get(
    "/assets",
    response_model=List[AssetResponse],
    responses={
        500: {
            "description": "Internal server error while listing assets.",
            "content": {
                "application/json": {"example": {"detail": ("An internal error occurred. Please try again later.")}}
            },
        },
    },
)
async def get_assets(
    asset_class: Optional[str] = None,
    sector: Optional[str] = None,
):
    """
    List assets, optionally filtered by asset class and sector.

    Parameters:
        asset_class (Optional[str]): Filter to include only assets matching
            this asset class. Accepts either the enum name (e.g., "EQUITY")
            or value (e.g., "Equity"), case-insensitive.
        sector (Optional[str]): Filter to include only assets whose
            `sector` equals this string.

    Returns:
        List[AssetResponse]: AssetResponse objects matching the filters.
        Each object's `additional_fields` contains any non-null,
        asset-type-specific attributes as defined in the respective asset
        model classes.
    """
    try:
        g = get_graph()
        assets = _build_filtered_asset_responses(
            g,
            asset_class=asset_class,
            sector=sector,
        )
    except Exception as e:  # noqa: BLE001
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting assets:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e
    else:
        return assets


@router.get(
    "/assets/{asset_id}",
    response_model=AssetResponse,
    responses={
        404: {
            "description": "Asset not found.",
            "content": {"application/json": {"example": {"detail": "Asset not found."}}},
        },
        500: {
            "description": "Internal server error while retrieving asset.",
            "content": {
                "application/json": {"example": {"detail": ("An internal error occurred. Please try again later.")}}
            },
        },
    },
)
async def get_asset_detail(asset_id: str):
    """
    Retrieve detailed information for the asset identified by `asset_id`.

    Parameters:
        asset_id (str): Identifier of the asset whose details are requested.

    Returns:
        AssetResponse: Detailed asset information as defined in the
        AssetResponse model, including core fields and an `additional_fields`
        map containing any asset-specific attributes that are present and
        non-null.

    Raises:
        HTTPException: 404 if the asset is not found.
        HTTPException: 500 for unexpected errors while retrieving the asset.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)

        asset = g.assets[asset_id]

        # Build response using serialization utility with issuer_id included
        asset_dict = serialize_asset(asset, include_issuer=True)
        return AssetResponse(**asset_dict)
    except Exception as e:  # noqa: BLE001
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset detail:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e


@router.get(
    "/assets/{asset_id}/relationships",
    response_model=List[RelationshipResponse],
    responses={
        404: {
            "description": "Asset not found.",
            "content": {"application/json": {"example": {"detail": "Asset not found."}}},
        },
        500: {
            "description": ("Internal server error while retrieving asset relationships."),
            "content": {
                "application/json": {"example": {"detail": ("An internal error occurred. Please try again later.")}}
            },
        },
    },
)
async def get_asset_relationships(asset_id: str):
    """
    List outgoing relationships for the specified asset.

    Parameters:
        asset_id (str): Identifier of the asset whose outgoing relationships
            are requested.

    Returns:
        List[RelationshipResponse]: Outgoing relationship records for the
        asset (each with source_id, target_id, relationship_type, and
        strength).

    Raises:
        HTTPException: 404 if the asset is not found; 500 for unexpected
        errors.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)

        relationships: List[RelationshipResponse] = []

        # Outgoing relationships
        if asset_id in g.relationships:
            for target_id, rel_type, strength in g.relationships[asset_id]:
                relationships.append(
                    RelationshipResponse(
                        source_id=asset_id,
                        target_id=target_id,
                        relationship_type=rel_type,
                        strength=strength,
                    )
                )
    except Exception as e:  # noqa: BLE001
        if isinstance(e, HTTPException):
            raise
        logger.exception("Error getting asset relationships:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e
    else:
        return relationships

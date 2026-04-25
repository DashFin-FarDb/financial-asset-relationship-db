"""Asset API routes."""


from fastapi import APIRouter, HTTPException

from ..api_models import AssetResponse
from ..router_helpers import (
    get_graph,
    logger,
    raise_asset_not_found,
    serialize_asset,
)

router = APIRouter()


@router.get("/api/assets", response_model=list[AssetResponse])
async def get_assets(
    asset_class: str | None = None,
    sector: str | None = None,
) -> list[AssetResponse]:
    """Return assets filtered by asset class and sector."""
    try:
        g = get_graph()
        assets = []
        for asset in g.assets.values():
            if asset_class and asset.asset_class.value != asset_class:
                continue
            if sector and asset.sector != sector:
                continue
            assets.append(AssetResponse(**serialize_asset(asset)))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting assets:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e
    return assets


@router.get("/api/assets/{asset_id}", response_model=AssetResponse)
async def get_asset_detail(asset_id: str) -> AssetResponse:
    """Return detailed data for a single asset."""
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)
        return AssetResponse(**serialize_asset(g.assets[asset_id], include_issuer=True))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting asset detail:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

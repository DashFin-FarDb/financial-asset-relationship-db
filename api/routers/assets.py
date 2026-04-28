"""Asset API routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..api_models import AssetPageResponse, AssetResponse
from ..router_helpers import (
    get_graph,
    logger,
    raise_asset_not_found,
    serialize_asset,
)

router = APIRouter()


@router.get("/api/assets")
async def get_assets(
    asset_class: str | None = None,
    sector: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=1000)] = 50,
) -> AssetPageResponse:
    """Return a paginated page of assets filtered by asset class and sector."""
    try:
        g = get_graph()
        assets = []
        for asset in g.assets.values():
            if asset_class and asset.asset_class.value != asset_class:
                continue
            if sector and asset.sector != sector:
                continue
            assets.append(asset)
        assets.sort(key=lambda asset: asset.id)
        total = len(assets)
        start = (page - 1) * per_page
        end = start + per_page
        page_assets = assets[start:end]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting assets:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e
    return AssetPageResponse(
        items=[AssetResponse(**serialize_asset(asset)) for asset in page_assets],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/api/assets/{asset_id}")
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

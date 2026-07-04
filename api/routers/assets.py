"""Asset API routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from src.observability.facade import ObservabilityEvent, log_event

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
    """
    Retrieve a paginated list of assets filtered by optional asset class and sector.

    Parameters:
        asset_class (str | None): If provided, include only assets whose `asset.asset_class.value` equals this string.
        sector (str | None): If provided, include only assets whose `asset.sector` equals this string.
        page (int): 1-based page number.
        per_page (int): Number of items per page (maximum 1000).

    Returns:
        AssetPageResponse: Page containing `items` (serialized assets for the requested page),
            `total` (total matched assets), `page`, `per_page`, and `hasMore`.

    Raises:
        HTTPException: Propagates existing HTTP errors; raises a 500-status `HTTPException`
            on unexpected internal errors.
    """
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
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="api_get_assets_failed",
                message=f"Error getting assets: {type(e).__name__}",
                metadata={"error": type(e).__name__},
            ),
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e
    return AssetPageResponse(
        items=[AssetResponse(**serialize_asset(asset)) for asset in page_assets],
        total=total,
        page=page,
        per_page=per_page,
        has_more=(page * per_page) < total,  # type: ignore[call-arg]
    )


@router.get("/api/assets/{asset_id}")
async def get_asset_detail(asset_id: str) -> AssetResponse:
    """
    Retrieve full details for a single asset, including its issuer.

    Parameters:
        asset_id: The unique identifier of the asset to retrieve.

    Returns:
        AssetResponse: The asset's details with issuer information.

    Raises:
        HTTPException: If the asset does not exist or an internal error occurs.
    """
    try:
        g = get_graph()
        if asset_id not in g.assets:
            raise_asset_not_found(asset_id)
        return AssetResponse(**serialize_asset(g.assets[asset_id], include_issuer=True))
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="api_get_asset_detail_failed",
                message=f"Error getting asset detail: {type(e).__name__}",
                metadata={"asset_id": asset_id, "error": type(e).__name__},
            ),
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

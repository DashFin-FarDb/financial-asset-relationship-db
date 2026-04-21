from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.models.financial_models import AssetClass

from ..main import get_graph, logger

router = APIRouter()


@router.get("/")
async def root() -> Dict[str, Any]:
    return {
        "message": "Financial Asset Relationship API",
        "version": "1.0.0",
        "endpoints": {
            "assets": "/api/assets",
            "asset_detail": "/api/assets/{asset_id}",
            "relationships": "/api/relationships",
            "metrics": "/api/metrics",
            "visualization": "/api/visualization",
        },
    }


@router.get("/api/health")
async def health_check() -> Dict[str, Any]:
    return {"status": "healthy", "graph_initialized": True}


@router.get("/api/asset-classes")
async def get_asset_classes() -> Dict[str, List[str]]:
    try:
        return {"asset_classes": sorted(ac.value for ac in AssetClass)}
    except Exception as e:
        logger.exception("Error getting asset classes:")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/sectors")
async def get_sectors() -> Dict[str, List[str]]:
    try:
        g = get_graph()
        return {"sectors": sorted({a.sector for a in g.assets.values() if a.sector})}
    except Exception as e:
        logger.exception("Error getting sectors:")
        raise HTTPException(status_code=500, detail=str(e)) from e

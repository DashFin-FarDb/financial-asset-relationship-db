"""System and metadata API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException

from src.models.financial_models import AssetClass

from ..api_models import DatabaseHealthResponse, DetailedHealthResponse, GraphHealthResponse
from ..router_helpers import get_graph, logger

router = APIRouter()


@router.get("/")
async def root() -> dict[str, Any]:
    """Return API metadata and key endpoint paths."""
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
async def health_check() -> dict[str, Any]:
    """Return service health status."""
    return {"status": "healthy", "graph_initialized": True}


def _get_graph_health() -> GraphHealthResponse:
    """Return bounded, non-secret graph readiness details."""
    try:
        graph = get_graph()
        relationships = getattr(graph, "relationships", {}) or {}
        return GraphHealthResponse(
            available=True,
            asset_count=len(getattr(graph, "assets", {}) or {}),
            relationship_count=sum(len(items) for items in relationships.values()),
        )
    except Exception:
        logger.exception("Detailed health graph check failed:")
        return GraphHealthResponse(
            available=False,
            asset_count=0,
            relationship_count=0,
        )


def _get_database_health() -> DatabaseHealthResponse:
    """Return bounded, non-secret auth database readiness details."""
    try:
        from api import database

        database_type = getattr(database, "DATABASE_TYPE", "unknown")
        if database_type not in {"sqlite", "postgresql"}:
            database_type = "unknown"

        database.fetch_value("SELECT 1")

        return DatabaseHealthResponse(
            configured=True,
            type=database_type,
            reachable=True,
        )
    except Exception:
        logger.exception("Detailed health database check failed:")
        return DatabaseHealthResponse(
            configured=False,
            type="unknown",
            reachable=False,
        )


@router.get("/api/health/detailed", response_model=DetailedHealthResponse)
def detailed_health_check() -> DetailedHealthResponse:
    """Return bounded, non-secret readiness information for hosted deployment."""
    graph_health = _get_graph_health()
    database_health = _get_database_health()

    status_value = "healthy" if graph_health.available and database_health.reachable else "degraded"

    return DetailedHealthResponse(
        status=status_value,
        graph=graph_health,
        database=database_health,
    )


@router.get("/api/asset-classes")
async def get_asset_classes() -> dict[str, list[str]]:
    """Return sorted asset class names."""
    try:
        return {"asset_classes": sorted(ac.value for ac in AssetClass)}
    except Exception as e:
        logger.exception("Error getting asset classes:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e


@router.get("/api/sectors")
async def get_sectors() -> dict[str, list[str]]:
    """Return sorted distinct sector names from the graph."""
    try:
        g = get_graph()
        return {"sectors": sorted({a.sector for a in g.assets.values() if a.sector})}
    except Exception as e:
        logger.exception("Error getting sectors:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

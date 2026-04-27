"""Metrics API routes."""

from fastapi import APIRouter, HTTPException

from ..api_models import MetricsResponse
from ..router_helpers import get_graph, logger

router = APIRouter()


@router.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Return summary metrics for the asset relationship graph."""
    try:
        g = get_graph()
        metrics = g.calculate_metrics()

        return MetricsResponse(
            total_assets=metrics["total_assets"],
            total_relationships=metrics["total_relationships"],
            asset_classes=metrics["asset_classes"],
            avg_degree=metrics["avg_degree"],
            max_degree=metrics["max_degree"],
            network_density=metrics["network_density"],
            relationship_density=metrics["relationship_density"],
        )
    except Exception as e:
        logger.exception("Error getting metrics:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

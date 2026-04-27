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

        return MetricsResponse.model_validate(metrics)
    except Exception as e:
        logger.exception("Error getting metrics:")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

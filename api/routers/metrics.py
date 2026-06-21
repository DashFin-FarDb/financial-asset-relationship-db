"""Graph metrics API routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.observability.facade import ObservabilityEvent, log_event

from ..api_models import MetricsResponse
from ..router_helpers import get_graph, logger

router = APIRouter()


@router.get("/api/graph/metrics", responses={500: {"description": "Internal server error"}})
async def get_graph_metrics() -> MetricsResponse:
    """
    Retrieve aggregated metrics, distributions, and density for the current asset graph.

    Returns:
        MetricsResponse: The calculated metrics for the graph state.

    Raises:
        HTTPException: Raised with status code 500 if an internal error occurs while calculating metrics.
    """
    try:
        g = get_graph()
        metrics_dict = g.calculate_metrics()
        return MetricsResponse(
            total_assets=metrics_dict["total_assets"],
            total_relationships=metrics_dict["total_relationships"],
            asset_classes=metrics_dict["asset_classes"],
            avg_degree=metrics_dict["avg_degree"],
            max_degree=metrics_dict["max_degree"],
            network_density=metrics_dict["network_density"],
        )
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="api_get_graph_metrics_failed",
                message=f"Error getting graph metrics: {type(e).__name__}",
                metadata={"error": type(e).__name__},
            ),
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Please try again later.",
        ) from e

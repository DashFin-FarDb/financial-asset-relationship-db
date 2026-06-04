"""System and metadata API routes."""

import logging
from typing import Any, Literal, NoReturn, cast

from fastapi import APIRouter, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # pylint: disable=import-error

from src.models.financial_models import AssetClass

from .. import graph_lifecycle
from ..api_models import DatabaseHealthResponse, DetailedHealthResponse, GraphHealthResponse
from ..graph_lifecycle_providers import (
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
)
from ..router_helpers import ObservabilityEvent, get_graph, log_event, logger

router = APIRouter()

SUPPORTED_DATABASE_TYPE = Literal["sqlite", "postgresql"]


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
    """
    Report bounded graph readiness and inventory counts for health checks.

    Reads the application's graph (assets and relationships)

    and returns a GraphHealthResponse containing availability,

    the current runtime lifecycle state, the total number of assets, and the total number of relationships.

    If the graph containers are not dictionary-shaped or an error occurs while reading the graph,

    returns `available=False` with asset and relationship counts set to 0.

    Returns:
        GraphHealthResponse: `available` indicating graph readiness;
        `lifecycle_state` as the current runtime lifecycle state value;
        `asset_count` as the number of assets;
        `relationship_count` as the summed length of relationship collections.
    """
    try:
        graph, _startup_source = graph_lifecycle.get_graph_with_startup_source()
        assets = getattr(graph, "assets", {})
        relationships = getattr(graph, "relationships", {})

        if assets is None:
            assets = {}
        if relationships is None:
            relationships = {}

        if not isinstance(assets, dict) or not isinstance(relationships, dict):
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="health_check_graph_unsupported_shape",
                    message="Detailed health graph check found unsupported graph container shape",
                ),
            )
            return GraphHealthResponse(
                available=False,
                lifecycle_state=graph_lifecycle.get_runtime_lifecycle_state().value,
                asset_count=0,
                relationship_count=0,
            )

        return GraphHealthResponse(
            available=True,
            lifecycle_state=graph_lifecycle.get_runtime_lifecycle_state().value,
            asset_count=len(assets),
            relationship_count=sum(len(items) for items in relationships.values()),
        )
    except Exception:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="health_check_graph_failed",
                message="Detailed health graph check failed",
            ),
        )
        return GraphHealthResponse(
            available=False,
            lifecycle_state=graph_lifecycle.get_runtime_lifecycle_state().value,
            asset_count=0,
            relationship_count=0,
        )


def _get_database_health() -> DatabaseHealthResponse:
    """
    Report whether an auth/database layer is configured and reachable for health checks.

    Returns:
        DatabaseHealthResponse: `configured` is `True` if a supported database type is configured,
        `type` is the detected database type (`"sqlite"`, `"postgresql"`, or `"unknown"`),
        and `reachable` is `True` if a simple connectivity query succeeded,
        `False` otherwise.
    """
    try:
        from api import database
    except Exception:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="health_check_database_config_failed",
                message="Detailed health database configuration check failed",
            ),
        )
        return DatabaseHealthResponse(
            configured=False,
            type="unknown",
            reachable=False,
        )

    database_type_raw = getattr(database, "DATABASE_TYPE", "unknown")
    if database_type_raw not in {"sqlite", "postgresql"}:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="health_check_database_unsupported_type",
                message="Detailed health database check found unsupported database type",
                metadata={"database_type": str(database_type_raw)},
            ),
        )
        return DatabaseHealthResponse(
            configured=False,
            type="unknown",
            reachable=False,
        )

    database_type = cast(SUPPORTED_DATABASE_TYPE, database_type_raw)

    try:
        database.fetch_value("SELECT 1")
    except Exception:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="health_check_database_unreachable",
                message="Detailed health database reachability check failed",
            ),
        )
        return DatabaseHealthResponse(
            configured=True,
            type=database_type,
            reachable=False,
        )

    return DatabaseHealthResponse(
        configured=True,
        type=database_type,
        reachable=True,
    )


def _get_graph_persistence_configured() -> bool:
    """
    Determine whether durable graph persistence is explicitly configured.

    Returns:
        bool: `True` if durable graph persistence is configured, `False` otherwise.
    """
    try:
        settings = get_graph_lifecycle_settings()
        resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        return True
    except (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
    ):
        return False
    except Exception as exc:
        # Removed exc_info=True to prevent leaking connection secrets in tracebacks
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="graph_persistence_config_check_failed",
                message=f"Unexpected error checking graph persistence configuration: {type(exc).__name__}",
                metadata={"error": type(exc).__name__},
            ),
        )
        return False


@router.get("/api/health/detailed")
def detailed_health_check() -> DetailedHealthResponse:
    """Return detailed health including graph persistence configuration."""
    graph_health = _get_graph_health()
    database_health = _get_database_health()

    status_value = "healthy" if graph_health.available and database_health.reachable else "degraded"

    return DetailedHealthResponse(
        status=status_value,
        graph_persistence_configured=_get_graph_persistence_configured(),
        graph=graph_health,
        database=database_health,
    )


@router.get("/api/metrics")
async def metrics() -> Response:
    """
    Expose Prometheus metrics in OpenMetrics format.
    
    Returns:
        Response: HTTP response containing OpenMetrics-formatted metrics with the OpenMetrics media type; on generation failure returns a 500 response with plain-text body "metrics generation error".
    """
    try:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="prometheus_metrics_generation_failed",
                message="Error generating Prometheus metrics; failing scrape request",
                metadata={"error": type(exc).__name__},
            ),
        )
        return Response(status_code=500, content="metrics generation error", media_type="text/plain")


def _raise_system_route_error(message: str, exc: Exception) -> NoReturn:
    """
    Emit a structured observability event for a system-route failure and raise a public HTTP 500 error.
    
    Parameters:
        message (str): Contextual message to include in the observability event.
        exc (Exception): The original exception that triggered the failure.
    
    Raises:
        HTTPException: Always raises an HTTP 500 error with a generic internal-error detail.
    """
    log_event(
        logger,
        logging.ERROR,
        ObservabilityEvent(
            event="system_route_failure",
            message=f"{message} {type(exc).__name__}",
            metadata={"error": type(exc).__name__},
        ),
    )
    raise HTTPException(
        status_code=500,
        detail="An internal error occurred. Please try again later.",
    ) from exc


@router.get("/api/asset-classes")
async def get_asset_classes() -> dict[str, list[str]]:
    """Return sorted asset class names."""
    try:
        return {"asset_classes": sorted(ac.value for ac in AssetClass)}
    except Exception as e:
        _raise_system_route_error("Error getting asset classes:", e)


@router.get("/api/sectors")
async def get_sectors() -> dict[str, list[str]]:
    """Return sorted distinct sector names from the graph."""
    try:
        g = get_graph()
        return {"sectors": sorted({a.sector for a in g.assets.values() if a.sector})}
    except Exception as e:
        _raise_system_route_error("Error getting sectors:", e)

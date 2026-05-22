"""System and metadata API routes."""

from typing import Any, Literal, NoReturn, cast

from fastapi import APIRouter, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # pylint: disable=import-error
from sqlalchemy.exc import ArgumentError  # pylint: disable=import-error

from src.models.financial_models import AssetClass

from .. import graph_lifecycle
from ..api_models import DatabaseHealthResponse, DetailedHealthResponse, GraphHealthResponse
from ..graph_lifecycle_providers import (
    GraphPersistenceInvalidUrlError,
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
)
from ..router_helpers import get_graph, logger

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
    """Return bounded, non-secret graph readiness details."""
    try:
        graph, _startup_source = graph_lifecycle.get_graph_with_startup_source()
        assets = getattr(graph, "assets", {})
        relationships = getattr(graph, "relationships", {})

        if assets is None:
            assets = {}
        if relationships is None:
            relationships = {}

        if not isinstance(assets, dict) or not isinstance(relationships, dict):
            logger.warning("Detailed health graph check found unsupported graph container shape")
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
        logger.warning("Detailed health graph check failed")
        return GraphHealthResponse(
            available=False,
            lifecycle_state=graph_lifecycle.get_runtime_lifecycle_state().value,
            asset_count=0,
            relationship_count=0,
        )


def _get_database_health() -> DatabaseHealthResponse:
    """Return bounded, non-secret auth database readiness details."""
    try:
        from api import database
    except Exception:
        logger.warning("Detailed health database configuration check failed")
        return DatabaseHealthResponse(
            configured=False,
            type="unknown",
            reachable=False,
        )

    database_type_raw = getattr(database, "DATABASE_TYPE", "unknown")
    if database_type_raw not in {"sqlite", "postgresql"}:
        logger.warning("Detailed health database check found unsupported database type")
        return DatabaseHealthResponse(
            configured=False,
            type="unknown",
            reachable=False,
        )

    database_type = cast(SUPPORTED_DATABASE_TYPE, database_type_raw)

    try:
        database.fetch_value("SELECT 1")
    except Exception:
        logger.warning("Detailed health database reachability check failed")
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
    """Return whether durable graph persistence is explicitly configured."""
    try:
        settings = get_graph_lifecycle_settings()
        resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        return True
    except (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
        GraphPersistenceInvalidUrlError,
    ):
        return False
    except Exception as exc:
        # Removed exc_info=True to prevent leaking connection secrets in tracebacks
        logger.error(
            "Unexpected error checking graph persistence configuration: %s",
def _get_graph_persistence_configured() -> bool:
    """Return whether durable graph persistence is explicitly configured."""
    try:
        settings = get_graph_lifecycle_settings()
        resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        return True
    except (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
        GraphPersistenceInvalidUrlError,
    ):
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error checking graph persistence configuration: %s",
            type(exc).__name__,
        )
        return False
        )
        return False

def _get_graph_persistence_configured() -> bool:
    """Return whether durable graph persistence is explicitly configured."""
    try:
        settings = get_graph_lifecycle_settings()
        resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        return True
    except (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
        GraphPersistenceInvalidUrlError,
    ):
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error checking graph persistence configuration: %s",
            type(exc).__name__,
        )
        return False
def detailed_health_check() -> DetailedHealthResponse:
def _get_graph_persistence_configured() -> bool:
    """Return whether durable graph persistence is explicitly configured."""
    try:
        settings = get_graph_lifecycle_settings()
        resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        return True
    except (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
        GraphPersistenceInvalidUrlError,
    ):
        return False
    except Exception as exc:
        logger.error(
            "Unexpected error checking graph persistence configuration: %s",
            type(exc).__name__,
        )
        return False
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
    """Expose Prometheus metrics in OpenMetrics format.

    Returns HTTP 500 on generation errors to fail scrape requests and surface
    operational issues immediately rather than masking them with stale data.
    """
    try:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception:
        logger.exception("Error generating Prometheus metrics; failing scrape request")
        return Response(status_code=500, content="metrics generation error", media_type="text/plain")


def _raise_system_route_error(message: str, exc: Exception) -> NoReturn:
    """Log a system route failure and raise the public internal-error response."""
    logger.exception(message)
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
        _raise_system_route_error("Error getting sectors:", e)
        return {"sectors": sorted({a.sector for a in g.assets.values() if a.sector})}
    except Exception as e:
    except Exception as e:
        _raise_system_route_error("Error getting sectors:", e)

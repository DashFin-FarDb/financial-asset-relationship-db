"""FastAPI backend for the Financial Asset Relationship Database."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Callable, Optional

from fastapi import FastAPI

# pylint: disable=import-error
from slowapi import _rate_limit_exceeded_handler  # type: ignore[import-not-found]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]

from src.config.settings import get_settings
from src.logic.asset_graph import AssetRelationshipGraph

# Backward compatibility re-exports for response models
# noqa: F401 tells flake8 to ignore "imported but unused" warnings
from .api_models import (  # noqa: F401
    AssetResponse,
    MetricsResponse,
    RelationshipResponse,
    VisualizationDataResponse,
)
from .auth import (  # noqa: F401
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)
from .cors_policy import configure_cors, validate_origin  # noqa: F401
from .graph_lifecycle import _initialize_graph as _lifecycle_initialize_graph
from .graph_lifecycle import get_graph as _get_graph
from .graph_lifecycle import reset_graph as _reset_graph
from .graph_lifecycle import set_graph as _set_graph
from .graph_lifecycle import set_graph_factory as _set_graph_factory

# Import and re-export limiter for backward compatibility
from .rate_limit import limiter  # noqa: F401

# Backward compatibility re-exports for helper functions
from .router_helpers import (  # noqa: F401
    raise_asset_not_found,
    serialize_asset,
)
from .routers.assets import router as assets_router
from .routers.auth import router as auth_router
from .routers.metrics import router as metrics_router
from .routers.relationships import router as relationships_router
from .routers.system import router as system_router
from .routers.visualization import router as visualization_router

# Backward compatibility export for older tests and callers.
ENV = get_settings().env

# Backward compatibility graph reference for older tests that patch api.main.graph.
graph = _get_graph()


def _initialize_graph() -> AssetRelationshipGraph:
    """Return a freshly initialized asset relationship graph."""
    return _lifecycle_initialize_graph()


# pylint: enable=import-error

logger = logging.getLogger(__name__)


def get_graph() -> AssetRelationshipGraph:
    """Return the shared asset relationship graph instance."""
    return _get_graph()


def set_graph(graph: AssetRelationshipGraph) -> None:
    """Set the shared asset relationship graph instance."""
    _set_graph(graph)


GraphFactory = Callable[[], AssetRelationshipGraph]


def set_graph_factory(factory: Optional[GraphFactory]) -> None:
    """Set the factory used to build the shared asset relationship graph."""
    _set_graph_factory(factory)


def reset_graph() -> None:
    """Reset the shared asset relationship graph state."""
    _reset_graph()


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """
    Manage application lifespan: initialize the shared asset relationship graph before startup and log shutdown.

    If graph initialization fails, the original exception is propagated to abort application startup.
    Raises:
        Exception: Any error encountered during graph initialization is re-raised to stop startup.
    """
    try:
        get_graph()
        logger.info("Application startup complete - graph initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    yield

    logger.info("Application shutdown")


# Initialise FastAPI app with lifespan handler
app = FastAPI(
    title="Financial Asset Relationship API",
    description="REST API for Financial Asset Relationship Database",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS via extracted policy
configure_cors(app)

app.include_router(auth_router)
app.include_router(system_router)
app.include_router(assets_router)
app.include_router(relationships_router)
app.include_router(metrics_router)
app.include_router(visualization_router)

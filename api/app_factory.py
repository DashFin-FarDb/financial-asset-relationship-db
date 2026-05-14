"""FastAPI application factory for the Financial Asset Relationship Database API.

This module contains the FastAPI application construction, middleware setup,
and router registration logic.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# pylint: disable=import-error
from slowapi import _rate_limit_exceeded_handler  # type: ignore[import-not-found]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]

from .cors_policy import configure_cors
from .graph_lifecycle import (
    GraphRuntimeLifecycleState,
    begin_shutdown,
    get_graph,
    get_runtime_lifecycle_state,
    sync_with_latest_rebuild,
)
from .rate_limit import limiter
from .routers.assets import router as assets_router
from .routers.auth import router as auth_router
from .routers.graph_admin import init_rebuild_executor, shutdown_rebuild_executor
from .routers.graph_admin import router as graph_admin_router
from .routers.relationships import router as relationships_router
from .routers.system import router as system_router
from .routers.visualization import router as visualization_router

# pylint: enable=import-error


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """Initialize graph state and clean up rebuild resources."""
    try:
        get_graph()
        init_rebuild_executor()
        logger.info("Application startup complete - graph and rebuild executor initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    # Start background synchronization task
    sync_task = asyncio.create_task(_run_graph_sync_loop())

    yield

    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        # Expected during shutdown after sync_task.cancel(); suppress intentionally.
        pass
    finally:
        begin_shutdown()
        shutdown_rebuild_executor()
        logger.info("Application shutdown")


async def _run_graph_sync_loop(interval_seconds: int = 60) -> None:
    """Run the graph synchronization loop in the background."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            if get_runtime_lifecycle_state() in (
                GraphRuntimeLifecycleState.SHUTTING_DOWN,
                GraphRuntimeLifecycleState.STOPPED,
            ):
                return
            await asyncio.to_thread(sync_with_latest_rebuild)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - bounded logging below
            logger.warning(
                "Unexpected error in graph synchronization loop: %s",
                type(exc).__name__,
            )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
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
    app.include_router(graph_admin_router)
    app.include_router(assets_router)
    app.include_router(relationships_router)
    app.include_router(visualization_router)

    return app


# Create the application instance
app = create_app()

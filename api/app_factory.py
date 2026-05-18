"""FastAPI application factory for the Financial Asset Relationship Database API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import FastAPI

if TYPE_CHECKING:
    from .graph_lifecycle_providers import GraphLifecycleSettings

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

_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS = 10.0


def _run_startup_reconciliation(settings: GraphLifecycleSettings) -> None:
    """Run database consistency reconciliation during application startup."""
    from src.data.database import create_session_factory, init_db
    from src.data.distributed_lock import DistributedLock
    from src.data.repository import AssetGraphRepository, session_scope
    from src.logic.recovery_gate import RecoveryGate

    from .graph_lifecycle_providers import create_engine_from_url, resolve_durable_graph_persistence_url

    url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
    engine = create_engine_from_url(url)
    try:
        # Schema guarantee runs safely isolated here before gate evaluations
        init_db(engine)
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            lock = DistributedLock(
                session=session,
                lock_id="startup_reconciliation",
                ttl_seconds=_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS,
            )
            gate = RecoveryGate(repo=repo, lock=lock)
            gate.evaluate_and_reconcile()
    finally:
        # Fix: Ensure short-lived startup verification engines are cleanly disposed
        engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application runtime setup and teardown lifecycles cleanly."""
    from src.logic.recovery_gate import ExecutionBlockedError

    from .graph_lifecycle_providers import get_graph_lifecycle_settings

    settings = get_graph_lifecycle_settings()
    has_durable_graph_persistence = bool(getattr(settings, "asset_graph_database_url", None))
    sync_task: asyncio.Task | None = None

    if has_durable_graph_persistence:
        try:
            _run_startup_reconciliation(settings)
        except ExecutionBlockedError as exc:
            logger.critical(
                "Application startup BLOCKED by RecoveryGate safety invariant: %s",
                exc,
                exc_info=True,
            )
            raise exc from None
        except Exception as exc:
            logger.critical(
                "Fatal infrastructure initialization failure during startup: %s",
                type(exc).__name__,
                exc_info=True,
            )
            # Sanitized to hide raw connection string secrets during start crashes
            raise RuntimeError("Failed to load persisted graph during startup") from exc

        init_rebuild_executor(settings)
        interval = getattr(settings, "graph_sync_interval_seconds", 60.0)
        sync_task = asyncio.create_task(_graph_synchronization_loop(interval_seconds=interval))

    # Required initialization for all environments to ensure state validity
    get_graph()

    yield

    logger.info("Initiating orderly application lifespan teardown processing...")
    begin_shutdown()

    if sync_task is not None:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass

    if has_durable_graph_persistence:
        shutdown_rebuild_executor()

    logger.info("Application context lifespan termination finalized successfully.")


async def _graph_synchronization_loop(interval_seconds: float) -> None:
    """Periodically synchronize the memory graph engine with changes from the database."""
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
        except Exception as exc:
            logger.warning(
                "Unexpected transient error in graph synchronization loop: %s",
                type(exc).__name__,
                exc_info=True,
            )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Financial Asset Relationship API",
        description="REST API for Financial Asset Relationship Database",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    configure_cors(app)

    app.include_router(auth_router)
    app.include_router(system_router)
    app.include_router(graph_admin_router)
    app.include_router(assets_router)
    app.include_router(relationships_router)
    app.include_router(visualization_router)

    return app


app = create_app()

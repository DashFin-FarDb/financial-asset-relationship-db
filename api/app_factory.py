"""FastAPI application factory for the Financial Asset Relationship Database API.

This module contains the FastAPI application construction, middleware setup,
and router registration logic.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

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

# Startup reconciliation uses a fixed TTL. GraphLifecycleSettings does not carry
# a configurable lock TTL, so using a reasonable baseline default of 10s.
_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS = 10.0


def _run_startup_reconciliation(settings: GraphLifecycleSettings) -> None:
    """Run database consistency reconciliation during application startup.

    This function sets up a transient transactional scope to check for active
    locks or dirty state markers left over from an ungraceful crash or hard terminating
    sigkill. It coordinates state recovery before background queues spin up.

    Args:
        settings: Initialized GraphLifecycleSettings object.

    Raises:
        ExecutionBlockedError: If the RecoveryGate identifies an unresolvable data
            inconsistency or a distributed lock state that is definitively LOST.
    """
    from src.data.database import create_engine_from_url
    from src.data.distributed_lock import DistributedLock
    from src.data.repository import AssetGraphRepository, session_scope
    from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

    # Ensure database schema initialization runs early inside reconciliation path
    engine = create_engine_from_url(settings.database_url)
    from src.data.database import init_db
    init_db(engine)

    from src.data.database import create_session_factory
    session_factory = create_session_factory(engine)

    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        lock = DistributedLock(
            session=session,
            lock_id="startup_reconciliation",
            ttl_seconds=_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS,
        )
        
        # Enforce structural integrity analysis via recovery gate
        gate = RecoveryGate(repo=repo, lock=lock)
        gate.evaluate_and_reconcile()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application runtime setup and teardown lifecycles cleanly."""
    from .graph_lifecycle_providers import get_graph_lifecycle_settings
    from src.logic.recovery_gate import ExecutionBlockedError

    settings = get_graph_lifecycle_settings()
    has_durable_graph_persistence = settings.has_durable_graph_persistence
    sync_task: asyncio.Task | None = None

    if has_durable_graph_persistence:
        try:
            # 1. Run startup reconciliation and audit safety assertions
            _run_startup_reconciliation(settings)
        except ExecutionBlockedError as exc:
            # CRITICAL: Crash startup cleanly if safety gates block execution invariants
            logger.critical(
                "Application startup BLOCKED by RecoveryGate safety invariant: %s",
                exc,
                exc_info=True,
            )
            raise exc from None
        except Exception as exc:
            # CRITICAL: Prevent boot if migrations or infrastructure layers fail
            logger.critical(
                "Fatal infrastructure initialization failure during startup reconciliation: %s",
                type(exc).__name__,
                exc_info=True,
            )
            raise exc

        # 2. Idempotent secondary database safety verification guard
        from src.data.database import create_engine_from_url, init_db
        try:
            init_db(create_engine_from_url(settings.database_url))
        except Exception as db_exc:
            logger.critical(
                "Failed to verify database schema initialization: %s",
                db_exc,
                exc_info=True,
            )
            raise db_exc

        # 3. Initialize background threading execution pool safely
        init_rebuild_executor(settings)

        # 4. Spawn graph synchronization looping routine
        sync_task = asyncio.create_task(
            _graph_synchronization_loop(
                interval_seconds=settings.graph_sync_interval_seconds
            )
        )

    yield

    # Clean application teardown processing path
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

    # Attach core cross-origin policies
    configure_cors(app)

    # Route configuration registrations
    app.include_router(auth_router)
    app.include_router(system_router)
    app.include_router(graph_admin_router)
    app.include_router(assets_router)
    app.include_router(relationships_router)
    app.include_router(visualization_router)

    return app


# Instantiate the root app layer variable object hook
app = create_app()

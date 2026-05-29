"""FastAPI application factory for the Financial Asset Relationship Database API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import AsyncGenerator
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
from .routers.graph_admin import init_rebuild_executor
from .routers.graph_admin import router as graph_admin_router
from .routers.graph_admin import shutdown_rebuild_executor_sync as shutdown_rebuild_executor
from .routers.relationships import router as relationships_router
from .routers.system import router as system_router
from .routers.visualization import router as visualization_router

# pylint: enable=import-error

logger = logging.getLogger(__name__)

_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS = 10.0


def _get_durable_graph_database_url(settings: GraphLifecycleSettings) -> str | None:
    """Return the configured durable graph persistence URL across old/new settings shapes."""
    return getattr(settings, "asset_graph_database_url", getattr(settings, "database_url", None))


def _resolve_startup_reconciliation_url(settings: GraphLifecycleSettings) -> str:
    """Resolve the startup reconciliation database URL, preserving legacy test seams."""
    database_url = _get_durable_graph_database_url(settings)
    if hasattr(settings, "asset_graph_database_url"):
        from .graph_lifecycle_providers import resolve_durable_graph_persistence_url

        return resolve_durable_graph_persistence_url(database_url)
    if database_url is None:
        raise RuntimeError("Graph persistence is not configured.")
    return database_url


def _run_startup_reconciliation(settings: GraphLifecycleSettings) -> None:
    """Run database consistency reconciliation during application startup."""
    from src.data.database import create_engine_from_url, create_session_factory, init_db
    from src.data.distributed_lock import DistributedLock
    from src.logic.recovery_gate import RecoveryGate

    from .metrics import increment_recovery_trigger

    url = _resolve_startup_reconciliation_url(settings)
    engine = create_engine_from_url(url)

    # Resolve primary-only Coordination Plane (Plane 2) engine and session factory
    coord_url = getattr(settings, "coordination_database_url", None) or url
    coord_engine = create_engine_from_url(coord_url) if coord_url != url else engine

    try:
        # Schema guarantee runs safely isolated here before gate evaluations
        init_db(engine)
        if coord_engine is not engine:
            init_db(coord_engine)

        session_factory = create_session_factory(engine)
        coordination_session_factory = (
            create_session_factory(coord_engine) if coord_engine is not engine else session_factory
        )

        lock = DistributedLock(
            coordination_session_factory=coordination_session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=int(_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS),
        )
        gate = RecoveryGate(
            session_factory=session_factory,
            lock=lock,
            increment_recovery_trigger=increment_recovery_trigger,
            runtime_has_active_executor=False,
            lock_ttl_seconds=int(_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS),
        )
        try:
            if hasattr(gate, "evaluate_and_reconcile"):
                logger.debug("Running evaluate_and_reconcile for startup reconciliation")
                gate.evaluate_and_reconcile()
            else:
                logger.debug("Falling back to ensure_safe_to_execute for startup reconciliation")
                gate.ensure_safe_to_execute()
        finally:
            if getattr(gate, "lock_was_reacquired", False):
                lock.release()
    finally:
        # Ensure short-lived startup verification engines are cleanly disposed
        engine.dispose()
        if coord_engine is not engine:
            coord_engine.dispose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application runtime setup and teardown lifecycles cleanly."""
    from src.logic.recovery_gate import ExecutionBlockedError

    from .graph_lifecycle_providers import get_graph_lifecycle_settings

    settings = get_graph_lifecycle_settings()
    database_url = _get_durable_graph_database_url(settings)
    has_durable_graph_persistence = bool(getattr(settings, "has_durable_graph_persistence", None) or database_url)
    sync_task: asyncio.Task | None = None

    if has_durable_graph_persistence:
        try:
            _run_startup_reconciliation(settings)
        except ExecutionBlockedError as exc:
            if exc.action == "wait" and exc.inconsistency_type == "none":
                logger.info(
                    "Benign clean-install detected on startup (action=wait, inconsistency=none). "
                    "Proceeding with startup."
                )
            else:
                logger.critical(
                    "Application startup BLOCKED by RecoveryGate safety invariant: %s",
                    type(exc).__name__,
                    exc_info=False,
                )
                logger.debug(
                    "Safety invariant traceback details",
                    exc_info=True,
                )
                raise exc from None
        except Exception as exc:
            logger.error(
                "Failed to load persisted graph during startup: %s",
                exc.__class__.__name__,
            )
            raise RuntimeError("Failed to load persisted graph during startup") from None

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
        with contextlib.suppress(asyncio.CancelledError):  # NOSONAR
            await sync_task

    if has_durable_graph_persistence:
        shutdown_rebuild_executor()

    logger.info("Application context lifespan termination finalized successfully.")


async def _graph_synchronization_loop(interval_seconds: float) -> None:
    """Periodically synchronize the memory graph engine with changes from the database."""
    current_interval = max(1.0, float(interval_seconds))
    is_in_error_state = False
    max_interval = 3600.0  # Cap backoff at 1 hour

    while True:
        try:
            await asyncio.sleep(current_interval)
            if get_runtime_lifecycle_state() in (
                GraphRuntimeLifecycleState.SHUTTING_DOWN,
                GraphRuntimeLifecycleState.STOPPED,
            ):
                return
            await asyncio.to_thread(sync_with_latest_rebuild)

            # Reset on successful sync
            if is_in_error_state:
                logger.info("Database connection restored.")
                is_in_error_state = False
            current_interval = interval_seconds
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not is_in_error_state:
                logger.warning(
                logger.warning(
                    "Unexpected transient error in graph synchronization loop (%s): %s. Engaging backoff policy.",
                    type(exc).__name__,
                    str(exc),
                    exc_info=True,
                )
logger.warning(
    "Unexpected transient error in graph synchronization loop (%s): %s. Engaging backoff policy.",
    type(exc).__name__,
    str(exc),
    exc_info=True,
)
            # Exponential backoff: double the interval, capped at max_interval
            current_interval = min(current_interval * 2, max_interval)
            # Add randomized jitter (0 to 10% of current interval) to avoid retry storms
            jitter = random.uniform(0, 0.1 * current_interval)
            await asyncio.sleep(jitter)


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

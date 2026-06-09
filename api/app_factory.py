"""FastAPI application factory for the Financial Asset Relationship Database API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

if TYPE_CHECKING:
    from .graph_lifecycle_providers import GraphLifecycleSettings

# pylint: disable=import-error
from slowapi import _rate_limit_exceeded_handler  # type: ignore[import-not-found]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]

from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event
from src.observability.logging import setup_logging

from .cors_policy import configure_cors
from .graph_lifecycle import (
    GraphRuntimeLifecycleState,
    begin_shutdown,
    get_graph,
    get_runtime_lifecycle_state,
    sync_with_latest_rebuild,
)
from .middleware.correlation import CorrelationMiddleware
from .middleware.request_metrics import RequestMetricsMiddleware
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
    """Initialize persisted graph state during application startup."""
    from src.data.database import create_engine_from_url

    url = _resolve_startup_reconciliation_url(settings)
    engine = create_engine_from_url(url)

    # Resolve primary-only Coordination Plane (Plane 2) engine
    coord_url = getattr(settings, "coordination_database_url", None) or url
    coord_engine = create_engine_from_url(coord_url) if coord_url != url else engine

    try:
        _init_reconciliation_schemas(engine, coord_engine)
        _execute_recovery_gate(engine, coord_engine)
    finally:
        # Ensure short-lived startup verification engines are cleanly disposed
        engine.dispose()
        if coord_engine is not engine:
            coord_engine.dispose()


def _init_reconciliation_schemas(engine: Any, coord_engine: Any) -> None:
    """Initialize database schemas for reconciliation."""
    from src.data.database import init_db

    init_db(engine)
    if coord_engine is not engine:
        init_db(coord_engine)


def _execute_recovery_gate(engine: Any, coord_engine: Any) -> None:
    """Acquire lock and execute recovery gate evaluation."""
    from src.data.database import create_session_factory
    from src.data.distributed_lock import DistributedLock
    from src.logic.recovery_gate import RecoveryGate

    from .metrics import increment_recovery_trigger

    session_factory = create_session_factory(engine)
    coord_session_factory = create_session_factory(coord_engine) if coord_engine is not engine else session_factory

    lock = DistributedLock(
        coordination_session_factory=coord_session_factory,
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
            gate.evaluate_and_reconcile()
        else:
            gate.ensure_safe_to_execute()
    finally:
        if getattr(gate, "lock_was_reacquired", False):
            lock.release()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown tasks for the FastAPI application."""
    from .graph_lifecycle_providers import get_graph_lifecycle_settings

    settings = get_graph_lifecycle_settings()
    database_url = _get_durable_graph_database_url(settings)
    has_persistence_flag = getattr(settings, "has_durable_graph_persistence", None)
    has_persistence = bool(has_persistence_flag) if has_persistence_flag is not None else bool(database_url)

    if has_persistence:
        await _perform_startup_reconciliation(settings)

    sync_task, slo_task = _start_background_tasks(has_persistence, settings)

    # Required initialization for all environments to ensure state validity
    get_graph()

    yield

    await _perform_orderly_shutdown(sync_task, slo_task, has_persistence)


async def _perform_startup_reconciliation(settings: GraphLifecycleSettings) -> None:
    """Run startup reconciliation with timeout and error handling."""
    from src.logic.recovery_gate import ExecutionBlockedError

    try:
        try:
            await asyncio.wait_for(asyncio.to_thread(_run_startup_reconciliation, settings), timeout=120)
        except asyncio.TimeoutError:
            log_event(
                logger,
                logging.CRITICAL,
                ObservabilityEvent(
                    event="startup_reconciliation_timeout",
                    message="Startup reconciliation timed out after 120s",
                ),
            )
            raise RuntimeError("Startup reconciliation timed out") from None
    except ExecutionBlockedError as exc:
        _handle_reconciliation_blocked(exc)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="startup_reconciliation_failed",
                message=f"Failed to load persisted graph during startup: {exc.__class__.__name__}",
                metadata={"error": exc.__class__.__name__},
            ),
        )
        raise RuntimeError("Failed to load persisted graph during startup") from None


def _handle_reconciliation_blocked(exc: Any) -> None:
    """Handle ExecutionBlockedError from RecoveryGate."""
    if exc.action == "wait" and exc.inconsistency_type == "none":
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="startup_reconciliation_benign_clean_install",
                message=(
                    "Benign clean-install detected on startup (action=wait, inconsistency=none). "
                    "Proceeding with startup."
                ),
            ),
        )
    else:
        log_event(
            logger,
            logging.CRITICAL,
            ObservabilityEvent(
                event="startup_reconciliation_blocked",
                message=f"Application startup BLOCKED by RecoveryGate safety invariant: {type(exc).__name__}",
                metadata={"error": type(exc).__name__},
            ),
        )
        raise exc from None


def _start_background_tasks(
    has_persistence: bool, settings: GraphLifecycleSettings
) -> tuple[asyncio.Task | None, asyncio.Task]:
    """Initialize and start background synchronization and SLO tasks."""
    sync_task: asyncio.Task | None = None
    if has_persistence:
        init_rebuild_executor(settings)
        interval = getattr(settings, "graph_sync_interval_seconds", 60.0)
        sync_task = asyncio.create_task(_graph_synchronization_loop(interval_seconds=interval))

    slo_task = asyncio.create_task(_slo_evaluation_loop())
    return sync_task, slo_task


async def _perform_orderly_shutdown(
    sync_task: asyncio.Task | None, slo_task: asyncio.Task, has_persistence: bool
) -> None:
    """Initiate orderly shutdown of background tasks and executors."""
    log_event(
        logger,
        logging.INFO,
        ObservabilityEvent(
            event="application_teardown_initiated",
            message="Initiating orderly application lifespan teardown processing...",
        ),
    )
    begin_shutdown()

    if sync_task is not None:
        sync_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):  # NOSONAR
            await sync_task

    slo_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):  # NOSONAR
        await slo_task

    if has_persistence:
        shutdown_rebuild_executor()

    log_event(
        logger,
        logging.INFO,
        ObservabilityEvent(
            event="application_teardown_completed",
            message="Application context lifespan termination finalized successfully.",
        ),
    )


async def _graph_synchronization_loop(interval_seconds: float) -> None:
    """
    Continuously synchronize the in-memory graph with persistent rebuild updates until shutdown.
    """
    base_interval = max(1.0, float(interval_seconds))
    current_interval = base_interval
    max_interval = base_interval * 32  # cap at 32× base interval
    is_in_error_state = False

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
                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="graph_sync_database_connection_restored",
                        message="Database connection restored.",
                    ),
                )
                is_in_error_state = False
            current_interval = base_interval

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not is_in_error_state:
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="graph_sync_transient_error",
                        message=(
                            f"Unexpected transient error in graph synchronization loop ({type(exc).__name__}). "
                            "Engaging backoff policy."
                        ),
                        metadata={"error": type(exc).__name__},
                    ),
                )
                is_in_error_state = True

            # Exponential backoff + randomized jitter applied cleanly to the next cycle
            backoff = min(current_interval * 2, max_interval)
            jitter = random.uniform(0, 0.1 * backoff)
            current_interval = min(backoff + jitter, max_interval)


async def _slo_evaluation_loop() -> None:
    """
    Periodically evaluate SLOs and update Prometheus metrics and logs.
    Includes exponential backoff on failures and checks lifecycle state.
    """
    from src.config.settings import get_settings

    from .slo_evaluator import SLOEvaluator

    settings = get_settings()
    base_interval = settings.slo_evaluation_interval_seconds
    current_interval = base_interval
    max_interval = base_interval * 32

    evaluator = SLOEvaluator(settings=settings)

    while True:
        try:
            await asyncio.sleep(current_interval)

            if get_runtime_lifecycle_state() in (
                GraphRuntimeLifecycleState.SHUTTING_DOWN,
                GraphRuntimeLifecycleState.STOPPED,
            ):
                return

            evaluator.evaluate_all(trigger_side_effects=True)

            # Reset on success
            current_interval = base_interval

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="slo_background_evaluation_failed",
                    message=f"Background SLO evaluation failed: {type(exc).__name__}. Engaging backoff.",
                    metadata={"error": type(exc).__name__},
                ),
            )
            # Exponential backoff
            current_interval = min(current_interval * 2, max_interval)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    setup_logging()
    app = FastAPI(
        title="Financial Asset Relationship API",
        description="REST API for Financial Asset Relationship Database",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    configure_cors(app)

    # Register RequestMetricsMiddleware before CorrelationMiddleware.
    app.add_middleware(RequestMetricsMiddleware)
    app.add_middleware(CorrelationMiddleware)

    app.include_router(auth_router)
    app.include_router(system_router)
    app.include_router(graph_admin_router)
    app.include_router(assets_router)
    app.include_router(relationships_router)
    app.include_router(visualization_router)

    return app


app = create_app()

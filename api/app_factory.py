"""FastAPI application factory for the Financial Asset Relationship Database API."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import threading
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import FastAPI

# pylint: disable=import-error
from slowapi import _rate_limit_exceeded_handler  # type: ignore[import-not-found]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]
from sqlalchemy.exc import SQLAlchemyError

from src.observability.context import async_trace_context, get_span_id, get_trace_id
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
from .graph_lifecycle_providers import (
    resolve_hosted_graph_database_url,
    should_degrade_hosted_startup,
)
from .middleware.correlation import CorrelationMiddleware
from .middleware.request_metrics import RequestMetricsMiddleware
from .rate_limit import limiter
from .routers.assets import router as assets_router
from .routers.auth import router as auth_router
from .routers.graph_admin import init_rebuild_executor
from .routers.graph_admin import router as graph_admin_router
from .routers.graph_admin import shutdown_rebuild_executor_sync as shutdown_rebuild_executor
from .routers.metrics import router as metrics_router
from .routers.relationships import router as relationships_router
from .routers.system import router as system_router
from .routers.visualization import router as visualization_router

# pylint: enable=import-error

if TYPE_CHECKING:
    from .graph_lifecycle_providers import GraphLifecycleSettings

logger = logging.getLogger(__name__)

_STARTUP_RECONCILIATION_LOCK_TTL_SECONDS = 10.0


def _get_durable_graph_database_url(settings: GraphLifecycleSettings) -> str | None:
    """Return the configured durable graph persistence URL across old/new settings shapes."""
    if not hasattr(settings, "asset_graph_database_url"):
        database_url = getattr(settings, "database_url", None)
        if isinstance(database_url, str):
            trimmed = database_url.strip()
            return trimmed or None
        return database_url
    return resolve_hosted_graph_database_url(settings)


def _resolve_startup_reconciliation_url(settings: GraphLifecycleSettings) -> str:
    """Resolve the startup reconciliation database URL, preserving legacy test seams."""
    database_url = _get_durable_graph_database_url(settings)
    if hasattr(settings, "asset_graph_database_url"):
        from .graph_lifecycle_providers import resolve_durable_graph_persistence_url

        return resolve_durable_graph_persistence_url(database_url)
    if database_url is None:
        raise RuntimeError("Graph persistence is not configured.")
    return database_url


def _run_startup_reconciliation(
    settings: GraphLifecycleSettings, cancellation_event: threading.Event | None = None
) -> None:
    """Initialize persisted graph state during application startup."""
    from src.data.database import create_engine_from_url

    url = _resolve_startup_reconciliation_url(settings)
    engine = create_engine_from_url(url)

    # Resolve primary-only Coordination Plane (Plane 2) engine
    coord_url = getattr(settings, "coordination_database_url", None) or url
    coord_engine = create_engine_from_url(coord_url) if coord_url != url else engine

    try:
        # Check cancellation before schema initialization (potentially slow)
        if cancellation_event and cancellation_event.is_set():
            return

        _init_reconciliation_schemas(engine, coord_engine)

        # Check cancellation before recovery gate (lock acquisition/evaluation)
        if cancellation_event and cancellation_event.is_set():
            return

        _execute_recovery_gate(engine, coord_engine, cancellation_event=cancellation_event)
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


def _execute_recovery_gate(engine: Any, coord_engine: Any, cancellation_event: threading.Event | None = None) -> None:
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
        enable_automatic_recovery=False,
    )

    try:
        # RecoveryGate methods are expected to check the cancellation_event
        if hasattr(gate, "ensure_safe_to_execute"):
            gate.ensure_safe_to_execute(cancellation_event=cancellation_event)
    finally:
        if getattr(gate, "lock_was_reacquired", False):
            lock.release()


def _generate_startup_trace_ids() -> tuple[str, str]:
    """
    Generate deterministic or random trace and span IDs for startup.

    Generates W3C-compatible trace identifiers (32-char trace_id, 16-char span_id).
    These IDs can be correlated in downstream systems (e.g. Jaeger, Datadog)
    to trace the startup lifecycle alongside structured application logs.

    Note: `uuid4().hex` intrinsically returns 32 lowercase hex characters,
    making it ideal for natively forming OpenTelemetry/W3C traceparent IDs
    without additional transformations.

    This is extracted to a separate function primarily for testability, allowing
    unit tests to easily mock trace IDs without monkeypatching module-level uuid4.
    """
    return uuid4().hex, uuid4().hex[:16]


def _trace_or_unknown(val: str | None) -> str:
    """Return the given trace/span ID or 'unknown' if not set."""
    return val or "unknown"


async def _run_with_generated_trace(
    func: Callable[..., Any], *args: Any, to_thread: bool = False, **kwargs: Any
) -> tuple[str, str, Any]:
    """Run a callable within a generated trace context, returning trace info and result.

    If the callable raises an exception, the exception is stamped with `trace_id` and `span_id`.
    """
    trace_id, span_id = _generate_startup_trace_ids()
    async with async_trace_context(trace_id=trace_id, span_id=span_id):
        try:
            if to_thread:
                res = await asyncio.to_thread(func, *args, **kwargs)
            elif asyncio.iscoroutinefunction(func):
                res = await func(*args, **kwargs)
            else:
                res = func(*args, **kwargs)
            return trace_id, span_id, res
        except Exception as exc:
            if not hasattr(exc, "trace_id"):
                exc.trace_id = trace_id  # type: ignore[attr-defined]
            if not hasattr(exc, "span_id"):
                exc.span_id = span_id  # type: ignore[attr-defined]
            raise


async def _initialize_application_state(
    settings: GraphLifecycleSettings,
    has_persistence: bool,
    hosted_startup_degradation_allowed: bool,
) -> None:
    """Run startup reconciliation and initialize the graph, handling degraded startup."""
    if has_persistence:
        try:
            await _perform_startup_reconciliation(settings)
        except (SQLAlchemyError, OSError, RuntimeError) as exc:
            if not hosted_startup_degradation_allowed:
                raise
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="startup_degraded",
                    message=("Hosted fallback startup reconciliation failed; continuing with degraded boot."),
                    metadata={
                        "error": type(exc).__name__,
                        "phase": "reconciliation",
                        "trace_id": _trace_or_unknown(get_trace_id()),
                        "span_id": _trace_or_unknown(get_span_id()),
                    },
                ),
            )
    # Required initialization for all environments to ensure state validity
    try:
        get_graph()
    except (SQLAlchemyError, OSError) as exc:
        if not hosted_startup_degradation_allowed:
            raise
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="startup_degraded",
                message="Hosted fallback graph bootstrap failed; continuing with degraded boot.",
                metadata={
                    "error": type(exc).__name__,
                    "phase": "graph_bootstrap",
                    "trace_id": _trace_or_unknown(get_trace_id()),
                    "span_id": _trace_or_unknown(get_span_id()),
                },
            ),
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown tasks for the FastAPI application."""
    from .graph_lifecycle_providers import get_graph_lifecycle_settings
    from .metrics import (
        APPLICATION_STARTUP_DURATION,
        APPLICATION_STARTUP_FAILURE_TOTAL,
        APPLICATION_STARTUP_SUCCESS_TOTAL,
    )

    settings = get_graph_lifecycle_settings()
    database_url = _get_durable_graph_database_url(settings)
    has_persistence_flag = getattr(settings, "has_durable_graph_persistence", None)
    has_persistence = bool(has_persistence_flag) if has_persistence_flag is not None else bool(database_url)
    hosted_startup_degradation_allowed = should_degrade_hosted_startup(settings)

    trace_id, span_id = _generate_startup_trace_ids()

    # Wrap the entire state initialization in a dedicated trace context.
    # This guarantees a fail-fast startup: if context initialization or graph
    # load fails, it will raise immediately before FastAPI accepts HTTP traffic.
    start_time = time.perf_counter()
    try:
        async with async_trace_context(trace_id=trace_id, span_id=span_id):
            logger.debug("Initiating traced startup sequence (trace_id=%s, span_id=%s)", trace_id, span_id)
            try:
                await _initialize_application_state(
                    settings,
                    has_persistence,
                    hosted_startup_degradation_allowed,
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.CRITICAL,
                    ObservabilityEvent(
                        event="startup_failed",
                        message=f"Application startup failed: {type(exc).__name__}",
                        metadata={
                            "error": type(exc).__name__,
                            "message": str(exc),
                            "trace_id": trace_id,
                            "span_id": span_id,
                        },
                    ),
                )
                raise

        sync_task, slo_task, recon_task = _start_background_tasks(has_persistence, settings)
        APPLICATION_STARTUP_SUCCESS_TOTAL.inc()
    except Exception:
        APPLICATION_STARTUP_FAILURE_TOTAL.inc()
        raise
    finally:
        APPLICATION_STARTUP_DURATION.observe(time.perf_counter() - start_time)

    yield

    await _perform_orderly_shutdown(sync_task, slo_task, recon_task, has_persistence)


async def _perform_startup_reconciliation(settings: GraphLifecycleSettings) -> None:
    """Run startup reconciliation with timeout and error handling."""
    from src.logic.recovery_gate import ExecutionBlockedError

    cancellation_event = threading.Event()
    try:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(_run_startup_reconciliation, settings, cancellation_event),
                timeout=120,
            )
        except (TimeoutError, asyncio.TimeoutError):  # pylint: disable=overlapping-except
            # Signal background thread to abort further processing
            cancellation_event.set()
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
                message=f"Failed to load persisted graph during startup: {type(exc).__name__}",
                metadata={
                    "error": type(exc).__name__,
                    "phase": "reconciliation",
                    "trace_id": _trace_or_unknown(get_trace_id()),
                    "span_id": _trace_or_unknown(get_span_id()),
                },
            ),
        )
        # Keep the public message and exception chain sanitized: do not embed
        # str(exc) (may contain DB URLs/secrets). Type name is logged above.
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
) -> tuple[asyncio.Task | None, asyncio.Task, asyncio.Task | None]:
    """Initialize and start background synchronization, SLO, and reconciliation tasks."""
    sync_task: asyncio.Task | None = None
    recon_task: asyncio.Task | None = None
    if has_persistence:
        init_rebuild_executor(settings)
        interval = getattr(settings, "graph_sync_interval_seconds", 60.0)
        sync_task = asyncio.create_task(_graph_synchronization_loop(interval_seconds=interval))

        recon_interval = getattr(settings, "reconciliation_interval_seconds", interval)
        from src.data.distributed_lock import MAX_TTL
        from src.logic.reconciliation_loop import periodic_reconciliation_loop

        recon_url = _resolve_startup_reconciliation_url(settings)
        coord_setting = getattr(settings, "coordination_database_url", None)
        coord_url = coord_setting.strip() if isinstance(coord_setting, str) else coord_setting
        coord_url = coord_url or recon_url
        lock_ttl_seconds = max(1, min(int(getattr(settings, "rebuild_lock_ttl_seconds", MAX_TTL)), MAX_TTL))

        recon_task = asyncio.create_task(
            periodic_reconciliation_loop(
                interval_seconds=recon_interval,
                database_url=recon_url,
                coordination_database_url=coord_url,
                is_shutdown_fn=lambda: (
                    get_runtime_lifecycle_state()
                    in (
                        GraphRuntimeLifecycleState.SHUTTING_DOWN,
                        GraphRuntimeLifecycleState.STOPPED,
                    )
                ),
                run_with_trace_fn=_run_with_generated_trace,
                cancel_event=None,
                lock_ttl_seconds=lock_ttl_seconds,
            )
        )

    slo_task = asyncio.create_task(_slo_evaluation_loop())
    return sync_task, slo_task, recon_task


async def _perform_orderly_shutdown(
    sync_task: asyncio.Task | None,
    slo_task: asyncio.Task,
    recon_task: asyncio.Task | None,
    has_persistence: bool,
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

    if recon_task is not None:
        recon_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):  # NOSONAR
            await recon_task

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
    """Continuously synchronize the in-memory graph with persistent rebuild updates until shutdown."""
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

            await _run_with_generated_trace(sync_with_latest_rebuild, to_thread=True)

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
                        metadata={
                            "error": type(exc).__name__,
                            "trace_id": getattr(exc, "trace_id", "unknown"),
                            "span_id": getattr(exc, "span_id", "unknown"),
                        },
                    ),
                )
                is_in_error_state = True

            # Exponential backoff + randomized jitter applied cleanly to the next cycle
            backoff = min(current_interval * 2, max_interval)
            jitter = random.uniform(0, 0.1 * backoff)
            current_interval = min(backoff + jitter, max_interval)


async def _slo_evaluation_loop() -> None:
    """Periodically evaluate SLOs and update Prometheus metrics and logs.

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

            await _run_with_generated_trace(evaluator.evaluate_all, trigger_side_effects=True, to_thread=False)

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
                    metadata={
                        "error": type(exc).__name__,
                        "trace_id": getattr(exc, "trace_id", "unknown"),
                        "span_id": getattr(exc, "span_id", "unknown"),
                    },
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
    app.include_router(metrics_router)

    return app


app = create_app()

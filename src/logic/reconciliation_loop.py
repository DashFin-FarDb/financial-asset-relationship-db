"""Background loop for periodic reconciliation."""

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any

from src.logic.reconciliation_engine import RebuildCancelledError
from src.logic.recovery_gate import ExecutionBlockedError
from src.observability.facade import ObservabilityEvent, log_event

logger = logging.getLogger(__name__)

_MAX_RECONCILIATION_LOCK_TTL_SECONDS = 300


def _bound_lock_ttl(lock_ttl: int) -> int:
    """Return a lock TTL within the distributed-lock safety bounds."""
    return max(1, min(int(lock_ttl), _MAX_RECONCILIATION_LOCK_TTL_SECONDS))


def _check_cancellation(cancel_event: threading.Event | None) -> None:
    """Raise RebuildCancelledError if the cancellation event is set."""
    if cancel_event and cancel_event.is_set():
        raise RebuildCancelledError("Rebuild cancelled via API request")


def _create_reconciliation_dependencies(
    engine: Any,
    coord_engine: Any,
    lock_ttl: int,
) -> tuple[Any, Any]:
    """Initialize and return session factory and distributed lock."""
    from src.data.database import create_session_factory
    from src.data.distributed_lock import DistributedLock

    bounded_lock_ttl = _bound_lock_ttl(lock_ttl)
    session_factory = create_session_factory(engine)
    coord_session_factory = create_session_factory(coord_engine) if coord_engine is not engine else session_factory

    lock = DistributedLock(
        coordination_session_factory=coord_session_factory,
        lock_name="graph_rebuild",
        ttl_seconds=bounded_lock_ttl,
    )

    return session_factory, lock


def _run_sync_reconciliation(
    engine: Any,
    coord_engine: Any,
    cancel_event: threading.Event | None,
    lock_ttl: int,
) -> None:
    """Execute a single synchronous reconciliation pass."""
    import time

    from api.metrics import RECONCILIATION_DURATION, increment_recovery_trigger, record_drift_metric
    from src.logic.recovery_gate import RecoveryGate

    start_time = time.perf_counter()

    _check_cancellation(cancel_event)

    bounded_lock_ttl = _bound_lock_ttl(lock_ttl)
    session_factory, lock = _create_reconciliation_dependencies(engine, coord_engine, bounded_lock_ttl)

    gate = RecoveryGate(
        session_factory=session_factory,
        lock=lock,
        increment_recovery_trigger=increment_recovery_trigger,
        runtime_has_active_executor=False,
        lock_ttl_seconds=bounded_lock_ttl,
        enable_automatic_recovery=True,
        record_drift_metric=record_drift_metric,
    )

    try:
        _check_cancellation(cancel_event)
        plan = gate.get_reconciliation_plan()
        gate.consume_reconciliation_plan(plan, cancellation_event=cancel_event)
    except RebuildCancelledError:
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="reconciliation_loop_cancelled",
                message="Periodic reconciliation cancelled via cancellation event",
            ),
        )
        raise
    except ExecutionBlockedError as blocked_exc:
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="reconciliation_loop_blocked",
                message=f"Periodic reconciliation execution blocked: {blocked_exc}",
            ),
        )
        raise
    finally:
        if getattr(gate, "lock_was_reacquired", False):
            try:
                gate.lock.release()
            except Exception as release_exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="reconciliation_loop_lock_release_failed",
                        message=f"Failed to release distributed rebuild lock: {type(release_exc).__name__}",
                        metadata={"error": type(release_exc).__name__},
                    ),
                )
        RECONCILIATION_DURATION.observe(time.perf_counter() - start_time)


async def _perform_reconciliation_iteration(
    run_with_trace_fn: Callable,
    engine: Any,
    coord_engine: Any,
    cancel_event: threading.Event | None,
    lock_ttl: int,
) -> None:
    """Perform a single periodic reconciliation iteration with shielding."""
    task = asyncio.create_task(
        run_with_trace_fn(
            lambda: _run_sync_reconciliation(
                engine=engine,
                coord_engine=coord_engine,
                cancel_event=cancel_event,
                lock_ttl=lock_ttl,
            ),
            to_thread=True,
        )
    )

    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        if cancel_event:
            cancel_event.set()
        try:
            await task
        except Exception as task_exc:
            # Task failed during cancellation - log but don't propagate
            # since we're already handling shutdown
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="reconciliation_task_failed_during_cancellation",
                    message=f"Reconciliation task raised {type(task_exc).__name__} during cancellation",
                    metadata={"error": type(task_exc).__name__},
                ),
            )
        raise


async def periodic_reconciliation_loop(
    interval_seconds: float,
    database_url: str,
    is_shutdown_fn: Callable[[], bool],
    run_with_trace_fn: Callable,
    coordination_database_url: str | None = None,
    cancel_event: threading.Event | None = None,
    lock_ttl_seconds: int = 300,
) -> None:
    """Periodically run drift planning and execute automatic recovery.

    Automatically execute RecoveryGate.ensure_safe_to_execute() if a reset state
    plan with automatic execution mode is returned.
    """
    base_interval = max(1.0, float(interval_seconds))
    current_interval = base_interval
    max_interval = base_interval * 32
    is_in_error_state = False

    engine = None
    coord_engine = None

    try:
        engine, coord_engine = _setup_engines(database_url, coordination_database_url)

        while True:
            try:
                await asyncio.sleep(current_interval)

                if is_shutdown_fn():
                    return

                from api.app_factory import GraphRuntimeLifecycleState, get_runtime_lifecycle_state

                # Skip drift evaluation while the app is still initializing or paused
                if get_runtime_lifecycle_state() != GraphRuntimeLifecycleState.READY:
                    continue

                await _perform_reconciliation_iteration(
                    run_with_trace_fn, engine, coord_engine, cancel_event, lock_ttl_seconds
                )

                is_in_error_state, current_interval = _handle_reconciliation_success(is_in_error_state, base_interval)

            except asyncio.CancelledError:
                raise
            except RebuildCancelledError:
                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="reconciliation_loop_cancelled_error",
                        message="Reconciliation loop received cancellation signal. Terminating loop.",
                    ),
                )
                return
            except ExecutionBlockedError as exc:
                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="reconciliation_loop_blocked_state",
                        message=f"Periodic reconciliation blocked by recovery gate: {exc}",
                        metadata={
                            "action": exc.action,
                            "inconsistency": exc.inconsistency_type,
                        },
                    ),
                )
                is_in_error_state, current_interval = _handle_reconciliation_success(is_in_error_state, base_interval)
            except Exception as exc:
                is_in_error_state, current_interval = _handle_reconciliation_error(
                    exc, is_in_error_state, current_interval, max_interval
                )
    finally:
        _dispose_engines(engine, coord_engine)


def _setup_engines(database_url: str, coordination_database_url: str | None) -> tuple[Any, Any]:
    """Create database engines from URLs."""
    from src.data.database import create_engine_from_url

    engine = create_engine_from_url(database_url)
    coord_engine = (
        create_engine_from_url(coordination_database_url)
        if coordination_database_url and coordination_database_url != database_url
        else engine
    )
    return engine, coord_engine


def _dispose_engines(engine: Any, coord_engine: Any) -> None:
    """Safely dispose of main and coordination engines."""
    if engine:
        engine.dispose()
    if coord_engine and coord_engine is not engine:
        coord_engine.dispose()


def _handle_reconciliation_success(is_in_error_state: bool, base_interval: float) -> tuple[bool, float]:
    """Process successful reconciliation loop and clear error states."""
    if is_in_error_state:
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="reconciliation_loop_connection_restored",
                message="Reconciliation loop DB connection restored.",
            ),
        )
        is_in_error_state = False
    return is_in_error_state, base_interval


def _handle_reconciliation_error(
    exc: Exception, is_in_error_state: bool, current_interval: float, max_interval: float
) -> tuple[bool, float]:
    """Log reconciliation errors, manage state, and compute backoff intervals."""
    from src.observability.context import get_span_id, get_trace_id

    if not is_in_error_state:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="reconciliation_loop_transient_error",
                message=(
                    f"Unexpected transient error in periodic reconciliation loop ({type(exc).__name__}). "
                    "Engaging backoff policy."
                ),
                metadata={
                    "error": type(exc).__name__,
                    "trace_id": get_trace_id() or "unknown",
                    "span_id": get_span_id() or "unknown",
                },
            ),
        )
        is_in_error_state = True
    return is_in_error_state, _next_backoff_interval(current_interval, max_interval)


def _next_backoff_interval(current_interval: float, max_interval: float) -> float:
    """Calculate the next backoff interval with jitter."""
    import secrets

    backoff = min(current_interval * 2, max_interval)
    # Generate jitter dynamically using secrets (e.g. integer scaling to simulate float randomness safely)
    jitter = (secrets.randbelow(100) / 1000.0) * backoff
    return min(backoff + jitter, max_interval)

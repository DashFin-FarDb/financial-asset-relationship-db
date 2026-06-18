"""Background loop for periodic reconciliation."""

import asyncio
import logging
import threading
from collections.abc import Callable
from typing import Any

from src.logic.reconciliation_engine import RebuildCancelledError
from src.observability.facade import ObservabilityEvent, log_event

logger = logging.getLogger(__name__)


def _run_sync_reconciliation(
    engine: Any,
    coord_engine: Any,
    cancel_event: threading.Event | None,
    lock_ttl: int,
) -> None:
    """Execute a single synchronous reconciliation pass."""
    from api.metrics import increment_recovery_trigger, record_drift_metric
    from src.data.database import create_session_factory
    from src.data.distributed_lock import DistributedLock
    from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator
    from src.logic.reconciliation_engine import ReconciliationEngine
    from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

    if cancel_event and cancel_event.is_set():
        raise RebuildCancelledError("Rebuild cancelled via API request")

    session_factory = create_session_factory(engine)
    coord_session_factory = create_session_factory(coord_engine) if coord_engine is not engine else session_factory

    lock = DistributedLock(
        coordination_session_factory=coord_session_factory,
        lock_name="graph_rebuild",
        ttl_seconds=lock_ttl,
    )

    evaluator = RebuildDriftEvaluator(
        session_factory=session_factory,
        lock=lock,
        runtime_has_active_executor=False,
        lock_ttl_seconds=lock_ttl,
    )

    engine_inst = ReconciliationEngine(
        evaluator=evaluator,
        enable_automatic_execution=True,
        record_drift_metric=record_drift_metric,
    )

    try:
        if cancel_event and cancel_event.is_set():
            raise RebuildCancelledError("Rebuild cancelled via API request")

        plan = engine_inst.generate_reconciliation_plan()

        if _should_execute_automatic_reset(plan):
            gate = RecoveryGate(
                session_factory=session_factory,
                lock=lock,
                increment_recovery_trigger=increment_recovery_trigger,
                runtime_has_active_executor=False,
                lock_ttl_seconds=lock_ttl,
            )
            try:
                gate.ensure_safe_to_execute(cancellation_event=cancel_event)
            finally:
                if getattr(gate, "lock_was_reacquired", False):
                    lock.release()
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
        except Exception:
            pass
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
    from src.data.database import create_engine_from_url

    base_interval = max(1.0, float(interval_seconds))
    current_interval = base_interval
    max_interval = base_interval * 32
    is_in_error_state = False

    engine = None
    coord_engine = None

    try:
        engine = create_engine_from_url(database_url)
        coord_engine = (
            create_engine_from_url(coordination_database_url)
            if coordination_database_url and coordination_database_url != database_url
            else engine
        )

        while True:
            try:
                await asyncio.sleep(current_interval)

                if is_shutdown_fn():
                    return

                await _perform_reconciliation_iteration(
                    run_with_trace_fn, engine, coord_engine, cancel_event, lock_ttl_seconds
                )

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
                current_interval = base_interval

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
            except Exception as exc:
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
                                "trace_id": getattr(exc, "trace_id", "unknown"),
                                "span_id": getattr(exc, "span_id", "unknown"),
                            },
                        ),
                    )
                    is_in_error_state = True

                current_interval = _next_backoff_interval(current_interval, max_interval)
    finally:
        if engine:
            engine.dispose()
        if coord_engine and coord_engine is not engine:
            coord_engine.dispose()


def _should_execute_automatic_reset(plan: Any) -> bool:
    """Check if the plan requires automatic reset."""
    from src.logic.reconciliation_engine import ActionType, ExecutionMode

    return ActionType.RESET_STATE in plan.actions and plan.execution_mode == ExecutionMode.AUTOMATIC


def _next_backoff_interval(current_interval: float, max_interval: float) -> float:
    """Calculate the next backoff interval with jitter."""
    import secrets

    backoff = min(current_interval * 2, max_interval)
    # Generate jitter dynamically using secrets (e.g. integer scaling to simulate float randomness safely)
    jitter = (secrets.randbelow(100) / 1000.0) * backoff
    return min(backoff + jitter, max_interval)

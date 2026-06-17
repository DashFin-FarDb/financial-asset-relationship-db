"""Background loop for periodic reconciliation."""

import asyncio
import logging
import random
import threading
from typing import Any, Callable

from src.logic.reconciliation_engine import ActionType, ExecutionMode, RebuildCancelledError
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

logger = logging.getLogger(__name__)


async def periodic_reconciliation_loop(  # noqa: C901
    interval_seconds: float,
    settings: Any,
    get_runtime_lifecycle_state: Callable[[], str],
    run_with_trace_fn: Callable,
    cancel_event: threading.Event | None = None,
) -> None:
    """Periodically run drift planning and execute automatic recovery.

    Automatically execute RecoveryGate.ensure_safe_to_execute() if a reset state
    plan with automatic execution mode is returned.
    """
    from api.metrics import increment_recovery_trigger, record_drift_metric
    from src.data.database import create_engine_from_url, create_session_factory
    from src.data.distributed_lock import DistributedLock
    from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator
    from src.logic.reconciliation_engine import ReconciliationEngine
    from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

    base_interval = max(1.0, float(interval_seconds))
    current_interval = base_interval
    max_interval = base_interval * 32
    is_in_error_state = False

    # Inline resolution equivalent to _resolve_startup_reconciliation_url
    url = getattr(settings, "asset_graph_database_url", None) or getattr(settings, "database_url", "sqlite:///:memory:")
    engine = create_engine_from_url(url)
    coord_url = getattr(settings, "coordination_database_url", None) or url
    coord_engine = create_engine_from_url(coord_url) if coord_url != url else engine

    # Use constant from app_factory or define here
    lock_ttl = 300

    try:
        while True:
            try:
                await asyncio.sleep(current_interval)

                if get_runtime_lifecycle_state() in ("shutting_down", "stopped"):
                    return

                def run_sync_reconciliation() -> None:
                    if cancel_event and cancel_event.is_set():
                        raise RebuildCancelledError("Rebuild cancelled via API request")

                    session_factory = create_session_factory(engine)
                    coord_session_factory = (
                        create_session_factory(coord_engine) if coord_engine is not engine else session_factory
                    )

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

                        if ActionType.RESET_STATE in plan.actions and plan.execution_mode == ExecutionMode.AUTOMATIC:
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

                await run_with_trace_fn(run_sync_reconciliation, to_thread=True)

                # Reset interval on successful iteration
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

                # Exponential backoff + randomized jitter applied to next cycle
                backoff = min(current_interval * 2, max_interval)
                jitter = random.uniform(0, 0.1 * backoff)
                current_interval = min(backoff + jitter, max_interval)
    finally:
        engine.dispose()
        if coord_engine is not engine:
            coord_engine.dispose()

"""Recovery gate to prevent execution under unsafe state conditions."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from src.data.distributed_lock import DistributedLock, LockAcquisitionTimeout, LockState
from src.data.repository import AssetGraphRepository
from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator
from src.logic.rebuild_failure_detection import InconsistencyType
from src.logic.reconciliation_engine import (
    ActionType,
    ExecutionMode,
    ExecutionSafety,
    ReconciliationEngine,
    ReconciliationPlan,
    Severity,
)
from src.observability.facade import ObservabilityEvent, log_event

logger = logging.getLogger(__name__)


class ExecutionBlockedError(Exception):
    """Raised when execution is blocked by the recovery gate.

    The ``action`` attribute carries the string value of the primary ``ActionType``
    that triggered the block.

    The ``inconsistency_type`` attribute usually carries the string value of the
    detected ``InconsistencyType``.
    """

    def __init__(self, message: str, action: str | None = None, inconsistency_type: str | None = None) -> None:
        """Initialize ExecutionBlockedError."""
        super().__init__(message)
        self.action = action
        self.inconsistency_type = inconsistency_type


class RecoveryGate:
    """Blocks execution unless the system state is consistent or safely recoverable."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        lock: DistributedLock,
        increment_recovery_trigger: Callable[[str], None] | None = None,
        runtime_has_active_executor: bool = False,
        lock_ttl_seconds: int = 300,
    ) -> None:
        """Initialize RecoveryGate."""
        self.session_factory = session_factory
        self.lock = lock
        self.increment_recovery_trigger = increment_recovery_trigger or (lambda _: None)
        self.runtime_has_active_executor = runtime_has_active_executor
        self.lock_ttl_seconds = lock_ttl_seconds
        self.lock_was_reacquired = False

    def _create_unsafe_plan_from_error(
        self, exc: Exception, error_context: str, log_level: str = "warning"
    ) -> ReconciliationPlan:
        """Create an unsafe ReconciliationPlan from an error."""
        exc_type = type(exc).__name__
        reason = f"{exc_type}: {error_context}"

        if log_level == "error":
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="recovery_gate_execution_blocked_error",
                    message=f"Execution blocked: {exc_type} ({error_context})",
                    metadata={"error": exc_type, "context": error_context},
                ),
            )
        else:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="recovery_gate_execution_blocked_warning",
                    message=f"Execution blocked: {exc_type} ({error_context})",
                    metadata={"error": exc_type, "context": error_context},
                ),
            )

        if isinstance(exc, sqlalchemy_exc.SQLAlchemyError):
            log_event(
                logger,
                logging.DEBUG,
                ObservabilityEvent(
                    event="recovery_gate_db_error_suppressed",
                    message="DB error prevented state evaluation - not incrementing recovery trigger",
                ),
            )
        else:
            log_event(
                logger,
                logging.DEBUG,
                ObservabilityEvent(
                    event="recovery_gate_unexpected_error_suppressed",
                    message=(
                        "Unexpected error prevented state evaluation - "
                        "not incrementing orphaned_running recovery trigger"
                    ),
                ),
            )

        return ReconciliationPlan(
            drift_type="evaluation_failed",
            severity=Severity.CRITICAL,
            actions=(ActionType.ALERT_ONLY,),
            target_state="healthy",
            execution_mode=ExecutionMode.MANUAL,
            safety_state=ExecutionSafety.EVALUATION_FAILED,
            reason=reason,
            metadata={"error": exc_type, "context": error_context},
            created_at=datetime.now(UTC),
        )

    def get_reconciliation_plan(self, increment_metric: bool = True) -> ReconciliationPlan:
        """Decide the appropriate recovery action based on lock, database, and runtime state.

        Returns a ReconciliationPlan.
        """
        import src.logic.rebuild_drift_evaluator as drift_evaluator_module

        orig_repo = getattr(drift_evaluator_module, "AssetGraphRepository", None)
        setattr(drift_evaluator_module, "AssetGraphRepository", AssetGraphRepository)

        try:
            try:
                evaluator = RebuildDriftEvaluator(
                    session_factory=self.session_factory,
                    lock=self.lock,
                    runtime_has_active_executor=self.runtime_has_active_executor,
                    lock_ttl_seconds=self.lock_ttl_seconds,
                )
                engine = ReconciliationEngine(evaluator=evaluator)
                plan = engine.generate_reconciliation_plan()
            except ValueError as exc:
                return self._create_unsafe_plan_from_error(exc, "active rebuild state query failed")
            except sqlalchemy_exc.SQLAlchemyError as exc:
                return self._create_unsafe_plan_from_error(exc, "database error during rebuild state query")
            except Exception as exc:
                return self._create_unsafe_plan_from_error(exc, "unexpected error during rebuild state query", "error")
        finally:
            if orig_repo is not None:
                setattr(drift_evaluator_module, "AssetGraphRepository", orig_repo)

        if increment_metric and plan.drift_type != InconsistencyType.NONE.value:
            # Handle possible conversion errors if drift_type isn't an InconsistencyType enum value
            try:
                inc_type = InconsistencyType(plan.drift_type)
                self.increment_recovery_trigger(inc_type.value)
            except ValueError:
                pass

        # Log if not safe to execute
        safe_to_execute = ActionType.NOOP in plan.actions and plan.safety_state == ExecutionSafety.CONVERGED
        if not safe_to_execute:
            action_val = plan.actions[0].value
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="recovery_gate_execution_blocked",
                    message=f"Execution blocked: {plan.reason}",
                    metadata={
                        "action": action_val,
                        "inconsistency": plan.drift_type,
                        "reason": plan.reason,
                    },
                ),
            )
        return plan

    def evaluate_state(self) -> str:
        """Evaluate DB state, runtime state, and lock state together.

        Returns the primary action value.
        """
        plan = self.get_reconciliation_plan()
        # To maintain compatibility with some tests, we'll map back to legacy strings
        if ActionType.RESET_STATE in plan.actions:
            return "reset"
        elif ActionType.WAIT_FOR_CONVERGENCE in plan.actions:
            return "wait"
        elif ActionType.NOOP in plan.actions:
            if plan.safety_state == ExecutionSafety.WAIT_REQUIRED:
                return "wait"
            return "resume"
        return "unsafe"

    def ensure_safe_to_execute(self, cancellation_event: threading.Event | None = None) -> None:
        """Enforce execution blocking rules and perform recovery actions."""
        self.lock_was_reacquired = False
        plan = self.get_reconciliation_plan()

        action = (
            "reset"
            if ActionType.RESET_STATE in plan.actions
            else (
                "wait"
                if (
                    ActionType.WAIT_FOR_CONVERGENCE in plan.actions
                    or plan.safety_state == ExecutionSafety.WAIT_REQUIRED
                )
                else "resume" if ActionType.NOOP in plan.actions else "unsafe"
            )
        )

        if action == "reset":
            if cancellation_event and cancellation_event.is_set():
                return

            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="recovery_gate_reset_recovery_initiated",
                    message=f"Recovery action RESET: attempting to reset orphaned job state. Reason: {plan.reason}",
                    metadata={"reason": plan.reason},
                ),
            )
            try:
                self._perform_reset_recovery(cancellation_event=cancellation_event)

                if cancellation_event and cancellation_event.is_set():
                    return

                new_plan = self.get_reconciliation_plan(increment_metric=False)
                new_action = (
                    "reset"
                    if ActionType.RESET_STATE in new_plan.actions
                    else (
                        "wait"
                        if (
                            ActionType.WAIT_FOR_CONVERGENCE in new_plan.actions
                            or new_plan.safety_state == ExecutionSafety.WAIT_REQUIRED
                        )
                        else "resume" if ActionType.NOOP in new_plan.actions else "unsafe"
                    )
                )

                if new_action != "resume":
                    raise ExecutionBlockedError(
                        f"Reset recovery completed but state still unsafe: action={new_action}",
                        action=new_action,
                        inconsistency_type=new_plan.drift_type,
                    )
                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="recovery_gate_reset_recovery_succeeded",
                        message="Reset recovery successful - execution can proceed",
                    ),
                )
            except ExecutionBlockedError:
                raise
            except sqlalchemy_exc.SQLAlchemyError as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="recovery_gate_reset_recovery_db_failed",
                        message=f"Reset recovery failed due to database error: {type(exc).__name__}",
                        metadata={"error": type(exc).__name__},
                    ),
                )
                raise ExecutionBlockedError(f"Reset recovery failed: {type(exc).__name__}") from exc
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="recovery_gate_reset_recovery_unexpected_error",
                        message=f"Unexpected error during reset recovery: {type(exc).__name__}",
                        metadata={"error": type(exc).__name__},
                    ),
                )
                raise ExecutionBlockedError(f"Reset recovery failed: {type(exc).__name__}") from exc
        elif action != "resume":
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="recovery_gate_execution_blocked_final",
                    message=(
                        f"Execution blocked by recovery gate: action={action}, " f"inconsistency={plan.drift_type}"
                    ),
                    metadata={
                        "action": action,
                        "inconsistency": plan.drift_type,
                    },
                ),
            )
            raise ExecutionBlockedError(
                f"Execution blocked: action={action}, inconsistency={plan.drift_type}",
                action=action,
                inconsistency_type=plan.drift_type,
            )

    def _perform_reset_recovery(self, cancellation_event: threading.Event | None = None) -> None:
        """Reset an orphaned RUNNING rebuild job so a new execution can proceed."""
        from src.data.db_models import RebuildJobStatus

        lock_state = self.lock.check_state()
        if lock_state != LockState.VALID:
            if cancellation_event and cancellation_event.is_set():
                return

            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="recovery_gate_lock_reacquisition_attempt",
                    message=f"Lock state is {lock_state.value} before RESET recovery, attempting reacquisition...",
                    metadata={"lock_state": lock_state.value},
                ),
            )
            try:
                self.lock.acquire()
            except LockAcquisitionTimeout as exc:
                msg = f"Cannot perform RESET recovery without valid lock (state={lock_state.value})"
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="recovery_gate_lock_reacquisition_failed",
                        message=f"{ExecutionBlockedError.__name__}: {msg}",
                        metadata={"error": ExecutionBlockedError.__name__, "details": msg},
                    ),
                )
                raise ExecutionBlockedError(msg) from exc
            self.lock_was_reacquired = True
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="recovery_gate_lock_reacquired",
                    message="Successfully reacquired lock for RESET recovery",
                ),
            )

        if cancellation_event and cancellation_event.is_set():
            return

        try:
            with self.session_factory() as session:
                repo = AssetGraphRepository(session)
                active_job = repo.get_active_rebuild_state()

                if active_job and active_job.status == RebuildJobStatus.RUNNING:
                    if cancellation_event and cancellation_event.is_set():
                        return

                    repo.mark_rebuild_job_failed(
                        active_job.job_id,
                        execution_id=active_job.execution_id,
                        failure_category="recovery_reset",
                        failure_message="Recovered from orphaned state by RecoveryGate",
                        duration_ms=0,
                    )
                    session.commit()
                    log_event(
                        logger,
                        logging.WARNING,
                        ObservabilityEvent(
                            event="recovery_gate_orphaned_job_reset",
                            message=(
                                f"Reset orphaned rebuild job {active_job.job_id} "
                                f"(previous owner: {active_job.active_worker_id or 'unknown'})"
                            ),
                            metadata={
                                "job_id": active_job.job_id,
                                "previous_owner": active_job.active_worker_id or "unknown",
                            },
                        ),
                    )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="recovery_gate_reset_recovery_failed",
                    message=f"Failed to perform reset recovery: {type(exc).__name__}",
                    metadata={"error": type(exc).__name__},
                ),
            )
            raise

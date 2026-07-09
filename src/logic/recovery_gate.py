"""Recovery gate to prevent execution under unsafe state conditions."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from src.data.distributed_lock import MAX_TTL, DistributedLock, LockAcquisitionTimeout, LockState
from src.data.repository import AssetGraphRepository, RebuildFailureDetails
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
UTC = timezone.utc


class ExecutionBlockedError(Exception):
    """Raised when execution is blocked by the recovery gate.

    The ``action`` attribute carries the legacy action contract values
    (reset, wait, unsafe, resume).

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
        enable_automatic_recovery: bool = False,
        record_drift_metric: Callable[[str, str, str], None] | None = None,
    ) -> None:
        """Initialize RecoveryGate."""
        self.session_factory = session_factory
        self.lock = lock
        self.increment_recovery_trigger = increment_recovery_trigger or (lambda _: None)
        self.runtime_has_active_executor = runtime_has_active_executor
        self.lock_ttl_seconds = max(1, min(int(lock_ttl_seconds), MAX_TTL))
        self.enable_automatic_recovery = enable_automatic_recovery
        self.record_drift_metric = record_drift_metric or (lambda _t, _s, _e: None)
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

    def _map_plan_to_action(self, plan: ReconciliationPlan) -> str:
        """Map a reconciliation plan to a legacy action string."""
        if ActionType.RESET_STATE in plan.actions:
            return "reset"
        if ActionType.WAIT_FOR_CONVERGENCE in plan.actions or plan.safety_state == ExecutionSafety.WAIT_REQUIRED:
            return "wait"
        if ActionType.ALERT_ONLY in plan.actions:
            return "alert_only"
        if ActionType.NOOP in plan.actions:
            return "resume"
        return "unsafe"

    def get_reconciliation_plan(self, increment_metric: bool = True) -> ReconciliationPlan:
        """Decide the appropriate recovery action based on lock, database, and runtime state.

        Returns a ReconciliationPlan.
        """
        import src.logic.rebuild_drift_evaluator as drift_evaluator_module

        orig_repo = getattr(drift_evaluator_module, "AssetGraphRepository", None)
        drift_evaluator_module.AssetGraphRepository = AssetGraphRepository  # type: ignore[misc]

        try:
            try:
                evaluator = RebuildDriftEvaluator(
                    session_factory=self.session_factory,
                    lock=self.lock,
                    runtime_has_active_executor=self.runtime_has_active_executor,
                    lock_ttl_seconds=self.lock_ttl_seconds,
                )
                engine = ReconciliationEngine(
                    evaluator=evaluator,
                    enable_automatic_execution=self.enable_automatic_recovery,
                    record_drift_metric=self.record_drift_metric,
                )
                plan = engine.generate_reconciliation_plan()
            except ValueError as exc:
                return self._create_unsafe_plan_from_error(exc, "active rebuild state query failed")
            except sqlalchemy_exc.SQLAlchemyError as exc:
                return self._create_unsafe_plan_from_error(exc, "database error during rebuild state query")
            except Exception as exc:
                return self._create_unsafe_plan_from_error(exc, "unexpected error during rebuild state query", "error")
        finally:
            if orig_repo is not None:
                drift_evaluator_module.AssetGraphRepository = orig_repo  # type: ignore[misc]

        if increment_metric and plan.drift_type != InconsistencyType.NONE.value:
            # Handle possible conversion errors if drift_type isn't an InconsistencyType enum value
            try:
                inc_type = InconsistencyType(plan.drift_type)
                self.increment_recovery_trigger(inc_type.value)
            except ValueError:
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="recovery_gate_unknown_drift_type",
                        message=f"Unknown drift type encountered: {plan.drift_type}",
                        metadata={"drift_type": plan.drift_type},
                    ),
                )

        # Log if not safe to execute
        action_val = self._map_plan_to_action(plan)
        if action_val != "resume":
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
        return self._map_plan_to_action(plan)

    def _raise_safety_block(self, plan: ReconciliationPlan, action: str) -> None:
        """Log and raise ExecutionBlockedError for unsafe safety states."""
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="recovery_gate_execution_blocked_final",
                message=(
                    f"Execution blocked by recovery gate safety state: "
                    f"safety_state={plan.safety_state.value}, inconsistency={plan.drift_type}"
                ),
                metadata={
                    "action": action,
                    "inconsistency": plan.drift_type,
                    "safety_state": plan.safety_state.value,
                },
            ),
        )
        raise ExecutionBlockedError(
            f"Execution blocked due to safety state: {plan.safety_state.value} "
            f"(action={action}, inconsistency={plan.drift_type})",
            action=action,
            inconsistency_type=plan.drift_type,
        )

    def _should_execute_reset(self, plan: ReconciliationPlan) -> bool:
        """Return True when a reset plan is authorized for immediate mutation."""
        if ActionType.RESET_STATE not in plan.actions or plan.safety_state != ExecutionSafety.RESET_REQUIRED:
            return False
        if plan.execution_mode == ExecutionMode.IMMEDIATE:
            return True
        return plan.execution_mode == ExecutionMode.AUTOMATIC and self.enable_automatic_recovery

    def _handle_reset_action(
        self,
        plan: ReconciliationPlan,
        cancellation_event: threading.Event | None = None,
    ) -> bool:
        """Handle reset actions. Returns True if reset was executed, False otherwise."""
        if ActionType.RESET_STATE not in plan.actions:
            return False

        if self._should_execute_reset(plan):
            from src.logic.reconciliation_engine import RebuildCancelledError

            if cancellation_event and cancellation_event.is_set():
                raise RebuildCancelledError("Rebuild cancelled via API request")

            self._execute_reset_path(plan, cancellation_event)

            if cancellation_event and cancellation_event.is_set():
                raise RebuildCancelledError("Rebuild cancelled via API request")
            return True

        action = "wait" if plan.execution_mode == ExecutionMode.DEFERRED else "alert_only"
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="recovery_gate_execution_blocked_final",
                message=(
                    f"Execution blocked for non-automatic reset plan: action={action}, inconsistency={plan.drift_type}"
                ),
                metadata={
                    "action": action,
                    "inconsistency": plan.drift_type,
                },
            ),
        )
        raise ExecutionBlockedError(
            f"Execution blocked: reset required but mode={plan.execution_mode.value} "
            f"(action={action}, inconsistency={plan.drift_type})",
            action=action,
            inconsistency_type=plan.drift_type,
        )

    def _raise_action_block(self, plan: ReconciliationPlan, action: str, reason_prefix: str) -> None:
        """Log and raise ExecutionBlockedError for a terminal block action."""
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="recovery_gate_execution_blocked_final",
                message=f"Execution blocked by recovery gate: action={action}, inconsistency={plan.drift_type}",
                metadata={
                    "action": action,
                    "inconsistency": plan.drift_type,
                },
            ),
        )
        raise ExecutionBlockedError(
            f"Execution blocked: {reason_prefix}. Reason: {plan.reason} "
            f"(action={action}, inconsistency={plan.drift_type})",
            action=action,
            inconsistency_type=plan.drift_type,
        )

    def _raise_wait_block(self, plan: ReconciliationPlan) -> None:
        """Log and raise ExecutionBlockedError for WAIT action."""
        self._raise_action_block(plan, "wait", "waiting for convergence")

    def _raise_alert_block(self, plan: ReconciliationPlan) -> None:
        """Log and raise ExecutionBlockedError for ALERT_ONLY action."""
        self._raise_action_block(plan, "alert_only", "alert only")

    def _handle_unknown_plan_block(self, plan: ReconciliationPlan) -> None:
        """Block unrecognized plan combinations without mutating state."""
        mapped_action = self._map_plan_to_action(plan)
        action = "unsafe" if mapped_action == "resume" else mapped_action
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="recovery_gate_execution_blocked_final",
                message=(
                    f"Execution blocked by recovery gate for unrecognized plan: "
                    f"action={action}, inconsistency={plan.drift_type}"
                ),
                metadata={
                    "action": action,
                    "inconsistency": plan.drift_type,
                    "mapped_action": mapped_action,
                },
            ),
        )
        raise ExecutionBlockedError(
            f"Execution blocked: unrecognized plan. (action={action}, inconsistency={plan.drift_type})",
            action=action,
            inconsistency_type=plan.drift_type,
        )

    def _is_terminal_safety_plan(self, plan: ReconciliationPlan) -> bool:
        """Return True when the plan safety state must block immediately."""
        return plan.safety_state in (
            ExecutionSafety.EVALUATION_FAILED,
            ExecutionSafety.OBSERVABILITY_FAILURE,
            ExecutionSafety.UNSAFE_SPLIT_BRAIN,
            ExecutionSafety.INTEGRITY_COMPROMISED,
        )

    def _is_wait_plan(self, plan: ReconciliationPlan) -> bool:
        """Return True when the plan requires waiting for convergence."""
        return ActionType.WAIT_FOR_CONVERGENCE in plan.actions or plan.safety_state == ExecutionSafety.WAIT_REQUIRED

    def _is_converged_noop_plan(self, plan: ReconciliationPlan) -> bool:
        """Return True when the plan explicitly allows execution."""
        return ActionType.NOOP in plan.actions and plan.safety_state == ExecutionSafety.CONVERGED

    def consume_reconciliation_plan(
        self,
        plan: ReconciliationPlan,
        cancellation_event: threading.Event | None = None,
    ) -> None:
        """Consume a ReconciliationPlan and enforce recovery or execution blocking rules."""
        if self._is_terminal_safety_plan(plan):
            action = self._map_plan_to_action(plan)
            if action == "resume":
                action = "unsafe"
            self._raise_safety_block(plan, action)

        if self._handle_reset_action(plan, cancellation_event):
            return

        if self._is_wait_plan(plan):
            self._raise_wait_block(plan)

        if ActionType.ALERT_ONLY in plan.actions:
            self._raise_alert_block(plan)

        if self._is_converged_noop_plan(plan):
            # allow execution
            return

        self._handle_unknown_plan_block(plan)

    def ensure_safe_to_execute(self, cancellation_event: threading.Event | None = None) -> None:
        """Enforce execution blocking rules and perform recovery actions."""
        self.lock_was_reacquired = False
        plan = self.get_reconciliation_plan()
        self.consume_reconciliation_plan(plan, cancellation_event)

    def _execute_reset_path(self, plan: ReconciliationPlan, cancellation_event: threading.Event | None) -> None:
        """Handle the reset recovery path."""
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
            self._perform_reset_recovery(cancellation_event=cancellation_event, drift_type=plan.drift_type)

            if cancellation_event and cancellation_event.is_set():
                return

            new_plan = self.get_reconciliation_plan(increment_metric=False)
            new_action = self._map_plan_to_action(new_plan)

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

    def _ensure_lock_for_reset(self, drift_type: str) -> None:
        """Acquire lock if not already held or reacquired."""
        if self.lock.check_state() == LockState.VALID:
            return

        try:
            self.lock.acquire(max_retries=30, timeout_seconds=30.0)
        except LockAcquisitionTimeout as lat_exc:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="recovery_gate_lock_reacquisition_failed",
                    message="Timeout acquiring distributed lock for reset recovery",
                    metadata={"error": "LockAcquisitionTimeout"},
                ),
            )
            raise ExecutionBlockedError(
                f"Timeout acquiring distributed lock for reset recovery: {lat_exc} "
                f"(action=wait, inconsistency={drift_type})",
                action="wait",
                inconsistency_type=drift_type,
            ) from lat_exc

        if self.lock.check_state() != LockState.VALID:
            raise ExecutionBlockedError(
                f"Cannot perform reset recovery without valid lock after reacquisition "
                f"(action=wait, inconsistency={drift_type})",
                action="wait",
                inconsistency_type=drift_type,
            )
        self.lock_was_reacquired = True

    def _is_heartbeat_stale(self, active_job: Any) -> bool:
        """Determine if active rebuild job heartbeat is stale."""
        if not active_job.last_heartbeat_at:
            return True
        heartbeat_time = active_job.last_heartbeat_at
        if heartbeat_time.tzinfo is None:
            heartbeat_time = heartbeat_time.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - heartbeat_time).total_seconds()
        return age >= self.lock_ttl_seconds

    def _reset_active_job(
        self,
        active_job: Any,
        repo: AssetGraphRepository,
        session: Any,
        drift_type: str,
    ) -> None:
        """Mark active job as failed and commit."""
        if self.lock.check_state() != LockState.VALID or not self.lock.holder_id:
            raise ExecutionBlockedError(
                f"Cannot reset job {active_job.job_id}: lock lost before reset "
                f"(action=wait, inconsistency={drift_type})",
                action="wait",
                inconsistency_type=drift_type,
            )

        current_worker = self.lock.holder_id
        if active_job.active_worker_id != current_worker and not self._is_heartbeat_stale(active_job):
            inconsistency = InconsistencyType.STALE_OWNERSHIP.value
            raise ExecutionBlockedError(
                f"Cannot reset job {active_job.job_id}: active worker "
                f"{active_job.active_worker_id} has fresh heartbeat (action=unsafe, inconsistency={inconsistency})",
                action="unsafe",
                inconsistency_type=inconsistency,
            )

        repo.mark_rebuild_job_failed(
            active_job.job_id,
            execution_id=active_job.execution_id,
            details=RebuildFailureDetails(
                failure_category="recovery_reset",
                failure_message="Recovered from orphaned state by RecoveryGate",
                duration_ms=0,
            ),
        )
        if (
            self.lock.check_state() != LockState.VALID
            or not self.lock.holder_id
            or self.lock.holder_id != current_worker
        ):
            job_id = active_job.job_id
            try:
                session.rollback()
            except Exception:
                logger.debug(
                    "Rollback failed while handling lock-loss during reset for job %s; "
                    "continuing to raise ExecutionBlockedError",
                    job_id,
                    exc_info=True,
                )
            raise ExecutionBlockedError(
                f"Cannot commit reset for job {job_id}: lock lost (action=wait, inconsistency={drift_type})",
                action="wait",
                inconsistency_type=drift_type,
            )
        session.commit()

    def _perform_reset_recovery(
        self,
        cancellation_event: threading.Event | None = None,
        drift_type: str = InconsistencyType.ORPHANED_RUNNING.value,
    ) -> None:
        """Reset an orphaned RUNNING rebuild job so a new execution can proceed."""
        from src.data.db_models import RebuildJobStatus

        if cancellation_event and cancellation_event.is_set():
            return

        self._ensure_lock_for_reset(drift_type)

        if cancellation_event and cancellation_event.is_set():
            return

        try:
            with self.session_factory() as session:
                repo = AssetGraphRepository(session)
                active_job = repo.get_active_rebuild_state()

                if not active_job or active_job.status != RebuildJobStatus.RUNNING:
                    return

                if cancellation_event and cancellation_event.is_set():
                    return

                self._reset_active_job(active_job, repo, session, drift_type)

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
            if isinstance(exc, ExecutionBlockedError):
                raise
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

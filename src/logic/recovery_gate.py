"""Recovery gate to prevent execution under unsafe state conditions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from src.data.distributed_lock import DistributedLock, LockState
from src.data.repository import AssetGraphRepository
from src.logic.rebuild_failure_detection import (
    InconsistencyType,
    detect_rebuild_inconsistency,
)
from src.logic.rebuild_recovery import RecoveryAction, determine_recovery_action

logger = logging.getLogger(__name__)


class ExecutionBlockedError(Exception):
    """Raised when execution is blocked by the recovery gate."""

    pass


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
        """
        Initialize the RecoveryGate.

        Args:
            session_factory: Factory for creating database sessions.
            lock: The distributed lock instance.
            increment_recovery_trigger: Optional callback for recording
                detected inconsistency metrics.
            runtime_has_active_executor: Whether the runtime currently has an active executor.
            lock_ttl_seconds: TTL seconds for the lock.
        """
        self.session_factory = session_factory
        self.lock = lock
        self.increment_recovery_trigger = increment_recovery_trigger or (lambda _: None)
        self.runtime_has_active_executor = runtime_has_active_executor
        self.lock_ttl_seconds = lock_ttl_seconds

    def _create_unsafe_decision_from_error(self, exc: Exception, error_context: str, log_level: str = "warning"):
        """
        Create an UNSAFE decision from an exception with sanitized logging.

        Args:
            exc: The exception that occurred.
            error_context: Context string (e.g., "active rebuild state query failed").
            log_level: Logging level ("warning" or "error").

        Returns:
            RecoveryDecision with UNSAFE action.
        """
        from src.logic.rebuild_recovery import RecoveryDecision

        exc_type = type(exc).__name__
        reason = f"{exc_type}: {error_context}"

        if log_level == "error":
            logger.error("Execution blocked: %s (%s)", exc_type, error_context)
        else:
            logger.warning("Execution blocked: %s (%s)", exc_type, error_context)

        # Do not increment orphaned-running metrics from this generic error path.
        # At this point we only know state evaluation failed; we do not know that
        # an ORPHANED_RUNNING inconsistency was actually detected.
        if isinstance(exc, sqlalchemy_exc.SQLAlchemyError):
            logger.debug("DB error prevented state evaluation - not incrementing recovery trigger")
        else:
            logger.debug(
                "Unexpected error prevented state evaluation - not incrementing " "orphaned_running recovery trigger"
            )

        return RecoveryDecision(
            action=RecoveryAction.UNSAFE,
            reason=reason,
            inconsistency_type=None,
            safe_to_execute=False,
        )

    def _apply_owner_mismatch_override(self, decision, inconsistency, lock_is_valid, job):
        """
        Override decision to RESET if orphaned job has wrong owner AND stale heartbeat.

        A different active_worker_id alone is NOT sufficient to downgrade to RESET
        because a healthy remote worker will have a different ID. We must also verify
        that the heartbeat is stale or missing to distinguish a crash from an active
        remote rebuild.

        Args:
            decision: Original recovery decision.
            inconsistency: Detected inconsistency.
            lock_is_valid: Whether lock state is valid.
            job: The rebuild job (may be None).

        Returns:
            Modified decision if owner mismatch detected, otherwise original.
        """
        from src.logic.rebuild_recovery import RecoveryDecision

        # Early return if not orphaned running state
        if inconsistency.inconsistency_type != InconsistencyType.ORPHANED_RUNNING:
            return decision

        # Without a job there is nothing to compare. Do not skip the owner/heartbeat
        # safety check merely because the current lock is invalid; an expired local
        # lock is exactly when we must avoid resetting a healthy remote worker.
        if job is None:
            return decision

        # Early return if owner matches
        if job.active_worker_id == self.lock.holder_id:
            return decision

        # Owner mismatch detected - check heartbeat staleness before downgrading to RESET
        # A different worker_id + fresh heartbeat = healthy remote worker (UNSAFE)
        # A different worker_id + stale/missing heartbeat = orphaned job (RESET)
        if job.last_heartbeat_at:
            # Handle both datetime (from ORM) and string (from raw SQL) types
            heartbeat_time = job.last_heartbeat_at
            if isinstance(heartbeat_time, str):
                heartbeat_time = datetime.fromisoformat(heartbeat_time)

            # Ensure timezone-aware comparison
            if heartbeat_time.tzinfo is None:
                heartbeat_time = heartbeat_time.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            heartbeat_age_seconds = (now - heartbeat_time).total_seconds()

            # Heartbeat is stale if older than lock TTL threshold
            if heartbeat_age_seconds < self.lock_ttl_seconds:
                # Fresh heartbeat from different worker = active remote rebuild
                # Do NOT reset - this would cause split-brain
                logger.warning(
                    "Owner mismatch with FRESH heartbeat (age=%.1fs): "
                    "job.active_worker_id=%s, lock.holder_id=%s. Keeping %s decision.",
                    heartbeat_age_seconds,
                    job.active_worker_id,
                    self.lock.holder_id,
                    decision.action.value,
                )
                return decision

        # Stale or missing heartbeat with owner mismatch = orphaned job
        logger.info(
            "Owner mismatch with STALE/MISSING heartbeat detected: "
            "job.active_worker_id=%s, lock.holder_id=%s. Downgrading to RESET.",
            job.active_worker_id,
            self.lock.holder_id,
        )
        return RecoveryDecision(
            action=RecoveryAction.RESET,
            reason=(
                "Orphaned running rebuild with stale heartbeat (owner mismatch: "
                f"job worker_id={job.active_worker_id!r}, "
                f"current lock holder_id={self.lock.holder_id!r})"
            ),
            inconsistency_type=decision.inconsistency_type,
            safe_to_execute=decision.safe_to_execute,
        )

    def _evaluate_decision(self, increment_metric: bool = True):
        """
        Evaluate lock, DB, and runtime state and return a recovery decision.

        Args:
            increment_metric: If True, increment recovery trigger metric when
                inconsistency is detected. Set to False on re-evaluation after
                recovery to avoid double-counting.

        Returns:
            RecoveryDecision: Deterministic decision used by both
                evaluate_state() and ensure_safe_to_execute().
        """
        from src.logic.rebuild_recovery import RecoveryDecision

        lock_state = self.lock.check_state()
        job = None

        if lock_state in (LockState.UNKNOWN, LockState.LOST):
            logger.warning("Execution blocked: Lock state is %s", lock_state.value)
            return RecoveryDecision(
                action=RecoveryAction.UNSAFE,
                reason=f"Lock state is {lock_state.value}",
                inconsistency_type=None,
                safe_to_execute=False,
            )

        lock_is_valid = lock_state == LockState.VALID

        with self.session_factory() as session:
            repo = AssetGraphRepository(session)
            try:
                job = repo.get_active_rebuild_state()
            except ValueError as exc:
                return self._create_unsafe_decision_from_error(exc, "active rebuild state query failed")
            except sqlalchemy_exc.SQLAlchemyError as exc:
                return self._create_unsafe_decision_from_error(exc, "database error during rebuild state query")
            except Exception as exc:
                return self._create_unsafe_decision_from_error(
                    exc, "unexpected error during rebuild state query", "error"
                )

        inconsistency = detect_rebuild_inconsistency(
            job=job,
            runtime_has_active_executor=self.runtime_has_active_executor,
            lock_ttl_seconds=self.lock_ttl_seconds,
        )

        decision = determine_recovery_action(
            inconsistency=inconsistency,
            lock_is_valid=lock_is_valid,
        )

        decision = self._apply_owner_mismatch_override(decision, inconsistency, lock_is_valid, job)

        if increment_metric and inconsistency.inconsistency_type != InconsistencyType.NONE:
            self.increment_recovery_trigger(inconsistency.inconsistency_type.value)

        if not decision.safe_to_execute:
            logger.warning("Execution blocked: %s", decision.reason)

        return decision

    def evaluate_state(self) -> RecoveryAction:
        """
        Evaluate DB state, runtime state, and lock state together.

        Returns:
            RecoveryAction: The safe action to take.
        """
        return self._evaluate_decision().action

    def ensure_safe_to_execute(self) -> None:
        """
        Enforce execution blocking rules and perform recovery actions.

        For RESET decisions, this automatically resets the orphaned job state
        before allowing execution to proceed.

        Raises:
            ExecutionBlockedError: If the execution is not safe (UNSAFE, WAIT)
                after any automatic recovery attempts.
        """
        decision = self._evaluate_decision()

        if decision.action == RecoveryAction.RESET:
            # Attempt automatic recovery by resetting the orphaned job
            logger.info("Recovery action RESET: attempting to reset orphaned job state. Reason: %s", decision.reason)
            try:
                self._perform_reset_recovery()
                # After successful reset, re-evaluate to confirm safe to proceed
                # Skip metric increment on re-evaluation to avoid double-counting
                decision = self._evaluate_decision(increment_metric=False)
                if decision.action != RecoveryAction.RESUME:
                    # Post-reset state still unsafe - use bounded reason to avoid leaking DB details
                    raise ExecutionBlockedError(
                        f"Reset recovery completed but state still unsafe: action={decision.action.value}"
                    )
                logger.info("Reset recovery successful - execution can proceed")
            except ExecutionBlockedError:
                # Re-raise ExecutionBlockedError as-is (already sanitized above)
                raise
            except Exception as exc:
                # Reset failed - block execution with bounded exception type only
                raise ExecutionBlockedError(f"Reset recovery failed: {type(exc).__name__}") from exc
        elif decision.action != RecoveryAction.RESUME:
            # Execution blocked - log full reason but expose only bounded info in exception
            logger.warning(
                "Execution blocked by recovery gate: action=%s, inconsistency=%s",
                decision.action.value,
                decision.inconsistency_type.value if decision.inconsistency_type else "unknown",
            )
            raise ExecutionBlockedError(
                f"Execution blocked: action={decision.action.value}, "
                f"inconsistency={decision.inconsistency_type.value if decision.inconsistency_type else 'unknown'}"
            )

    def _perform_reset_recovery(self) -> None:
        """
        Reset an orphaned rebuild job to allow new execution.

        CRITICAL: Must reacquire lock if expired before mutating RUNNING job state.
        Without a valid lock, multiple workers can perform concurrent reset operations
        leading to database corruption.

        This transitions the orphaned RUNNING job to FAILED with a clear
        marker that it was recovered/cleaned up by the recovery system.
        """
        from src.data.db_models import RebuildJobStatus

        # Check lock state and reacquire if expired
        lock_state = self.lock.check_state()
        if lock_state != LockState.VALID:
            logger.warning(
                "Lock state is %s before RESET recovery, attempting reacquisition...",
                lock_state.value,
            )
            if not self.lock.acquire():
                msg = f"Cannot perform RESET recovery without valid lock (state={lock_state.value})"
                logger.error("%s: %s", type(ExecutionBlockedError).__name__, msg)
                raise ExecutionBlockedError(msg)
            logger.info("Successfully reacquired lock for RESET recovery")

        try:
            session = self.session_factory()
            try:
                repo = AssetGraphRepository(session)
                # Get the active rebuild job
                active_job = repo.get_active_rebuild_state()

                if active_job and active_job.status == RebuildJobStatus.RUNNING:
                    # Transition to FAILED with recovery marker
                    repo.mark_rebuild_job_failed(
                        active_job.job_id,
                        failure_category="recovery_reset",
                        failure_message="Recovered from orphaned state by RecoveryGate",
                        duration_ms=0,  # Unknown duration for orphaned job
                    )
                    session.commit()
                    logger.warning(
                        "Reset orphaned rebuild job %s (previous owner: %s)",
                        active_job.job_id,
                        active_job.active_worker_id or "unknown",
                    )
            finally:
                session.close()
        except Exception as exc:
            # Use bounded logging to prevent DSN/credential leakage in tracebacks
            logger.error("Failed to perform reset recovery: %s", type(exc).__name__)
            raise

"""Recovery gate to prevent execution under unsafe state conditions."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from src.data.distributed_lock import DistributedLock, LockAcquisitionTimeout, LockState
from src.data.repository import AssetGraphRepository
from src.logic.rebuild_failure_detection import InconsistencyType, detect_rebuild_inconsistency
from src.logic.rebuild_recovery import RecoveryAction, RecoveryDecision, determine_recovery_action
from src.observability.facade import ObservabilityEvent, log_event

logger = logging.getLogger(__name__)


class ExecutionBlockedError(Exception):
    """Raised when execution is blocked by the recovery gate.

    The ``action`` attribute carries the string value of the ``RecoveryAction``
    that triggered the block (e.g. ``"wait"``, ``"unsafe"``).  Callers that need
    to distinguish between specific blocking reasons — without re-running the
    gate evaluation — can inspect this attribute instead of parsing the message.

    The ``inconsistency_type`` attribute usually carries the string value of the
    detected ``InconsistencyType`` (e.g. ``"none"``, ``"orphaned_running"``).
    Together with ``action``, it allows callers to determine whether a ``WAIT``
    block is a benign clean-install case
    (``action="wait", inconsistency_type="none"``) or a genuine inconsistency
    that should block execution.

    Note that ``inconsistency_type`` may legitimately be ``None`` for early-return
    blocking paths that do not have a specific inconsistency classification,
    including LOST, UNKNOWN-with-active-job, and reset-failure/error paths.
    Callers should therefore treat ``None`` distinctly rather than assuming every
    blocking decision uses a string such as ``"none"``.
    """

    def __init__(self, message: str, action: str | None = None, inconsistency_type: str | None = None) -> None:
        """Initialize with message and optional caller-inspection attributes.

        Args:
            message: Human-readable description of why execution was blocked.
            action: String value of the ``RecoveryAction`` that triggered the block
                (e.g. ``"wait"``, ``"unsafe"``).  ``None`` when the blocking path
                does not correspond to a single named action (e.g. reset failures).
            inconsistency_type: String value of the detected ``InconsistencyType``
                (e.g. ``"none"``, ``"crash_suspicion"``).  ``None`` when the blocking
                path does not have a known inconsistency (e.g. reset failures).
        """
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
        self.lock_was_reacquired = False

    def _create_unsafe_decision_from_error(self, exc: Exception, error_context: str, log_level: str = "warning"):
        """Create an unsafe recovery decision from an error.

        Create a RecoveryDecision that blocks execution (UNSAFE) and logs a sanitized
        observability event for the provided error context.

        Parameters:
            exc (Exception): The caught exception used to build the decision reason.
            error_context (str): Short description of where the error occurred.
            log_level (str): "warning" or "error" determining the event severity.

        Returns:
            RecoveryDecision: Decision with action UNSAFE, safe_to_execute=False,
                inconsistency_type=None, and reason formatted as "<ExceptionType>: <error_context>".
        """
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

        # Do not increment orphaned-running metrics from this generic error path.
        # At this point we only know state evaluation failed; we do not know that
        # an ORPHANED_RUNNING inconsistency was actually detected.
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

        return RecoveryDecision(
            action=RecoveryAction.UNSAFE,
            reason=reason,
            inconsistency_type=None,
            safe_to_execute=False,
        )

    def _apply_owner_mismatch_override(self, decision, inconsistency, lock_is_valid, job):
        """Override the recovery decision when an owner mismatch occurs.

        Override the provided recovery decision when an ORPHANED_RUNNING inconsistency indicates
        the job is owned by a different worker.

        If the inconsistency is not ORPHANED_RUNNING or no job is present, the original decision
        is returned unchanged. When the job's active worker ID differs from the current lock holder,
        this routine checks the job's last heartbeat: if a heartbeat exists and its age is less
        than the lock TTL, it forces an UNSAFE decision to avoid resetting a likely healthy remote
        worker; if the heartbeat is missing or stale, it forces a RESET decision treating the
        job as orphaned.

        Parameters:
            decision: The incoming RecoveryDecision to potentially override.
            inconsistency: The detected rebuild inconsistency (used to check for ORPHANED_RUNNING).
            lock_is_valid: Whether the distributed lock is currently valid (not used to skip checks).
            job: The active rebuild job record (may be None).

        Returns:
            A RecoveryDecision: either the original decision or a modified UNSAFE/RESET decision when
                an owner-mismatch with fresh or stale/missing heartbeat is detected.
        """
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
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="recovery_gate_owner_mismatch_fresh_heartbeat",
                        message=(
                            f"Owner mismatch with FRESH heartbeat (age={heartbeat_age_seconds:.1f}s): "
                            f"job.active_worker_id:{job.active_worker_id}, "
                            f"lock.holder_id:{self.lock.holder_id}. Forcing unsafe/blocking "
                            "decision to avoid resetting a healthy remote worker."
                        ),
                        metadata={
                            "heartbeat_age": heartbeat_age_seconds,
                            "job_worker_id": job.active_worker_id,
                            "lock_holder_id": self.lock.holder_id,
                        },
                    ),
                )
                return RecoveryDecision(
                    action=RecoveryAction.UNSAFE,
                    reason=(
                        "Running rebuild is owned by a different worker with a fresh heartbeat "
                        f"(job worker_id={job.active_worker_id!r}, "
                        f"current lock holder_id={self.lock.holder_id!r}); "
                        "local recovery is unsafe"
                    ),
                    inconsistency_type=decision.inconsistency_type,
                    safe_to_execute=False,
                )

        # Stale or missing heartbeat with owner mismatch = orphaned job
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="recovery_gate_owner_mismatch_stale_heartbeat",
                message=(
                    "Owner mismatch with STALE/MISSING heartbeat detected: "
                    f"job.active_worker_id:{job.active_worker_id}, "
                    f"lock.holder_id:{self.lock.holder_id}. Downgrading to RESET."
                ),
                metadata={"job_worker_id": job.active_worker_id, "lock_holder_id": self.lock.holder_id},
            ),
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

    def _handle_unknown_lock_state(self, job) -> RecoveryDecision:
        """Handle the UNKNOWN lock state, distinguishing between clean install vs wrong owner."""
        if job is None:
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="recovery_gate_clean_install_detected",
                    message=(
                        "Lock state is UNKNOWN with no active job; "
                        "treating as clean install WAIT until lock is acquired"
                    ),
                ),
            )
            return RecoveryDecision(
                action=RecoveryAction.WAIT,
                reason="Lock state is unknown with no active rebuild job; waiting until lock is acquired",
                inconsistency_type=InconsistencyType.NONE,
                safe_to_execute=False,
            )

        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="recovery_gate_lock_unknown_with_active_job",
                message="Execution blocked: Lock state is UNKNOWN with active job (wrong owner or no lock)",
            ),
        )
        return RecoveryDecision(
            action=RecoveryAction.UNSAFE,
            reason="Lock state is unknown with active rebuild job",
            inconsistency_type=None,
            safe_to_execute=False,
        )

    def get_recovery_decision(self, increment_metric: bool = True):
        """
        Decide the appropriate recovery action based on lock, database, and runtime state.

        Evaluates distributed lock state, queries the active rebuild job, detects rebuild
        inconsistencies, applies owner-mismatch overrides, and optionally increments a
        recovery trigger metric.

        Parameters:
            increment_metric (bool): If True, increment the recovery trigger metric when an
                inconsistency (other than `InconsistencyType.NONE`) is detected. Set to False
                when re-evaluating after recovery to avoid double-counting.

        Returns:
            RecoveryDecision: Decision containing the chosen `action`, `reason`,
                `inconsistency_type`, and `safe_to_execute` flag.
        """
        lock_state = self.lock.check_state()
        job = None

        # LOST state always blocks - cannot determine lock ownership due to DB error
        if lock_state == LockState.LOST:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="recovery_gate_lock_lost",
                    message="Execution blocked: Lock state is LOST (database connectivity failure)",
                ),
            )
            return RecoveryDecision(
                action=RecoveryAction.UNSAFE,
                reason="Lock state is lost (database connectivity failure)",
                inconsistency_type=None,
                safe_to_execute=False,
            )

        lock_is_valid = lock_state == LockState.VALID

        try:
            with self.session_factory() as session:
                repo = AssetGraphRepository(session)
                job = repo.get_active_rebuild_state()
        except ValueError as exc:
            return self._create_unsafe_decision_from_error(exc, "active rebuild state query failed")
        except sqlalchemy_exc.SQLAlchemyError as exc:
            return self._create_unsafe_decision_from_error(exc, "database error during rebuild state query")
        except Exception as exc:
            return self._create_unsafe_decision_from_error(exc, "unexpected error during rebuild state query", "error")

        # UNKNOWN state handling: distinguish between clean install vs wrong owner
        if lock_state == LockState.UNKNOWN:
            return self._handle_unknown_lock_state(job)

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
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="recovery_gate_execution_unsafe",
                    message=f"Execution blocked: {decision.reason}",
                    metadata={"reason": decision.reason},
                ),
            )

        return decision

    def evaluate_state(self) -> RecoveryAction:
        """
        Evaluate DB state, runtime state, and lock state together.

        Returns:
            RecoveryAction: The safe action to take.
        """
        return self.get_recovery_decision().action

    def ensure_safe_to_execute(self, cancellation_event: threading.Event | None = None) -> None:
        """
        Enforce execution blocking rules and perform recovery actions.

        For RESET decisions, this automatically resets the orphaned job state
        before allowing execution to proceed.

        Args:
            cancellation_event: Optional event to signal cancellation.

        Raises:
            ExecutionBlockedError: If the execution is not safe (UNSAFE, WAIT)
                after any automatic recovery attempts.
        """
        self.lock_was_reacquired = False
        decision = self.get_recovery_decision()

        if decision.action == RecoveryAction.RESET:
            # Check cancellation before starting recovery
            if cancellation_event and cancellation_event.is_set():
                return

            # Attempt automatic recovery by resetting the orphaned job
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="recovery_gate_reset_recovery_initiated",
                    message=f"Recovery action RESET: attempting to reset orphaned job state. Reason: {decision.reason}",
                    metadata={"reason": decision.reason},
                ),
            )
            try:
                self._perform_reset_recovery(cancellation_event=cancellation_event)

                # Check cancellation after recovery but before re-evaluation
                if cancellation_event and cancellation_event.is_set():
                    return

                # After successful reset, re-evaluate to confirm safe to proceed
                # Skip metric increment on re-evaluation to avoid double-counting
                decision = self.get_recovery_decision(increment_metric=False)
                if decision.action != RecoveryAction.RESUME:
                    # Post-reset state still unsafe - use bounded reason to avoid leaking DB details
                    raise ExecutionBlockedError(
                        f"Reset recovery completed but state still unsafe: action={decision.action.value}",
                        action=decision.action.value,
                        inconsistency_type=(decision.inconsistency_type.value if decision.inconsistency_type else None),
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
                # Re-raise ExecutionBlockedError as-is (already sanitized above)
                raise
            except sqlalchemy_exc.SQLAlchemyError as exc:
                # Expected database error during reset - block execution
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
                # Unexpected error - block execution with bounded exception type only
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
        elif decision.action != RecoveryAction.RESUME:
            # Execution blocked - log full reason but expose only bounded info in exception
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="recovery_gate_execution_blocked_final",
                    message=(
                        f"Execution blocked by recovery gate: action={decision.action.value}, "
                        "inconsistency="
                        f"{decision.inconsistency_type.value if decision.inconsistency_type else 'unknown'}"
                    ),
                    metadata={
                        "action": decision.action.value,
                        "inconsistency": (
                            decision.inconsistency_type.value if decision.inconsistency_type else "unknown"
                        ),
                    },
                ),
            )
            raise ExecutionBlockedError(
                f"Execution blocked: action={decision.action.value}, "
                f"inconsistency={decision.inconsistency_type.value if decision.inconsistency_type else 'unknown'}",
                action=decision.action.value,
                inconsistency_type=decision.inconsistency_type.value if decision.inconsistency_type else None,
            )

    def _perform_reset_recovery(self, cancellation_event: threading.Event | None = None) -> None:
        """
        Reset an orphaned RUNNING rebuild job so a new execution can proceed.

        If the lock is not valid, attempts to reacquire it and raises ExecutionBlockedError if
        acquisition fails. If an active rebuild job exists with status RUNNING, marks that job
        as FAILED with failure_category "recovery_reset" and commits the change. May set
        self.lock_was_reacquired to True when the lock is successfully reacquired.

        Args:
            cancellation_event: Optional event to signal cancellation.

        Raises:
            ExecutionBlockedError: if the lock cannot be reacquired and reset recovery cannot proceed.
        """
        from src.data.db_models import RebuildJobStatus

        # Check lock state and reacquire if expired
        lock_state = self.lock.check_state()
        if lock_state != LockState.VALID:
            # Check cancellation before lock acquisition attempt
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

        # Check cancellation before DB operations
        if cancellation_event and cancellation_event.is_set():
            return

        try:
            with self.session_factory() as session:
                repo = AssetGraphRepository(session)
                # Get the active rebuild job
                active_job = repo.get_active_rebuild_state()

                if active_job and active_job.status == RebuildJobStatus.RUNNING:
                    # Check cancellation before mutation
                    if cancellation_event and cancellation_event.is_set():
                        return

                    # Transition to FAILED with recovery marker
                    repo.mark_rebuild_job_failed(
                        active_job.job_id,
                        failure_category="recovery_reset",
                        failure_message="Recovered from orphaned state by RecoveryGate",
                        duration_ms=0,  # Unknown duration for orphaned job
                    )
                    session.commit()
                    log_event(
                        logger,
                        logging.WARNING,
                        ObservabilityEvent(
                            event="recovery_gate_orphaned_job_reset",
                            message=(
                                f"Reset orphaned rebuild job {active_job.job_id} "
                                "(previous owner: "
                                f"{active_job.active_worker_id or 'unknown'})"
                            ),
                            metadata={
                                "job_id": active_job.job_id,
                                "previous_owner": active_job.active_worker_id or "unknown",
                            },
                        ),
                    )
        except Exception as exc:
            # Use bounded logging to prevent DSN/credential leakage in tracebacks
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

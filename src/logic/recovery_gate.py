"""Recovery gate to prevent execution under unsafe state conditions."""

from __future__ import annotations

import logging
from typing import Callable

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

    def _evaluate_decision(self):
        """
        Evaluate lock, DB, and runtime state and return a recovery decision.

        Returns:
            RecoveryDecision: Deterministic decision used by both
                evaluate_state() and ensure_safe_to_execute().
        """
        from src.logic.rebuild_recovery import RecoveryDecision

        lock_state = self.lock.check_state()
        job = None

        if lock_state in (LockState.UNKNOWN, LockState.LOST):
            logger.warning(
                "Execution blocked: Lock state is %s",
                lock_state.value,
            )
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
                logger.warning("Execution blocked: %s", exc)
                self.increment_recovery_trigger(InconsistencyType.ORPHANED_RUNNING.value)
                return RecoveryDecision(
                    action=RecoveryAction.UNSAFE,
                    reason=str(exc),
                    inconsistency_type=InconsistencyType.ORPHANED_RUNNING,
                    safe_to_execute=False,
                )

        inconsistency = detect_rebuild_inconsistency(
            job=job,
            runtime_has_active_executor=self.runtime_has_active_executor,
            lock_ttl_seconds=self.lock_ttl_seconds,
        )

        if (
            inconsistency.inconsistency_type == InconsistencyType.ORPHANED_RUNNING
            and lock_is_valid
            and job is not None
            and job.active_worker_id != self.lock.holder_id
        ):
            # Lock validity reflects current lock-row ownership. If the DB job
            # owner differs from this lock holder (or is unset), treat this as a
            # takeover/reset condition rather than an in-process split-brain.
            lock_is_valid = False

        decision = determine_recovery_action(
            inconsistency=inconsistency,
            lock_is_valid=lock_is_valid,
        )

        if inconsistency.inconsistency_type != InconsistencyType.NONE:
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
        Enforce execution blocking rules.

        Raises:
            ExecutionBlockedError: If the execution is not safe (e.g. UNSAFE, WAIT, RESET).
        """
        decision = self._evaluate_decision()
        if decision.action != RecoveryAction.RESUME:
            raise ExecutionBlockedError(
                f"Execution blocked: action={decision.action.value}, reason={decision.reason}"
            )

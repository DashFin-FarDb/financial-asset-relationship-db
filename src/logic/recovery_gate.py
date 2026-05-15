"""Recovery gate to prevent execution under unsafe state conditions."""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.orm import Session

from src.data.distributed_lock import DistributedLock, LockState
from src.data.repository import AssetGraphRepository
from src.logic.rebuild_failure_detection import (
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
        runtime_has_active_executor: bool = False,
        lock_ttl_seconds: int = 300,
    ) -> None:
        """
        Initialize the RecoveryGate.

        Args:
            session_factory: Factory for creating database sessions.
            lock: The distributed lock instance.
            runtime_has_active_executor: Whether the runtime currently has an active executor.
            lock_ttl_seconds: TTL seconds for the lock.
        """
        self.session_factory = session_factory
        self.lock = lock
        self.runtime_has_active_executor = runtime_has_active_executor
        self.lock_ttl_seconds = lock_ttl_seconds

    def evaluate_state(self) -> RecoveryAction:
        """
        Evaluate DB state, runtime state, and lock state together.

        Returns:
            RecoveryAction: The safe action to take.
        """
        lock_state = self.lock.check_state()

        if lock_state in (LockState.UNKNOWN, LockState.LOST):
            logger.warning(
                "Execution blocked: Lock state is %s",
                lock_state.value,
            )
            return RecoveryAction.UNSAFE

        lock_is_valid = (lock_state == LockState.VALID)

        with self.session_factory() as session:
            repo = AssetGraphRepository(session)
            job = repo.get_active_rebuild_state()

        inconsistency = detect_rebuild_inconsistency(
            job=job,
            runtime_has_active_executor=self.runtime_has_active_executor,
            lock_ttl_seconds=self.lock_ttl_seconds,
        )

        decision = determine_recovery_action(
            inconsistency=inconsistency,
            lock_is_valid=lock_is_valid,
        )

        if not decision.safe_to_execute:
            logger.warning("Execution blocked: %s", decision.reason)

        return decision.action

    def ensure_safe_to_execute(self) -> None:
        """
        Enforce execution blocking rules.

        Raises:
            ExecutionBlockedError: If the execution is not safe (e.g. UNSAFE, WAIT, RESET).
        """
        action = self.evaluate_state()
        if action != RecoveryAction.RESUME:
            raise ExecutionBlockedError(f"Execution is blocked. Recovery action required: {action.value}")

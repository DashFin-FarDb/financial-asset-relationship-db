"""Drift evaluator implementation for rebuild state reconciliation.

This module adapts the existing rebuild failure detection logic to the
ReconciliationEngine interface, bridging the gap between the legacy
drift detection system and the new reconciliation abstraction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from src.data.distributed_lock import DistributedLock, LockState
from src.data.repository import AssetGraphRepository
from src.logic.rebuild_failure_detection import (
    InconsistencyType,
    detect_rebuild_inconsistency,
)
from src.logic.reconciliation_engine import Severity

if TYPE_CHECKING:
    from src.data.db_models import RebuildJobORM

logger = logging.getLogger(__name__)


class RebuildDriftEvaluator:
    """Evaluates drift between desired rebuild state and observed rebuild state.

    This implements the DriftEvaluator protocol for rebuild coordination,
    integrating with the existing rebuild_failure_detection module.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        lock: DistributedLock,
        runtime_has_active_executor: bool = False,
        lock_ttl_seconds: int = 300,
    ) -> None:
        """Initialize rebuild drift evaluator.

        Args:
            session_factory: Factory for creating database sessions
            lock: Distributed lock instance
            runtime_has_active_executor: Whether runtime has active rebuild executor
            lock_ttl_seconds: Lock TTL threshold in seconds
        """
        self.session_factory = session_factory
        self.lock = lock
        self.runtime_has_active_executor = runtime_has_active_executor
        self.lock_ttl_seconds = lock_ttl_seconds

    def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
        """Evaluate drift between desired and observed rebuild states.

        Returns:
            Tuple of (drift_type, severity, metadata)
        """
        # Check lock state first
        lock_state = self.lock.check_state()

        # Handle LOST lock state as critical drift
        if lock_state == LockState.LOST:
            return (
                "lock_lost",
                Severity.CRITICAL,
                {
                    "lock_state": lock_state.value,
                    "lock_is_valid": False,
                    "reason": "Distributed lock was lost during operation",
                    "runtime_has_active_executor": self.runtime_has_active_executor,
                },
            )

        lock_is_valid = lock_state == LockState.VALID

        # Get current rebuild job from DB
        job = self._get_active_rebuild_job()

        # Detect inconsistency using existing logic
        inconsistency = detect_rebuild_inconsistency(
            job=job,
            runtime_has_active_executor=self.runtime_has_active_executor,
            lock_ttl_seconds=self.lock_ttl_seconds,
        )

        # Map inconsistency to drift classification
        drift_type = inconsistency.inconsistency_type.value
        severity = self._classify_severity(inconsistency.inconsistency_type, lock_is_valid)

        # Build metadata
        metadata: dict[str, str | int | float | bool | None] = {
            "job_id": inconsistency.job_id,
            "reason": inconsistency.reason,
            "lock_state": lock_state.value,
            "lock_is_valid": lock_is_valid,
            "runtime_has_active_executor": self.runtime_has_active_executor,
            "detected_at": inconsistency.detected_at.isoformat(),
        }

        if job:
            # Handle heartbeat safely - check if it has isoformat before calling
            heartbeat_str: str | None = None
            if job.last_heartbeat_at is not None:
                if hasattr(job.last_heartbeat_at, "isoformat"):
                    heartbeat_str = job.last_heartbeat_at.isoformat()
                else:
                    heartbeat_str = str(job.last_heartbeat_at)

            metadata.update(
                {
                    "job_status": job.status.value if hasattr(job.status, "value") else str(job.status),
                    "active_worker_id": job.active_worker_id,
                    "last_heartbeat_at": heartbeat_str,
                }
            )

        logger.debug(
            "Drift evaluation completed: type=%s, severity=%s, lock_valid=%s",
            drift_type,
            severity.value,
            lock_is_valid,
        )

        return drift_type, severity, metadata

    def _get_active_rebuild_job(self) -> RebuildJobORM | None:
        """Get active rebuild job from database.

        Raises:
            ValueError: If database integrity constraint violated (e.g., multiple RUNNING jobs)
        """
        from sqlalchemy.exc import SQLAlchemyError

        try:
            with self.session_factory() as session:
                repo = AssetGraphRepository(session)
                return repo.get_active_rebuild_state()
        except ValueError:
            # DB integrity violation - let it propagate as this indicates serious state corruption
            raise
        except (SQLAlchemyError, OSError) as exc:
            # Transient DB errors - log and treat as "no job" to allow graceful degradation
            logger.warning(
                "Failed to retrieve active rebuild job: %s",
                type(exc).__name__,
            )
            return None

    def _classify_severity(  # pylint: disable=too-many-return-statements  # Each inconsistency type requires distinct severity mapping; table-driven refactor deferred to Phase 2
        self,
        inconsistency_type: InconsistencyType,
        lock_is_valid: bool,
    ) -> Severity:
        """Classify severity based on inconsistency type and lock state.

        Args:
            inconsistency_type: Detected inconsistency type
            lock_is_valid: Whether distributed lock is currently valid

        Returns:
            Severity classification
        """
        # No inconsistency
        if inconsistency_type == InconsistencyType.NONE:
            return Severity.NONE

        # Critical: Orphaned running with valid lock (split-brain risk)
        if inconsistency_type == InconsistencyType.ORPHANED_RUNNING and lock_is_valid:
            return Severity.CRITICAL

        # Critical: Zombie executor (runtime/DB divergence)
        if inconsistency_type == InconsistencyType.ZOMBIE_EXECUTOR:
            return Severity.CRITICAL

        # High: Orphaned running without lock (can be safely reset)
        if inconsistency_type == InconsistencyType.ORPHANED_RUNNING:
            return Severity.HIGH

        # High: Crash suspicion
        if inconsistency_type == InconsistencyType.CRASH_SUSPICION:
            return Severity.HIGH

        # Medium: Stale ownership
        if inconsistency_type == InconsistencyType.STALE_OWNERSHIP:
            return Severity.MEDIUM

        # Default to medium for unknown types
        logger.warning("Unknown inconsistency type %s - defaulting to MEDIUM severity", inconsistency_type)
        return Severity.MEDIUM

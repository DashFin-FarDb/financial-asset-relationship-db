"""Drift evaluator implementation for rebuild state reconciliation.

This module adapts the existing rebuild failure detection logic to the
ReconciliationEngine interface, bridging the gap between the legacy
drift detection system and the new reconciliation abstraction.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError
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
        try:
            job = self._get_active_rebuild_job()
        except ValueError:
            raise
        except (SQLAlchemyError, OSError) as exc:
            return (
                "persistence_unavailable",
                Severity.CRITICAL,
                {
                    "error_type": type(exc).__name__,
                    "lock_state": lock_state.value,
                    "lock_is_valid": lock_is_valid,
                    "reason": "Unable to read rebuild state from persistence",
                    "runtime_has_active_executor": self.runtime_has_active_executor,
                },
            )

        # Detect inconsistency using existing logic
        inconsistency = detect_rebuild_inconsistency(
            job=job,
            runtime_has_active_executor=self.runtime_has_active_executor,
            lock_ttl_seconds=self.lock_ttl_seconds,
        )

        # Map inconsistency to drift classification
        drift_type = inconsistency.inconsistency_type.value

        # Detect owner mismatch for orphaned running jobs
        owner_mismatch, owner_mismatch_with_stale_heartbeat = self._detect_owner_mismatch(
            job, inconsistency.inconsistency_type
        )

        severity = self._classify_severity(
            inconsistency.inconsistency_type, lock_is_valid, owner_mismatch_with_stale_heartbeat
        )

        # Build metadata
        metadata: dict[str, str | int | float | bool | None] = {
            "job_id": inconsistency.job_id,
            "reason": inconsistency.reason,
            "lock_state": lock_state.value,
            "lock_is_valid": lock_is_valid,
            "runtime_has_active_executor": self.runtime_has_active_executor,
            "detected_at": inconsistency.detected_at.isoformat(),
        }

        # Add job-specific metadata
        metadata.update(self._build_job_metadata(job, owner_mismatch))

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
            SQLAlchemyError: If persistence cannot be queried
            OSError: If the underlying database access fails
        """
        with self.session_factory() as session:
            repo = AssetGraphRepository(session)
            return repo.get_active_rebuild_state()

    def _parse_heartbeat_time(self, heartbeat_at: datetime | str | None) -> datetime | None:
        """Parse heartbeat timestamp from various formats.

        Args:
            heartbeat_at: Heartbeat timestamp (datetime, ISO string, or None)

        Returns:
            Timezone-aware datetime or None if unparseable or missing
        """
        if heartbeat_at is None:
            return None

        try:
            heartbeat_time = heartbeat_at
            if isinstance(heartbeat_time, str):
                # Normalize trailing 'Z' to '+00:00' for compatibility with fromisoformat
                heartbeat_str = (
                    heartbeat_time[:-1] + "+00:00"
                    if heartbeat_time.upper().endswith("Z")
                    else heartbeat_time
                )
                heartbeat_time = datetime.fromisoformat(heartbeat_str)
            # Ensure timezone-aware
            # Note: Assumes DB returns UTC-naive datetimes or timezone-aware UTC datetimes
            if heartbeat_time.tzinfo is None:
                heartbeat_time = heartbeat_time.replace(tzinfo=timezone.utc)
            return heartbeat_time
        except (ValueError, AttributeError, TypeError) as exc:
            # Unparseable heartbeat treated as None (caller will treat as stale)
            logger.warning(
                "Failed to parse heartbeat timestamp, treating as stale", 
                exc_info=True
            )
            return None

    def _is_heartbeat_stale(self, heartbeat_at: datetime | str | None) -> bool:
        """Check if heartbeat timestamp is stale or missing.

        Args:
            heartbeat_at: Heartbeat timestamp to check

        Returns:
            True if stale or unparseable, False if fresh
        """
        heartbeat_time = self._parse_heartbeat_time(heartbeat_at)
        if heartbeat_time is None:
            return True  # Missing or unparseable is considered stale

        now = datetime.now(timezone.utc)
        heartbeat_age_seconds = (now - heartbeat_time).total_seconds()
        return heartbeat_age_seconds >= self.lock_ttl_seconds

    def _detect_owner_mismatch(
        self, job: RebuildJobORM | None, inconsistency_type: InconsistencyType
    ) -> tuple[bool, bool]:
        """Detect owner mismatch between job and lock holder.

        Args:
            job: Current rebuild job (or None)
            inconsistency_type: Detected inconsistency type

        Returns:
            Tuple of (owner_mismatch, owner_mismatch_with_stale_heartbeat)
        """
        if not job or inconsistency_type != InconsistencyType.ORPHANED_RUNNING:
            return False, False

        owner_mismatch = (
            job.active_worker_id is not None
            and self.lock.holder_id is not None
            and job.active_worker_id != self.lock.holder_id
        )

        if not owner_mismatch:
            return False, False

        # Check if heartbeat is stale or missing
        # This preserves RecoveryGate's resettable orphaned-owner mismatch path
        heartbeat_is_stale = self._is_heartbeat_stale(job.last_heartbeat_at)
        owner_mismatch_with_stale_heartbeat = heartbeat_is_stale

        return owner_mismatch, owner_mismatch_with_stale_heartbeat

    def _build_job_metadata(self, job: RebuildJobORM | None, owner_mismatch: bool) -> dict[str, str | int | float | bool | None]:
        """Build metadata dictionary for job state.

        Args:
            job: Current rebuild job (or None)
            owner_mismatch: Whether job owner mismatches lock holder

        Returns:
            Metadata dictionary with job details
        """
        if not job:
            return {}

        # Handle heartbeat safely - check if it has isoformat before calling
        heartbeat_str: str | None = None
        if job.last_heartbeat_at is not None:
            if hasattr(job.last_heartbeat_at, "isoformat"):
                heartbeat_str = job.last_heartbeat_at.isoformat()
            else:
                heartbeat_str = str(job.last_heartbeat_at)

        return {
            "job_status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "active_worker_id": job.active_worker_id,
            "last_heartbeat_at": heartbeat_str,
            "owner_mismatch": owner_mismatch,
            "lock_holder_id": self.lock.holder_id,
        }

    def _classify_severity(  # pylint: disable=too-many-return-statements  # Each inconsistency type requires distinct severity mapping; table-driven refactor deferred to Phase 2
        self,
        inconsistency_type: InconsistencyType,
        lock_is_valid: bool,
        owner_mismatch_with_stale_heartbeat: bool = False,
    ) -> Severity:
        """Classify severity based on inconsistency type and lock state.

        Args:
            inconsistency_type: Detected inconsistency type
            lock_is_valid: Whether distributed lock is currently valid
            owner_mismatch_with_stale_heartbeat: Whether job.active_worker_id differs
                from lock.holder_id AND heartbeat is stale/missing (only relevant for
                ORPHANED_RUNNING). When True, allows RecoveryGate to downgrade to RESET.

        Returns:
            Severity classification
        """
        # No inconsistency
        if inconsistency_type == InconsistencyType.NONE:
            return Severity.NONE

        # Critical: Orphaned running with valid lock (split-brain risk)
        # BUT downgrade to HIGH if owner mismatch with stale heartbeat (resettable path)
        if inconsistency_type == InconsistencyType.ORPHANED_RUNNING and lock_is_valid:
            if owner_mismatch_with_stale_heartbeat:
                # Owner mismatch + stale heartbeat allows RecoveryGate to downgrade to RESET
                # This preserves the auto-recoverable path
                return Severity.HIGH
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

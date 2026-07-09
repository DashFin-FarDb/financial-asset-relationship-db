"""
Drift evaluator implementation for rebuild state reconciliation.

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
from src.logic.rebuild_failure_detection import InconsistencyType, detect_rebuild_inconsistency
from src.logic.reconciliation_engine import Severity
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

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
        """
        Create a RebuildDriftEvaluator with its persistence and lock dependencies and runtime configuration.

        Parameters:
            session_factory (Callable[[], Session]): Factory that produces SQLAlchemy
                sessions used to load rebuild state.
            lock (DistributedLock): Distributed lock used to inspect lock state and holder id.
            runtime_has_active_executor (bool): Whether this runtime currently has
                an active rebuild executor; included in metadata and passed to inconsistency detection.
            lock_ttl_seconds (int): Time-to-live in seconds used to determine whether a heartbeat is considered stale.
        """
        self.session_factory = session_factory
        self.lock = lock
        self.runtime_has_active_executor = runtime_has_active_executor
        self.lock_ttl_seconds = lock_ttl_seconds

    def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
        """
        Evaluate rebuild coordination drift and classify its type, severity, and associated metadata.

        Returns:
            tuple[str, Severity, dict[str, str | int | float | bool | None]]:
                - `drift_type`: Classification string describing the detected drift
                  (e.g., `"lock_lost"`, `"persistence_unavailable"`, or an inconsistency type value).
                - `Severity`: Severity enum value for the detected drift.
                - `metadata`: A dictionary with contextual information. Always includes
                  `lock_state`, `lock_is_valid`, `runtime_has_active_executor`, and
                  `detected_at` (when applicable). For normal evaluations the metadata also
                  contains `job_id`, `reason`, and job-specific fields added by
                  `_build_job_metadata()` such as `job_status`, `active_worker_id`,
                  `last_heartbeat_at`, `owner_mismatch`, and `lock_holder_id`. In early-failure
                  cases the metadata contains error-related fields (for example `error_type`
                  and `reason`).
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

        log_event(
            logger,
            logging.DEBUG,
            ObservabilityEvent(
                event="rebuild_drift_evaluation_completed",
                message=(
                    f"Drift evaluation completed: type={drift_type}, "
                    f"severity={severity.value}, lock_valid={lock_is_valid}"
                ),
                metadata={"drift_type": drift_type, "severity": severity.value, "lock_is_valid": lock_is_valid},
            ),
        )

        return drift_type, severity, metadata

    def _get_active_rebuild_job(self) -> RebuildJobORM | None:
        """
        Retrieve the currently active rebuild job from persistence.

        Returns:
            RebuildJobORM | None: The active rebuild job if one exists, otherwise `None`.

        Raises:
            ValueError: If a data integrity constraint is violated (e.g., multiple RUNNING jobs).
            SQLAlchemyError: If the persistence layer cannot be queried.
            OSError: If underlying database access fails.
        """
        with self.session_factory() as session:
            repo = AssetGraphRepository(session)
            return repo.get_active_rebuild_state()

    def _parse_heartbeat_time(self, heartbeat_at: datetime | str | None) -> datetime | None:
        """
        Convert a heartbeat timestamp (datetime, ISO 8601 string, or None) into a timezone-aware UTC datetime.

        Parameters:
            heartbeat_at (datetime | str | None): Heartbeat value to normalize. Strings are parsed as ISO 8601.

        Returns:
            datetime | None: A timezone-aware `datetime` in UTC when parsing succeeds,
                or `None` if `heartbeat_at` is `None` or cannot be parsed.
        """
        if heartbeat_at is None:
            return None

        try:
            heartbeat_time = heartbeat_at
            if isinstance(heartbeat_time, str):
                # Normalize trailing 'Z' to '+00:00' for compatibility with fromisoformat
                heartbeat_str = (
                    heartbeat_time[:-1] + "+00:00" if heartbeat_time.upper().endswith("Z") else heartbeat_time
                )
                heartbeat_time = datetime.fromisoformat(heartbeat_str)
            # Ensure timezone-aware
            # Note: Assumes DB returns UTC-naive datetimes or timezone-aware UTC datetimes
            if heartbeat_time.tzinfo is None:
                heartbeat_time = heartbeat_time.replace(tzinfo=timezone.utc)
            return heartbeat_time
        except (ValueError, AttributeError, TypeError):
            # Unparseable heartbeat treated as None (caller will treat as stale).
            # Expected for string/non-datetime values; avoid including full stack
            # traces for expected parse failures.
            log_event(
                logger,
                logging.DEBUG,
                ObservabilityEvent(
                    event="rebuild_drift_heartbeat_parse_failed",
                    message=f"Failed to parse heartbeat timestamp {heartbeat_at!r}, treating as stale",
                    metadata={"heartbeat_at": str(heartbeat_at)},
                ),
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

        job_active_worker_id = getattr(job, "active_worker_id", None)
        owner_mismatch = (
            job_active_worker_id is not None
            and self.lock.holder_id is not None
            and job_active_worker_id != self.lock.holder_id
        )

        if not owner_mismatch:
            return False, False

        # Check if heartbeat is stale or missing
        # This preserves RecoveryGate's resettable orphaned-owner mismatch path
        last_heartbeat_at = getattr(job, "last_heartbeat_at", None)
        heartbeat_is_stale = self._is_heartbeat_stale(last_heartbeat_at)
        owner_mismatch_with_stale_heartbeat = heartbeat_is_stale

        return owner_mismatch, owner_mismatch_with_stale_heartbeat

    def _build_job_metadata(
        self, job: RebuildJobORM | None, owner_mismatch: bool
    ) -> dict[str, str | int | float | bool | None]:
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
        last_heartbeat_at = getattr(job, "last_heartbeat_at", None)
        if last_heartbeat_at is not None:
            if hasattr(last_heartbeat_at, "isoformat"):
                heartbeat_str = last_heartbeat_at.isoformat()
            else:
                heartbeat_str = str(last_heartbeat_at)

        job_status = getattr(job, "status", None)
        job_status_str: str | None = None
        if job_status is not None:
            job_status_str = job_status.value if hasattr(job_status, "value") else str(job_status)

        return {
            "job_status": job_status_str,
            "active_worker_id": getattr(job, "active_worker_id", None),
            "last_heartbeat_at": heartbeat_str,
            "owner_mismatch": owner_mismatch,
            "lock_holder_id": self.lock.holder_id,
        }

    # Each inconsistency type requires distinct severity mapping; table-driven refactor deferred to Phase 2
    def _classify_severity(  # pylint: disable=too-many-return-statements
        self,
        inconsistency_type: InconsistencyType,
        lock_is_valid: bool,
        owner_mismatch_with_stale_heartbeat: bool = False,
    ) -> Severity:
        """
        Map a rebuild inconsistency and lock state to a Severity level.

        Parameters:
            inconsistency_type (InconsistencyType): The detected rebuild inconsistency.
            lock_is_valid (bool): Whether the distributed lock is currently valid.
            owner_mismatch_with_stale_heartbeat (bool): For ORPHANED_RUNNING, True when the job's
                active_worker_id differs from the lock holder and the job's last heartbeat is stale
                or unparseable; when True this can reduce severity from CRITICAL to HIGH.

        Returns:
            Severity: Severity level representing the urgency of the detected inconsistency.
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
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="rebuild_drift_unknown_inconsistency_severity",
                message=f"Unknown inconsistency type {inconsistency_type} - defaulting to MEDIUM severity",
                metadata={"inconsistency_type": str(inconsistency_type)},
            ),
        )
        return Severity.MEDIUM

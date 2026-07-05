"""Failure detection layer for rebuild coordination.

Stage 5C.1: Provides detection of inconsistent rebuild states without acting on them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from src.data.db_models import RebuildJobORM, RebuildJobStatus

UTC = timezone.utc


logger = logging.getLogger(__name__)


class InconsistencyType(str, Enum):
    """Types of rebuild state inconsistencies."""

    STALE_OWNERSHIP = "stale_ownership"
    ORPHANED_RUNNING = "orphaned_running"
    ZOMBIE_EXECUTOR = "zombie_executor"
    CRASH_SUSPICION = "crash_suspicion"
    NONE = "none"


@dataclass(frozen=True)
class RebuildInconsistency:
    """Detected rebuild state inconsistency."""

    inconsistency_type: InconsistencyType
    job_id: str | None
    reason: str
    detected_at: datetime


def _to_aware_utc(value: datetime) -> datetime:
    """Normalize naive datetimes to timezone-aware UTC (assuming naive inputs are UTC).

    Note: If a naive persisted value was originally stored in a non-UTC timezone,
    this normalization would misinterpret the instant.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def detect_stale_ownership(
    job: RebuildJobORM,
    ttl_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    """
    Detect if rebuild ownership is stale based on heartbeat age.

    A rebuild is considered to have stale ownership when:
    - Status is 'running'
    - AND either:
      - No heartbeat has ever been recorded
      - OR last heartbeat is older than TTL threshold

    Args:
        job: The rebuild job to check.
        ttl_seconds: Time-to-live threshold in seconds.
        now: Current timestamp (for testing); defaults to utcnow().

    Returns:
        True if ownership is stale, False otherwise.
    """
    if job.status != RebuildJobStatus.RUNNING:
        return False

    if job.last_heartbeat_at is None:
        # Running without any heartbeat is stale
        return True

    current_time = _to_aware_utc(now) if now is not None else datetime.now(UTC)
    heartbeat_at = _to_aware_utc(job.last_heartbeat_at)
    age = current_time - heartbeat_at
    return age.total_seconds() > ttl_seconds


def detect_orphaned_running_state(
    job: RebuildJobORM,
    runtime_has_active_executor: bool,
) -> bool:
    """
    Detect if a rebuild job is in running state with no active executor.

    This indicates the runtime state and DB state have diverged, possibly
    due to a crash or unexpected termination.

    Args:
        job: The rebuild job to check.
        runtime_has_active_executor: Whether the runtime currently has an
            active rebuild executor.

    Returns:
        True if state is orphaned (running in DB, no executor in runtime).
    """
    if job.status != RebuildJobStatus.RUNNING:
        return False

    return not runtime_has_active_executor


def detect_crash_suspicion(
    job: RebuildJobORM,
    heartbeat_stale_threshold_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    """
    Detect suspicion of executor crash based on missing heartbeats.

    A crash is suspected when:
    - Job status is 'running'
    - Job has an active_worker_id assigned
    - Last heartbeat is missing or significantly stale

    This is similar to stale ownership but specifically indicates
    a probable crash scenario rather than TTL expiry.

    Args:
        job: The rebuild job to check.
        heartbeat_stale_threshold_seconds: Threshold for considering
            heartbeat stale (typically smaller than lock TTL).
        now: Current timestamp (for testing); defaults to utcnow().

    Returns:
        True if crash is suspected, False otherwise.
    """
    if job.status != RebuildJobStatus.RUNNING or not job.active_worker_id:
        # Not running or no worker assigned - not a crash
        return False

    if job.last_heartbeat_at is None:
        # Worker assigned but never heartbeat - suspicious
        return True

    current_time = _to_aware_utc(now) if now is not None else datetime.now(UTC)
    heartbeat_at = _to_aware_utc(job.last_heartbeat_at)
    age = current_time - heartbeat_at
    return age.total_seconds() > heartbeat_stale_threshold_seconds


def _create_crash_suspicion_reason(job: RebuildJobORM, age_seconds: float | None, threshold: int) -> str:
    """Generate reason message for crash suspicion inconsistency."""
    if age_seconds is not None:
        return (
            f"Job {job.job_id} worker {job.active_worker_id} "
            f"has stale heartbeat (age: {age_seconds}s, threshold: {threshold}s)"
        )
    return f"Job {job.job_id} worker {job.active_worker_id} never sent heartbeat"


def _create_stale_ownership_reason(job: RebuildJobORM, age_seconds: float | None, ttl: int) -> str:
    """Generate reason message for stale ownership inconsistency."""
    if age_seconds is not None:
        return f"Job {job.job_id} ownership stale (heartbeat age: {age_seconds}s > TTL: {ttl}s)"
    return f"Job {job.job_id} ownership stale (no heartbeat recorded)"


def _check_no_job_scenario(runtime_has_active_executor: bool, current_time: datetime) -> RebuildInconsistency:
    """Handle scenario when no job exists in DB."""
    if runtime_has_active_executor:
        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.ZOMBIE_EXECUTOR,
            job_id=None,
            reason="Runtime has active executor but no DB job exists",
            detected_at=current_time,
        )
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.NONE,
        job_id=None,
        reason="No inconsistency detected",
        detected_at=current_time,
    )


def _check_divergence(
    job: RebuildJobORM,
    runtime_has_active_executor: bool,
    current_time: datetime,
) -> RebuildInconsistency | None:
    """Check for orphaned running or zombie executor divergence. Returns None if no divergence."""
    is_db_running = job.status == RebuildJobStatus.RUNNING

    if is_db_running and not runtime_has_active_executor:
        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.ORPHANED_RUNNING,
            job_id=job.job_id,
            reason=f"Job {job.job_id} divergence: DB is 'RUNNING' but no active executor found",
            detected_at=current_time,
        )

    if runtime_has_active_executor and not is_db_running:
        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.ZOMBIE_EXECUTOR,
            job_id=job.job_id,
            reason=f"Job {job.job_id} divergence: active executor found but DB is '{job.status}'",
            detected_at=current_time,
        )

    return None


def _check_heartbeat_issues(
    job: RebuildJobORM,
    heartbeat_threshold: int,
    lock_ttl: int,
    current_time: datetime,
) -> RebuildInconsistency | None:
    """Check for crash suspicion and stale ownership. Returns None if no issues."""
    heartbeat_at = _to_aware_utc(job.last_heartbeat_at) if job.last_heartbeat_at else None
    age_seconds = (current_time - heartbeat_at).total_seconds() if heartbeat_at else None

    # Crash suspicion (uses tighter threshold)
    if detect_crash_suspicion(job, heartbeat_threshold, now=current_time):
        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.CRASH_SUSPICION,
            job_id=job.job_id,
            reason=_create_crash_suspicion_reason(job, age_seconds, heartbeat_threshold),
            detected_at=current_time,
        )

    # Stale ownership (uses full lock TTL)
    if detect_stale_ownership(job, lock_ttl, now=current_time):
        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.STALE_OWNERSHIP,
            job_id=job.job_id,
            reason=_create_stale_ownership_reason(job, age_seconds, lock_ttl),
            detected_at=current_time,
        )

    return None


def detect_rebuild_inconsistency(
    job: RebuildJobORM | None,
    runtime_has_active_executor: bool,
    lock_ttl_seconds: int,
    heartbeat_threshold_seconds: int | None = None,
    *,
    now: datetime | None = None,
) -> RebuildInconsistency:
    """
    Detect rebuild state inconsistencies by aggregating all detection checks.

    This is the main service function for detecting inconsistent rebuild states.
    It runs all detection checks and returns the highest-priority inconsistency
    found (if any).

    Priority order depends on whether a DB job exists:
    1. Zombie executor (runtime has an active executor but no DB job exists)
    2. Orphaned running state (most critical - immediate divergence)
    3. Crash suspicion (indicates probable executor crash)
    4. Stale ownership (indicates lock/heartbeat expiry)
    5. None (consistent state)

    Args:
        job: Current rebuild job from DB (None if no job exists).
        runtime_has_active_executor: Whether runtime has an active executor.
        lock_ttl_seconds: Lock TTL threshold.
        heartbeat_threshold_seconds: Heartbeat staleness threshold; defaults
            to lock_ttl_seconds if not provided.
        now: Current timestamp (for testing); defaults to utcnow().

    Returns:
        RebuildInconsistency describing the detected issue or NONE.
    """
    current_time = _to_aware_utc(now) if now is not None else datetime.now(UTC)
    heartbeat_threshold = heartbeat_threshold_seconds if heartbeat_threshold_seconds is not None else lock_ttl_seconds

    # No job in DB - check if runtime thinks it's running
    if job is None:
        return _check_no_job_scenario(runtime_has_active_executor, current_time)

    # Check for state divergence (highest priority)
    divergence = _check_divergence(job, runtime_has_active_executor, current_time)
    if divergence is not None:
        return divergence

    # Check for heartbeat-based issues (Crash Suspicion or Stale Ownership)
    heartbeat_issue = _check_heartbeat_issues(job, heartbeat_threshold, lock_ttl_seconds, current_time)
    if heartbeat_issue is not None:
        return heartbeat_issue

    # No inconsistency detected
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.NONE,
        job_id=job.job_id,
        reason="No inconsistency detected",
        detected_at=current_time,
    )

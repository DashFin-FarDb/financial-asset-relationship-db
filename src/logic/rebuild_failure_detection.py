"""Failure detection layer for rebuild coordination.

Stage 5C.1: Provides detection of inconsistent rebuild states without acting on them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from src.data.db_models import RebuildJobORM, RebuildJobStatus

logger = logging.getLogger(__name__)


class InconsistencyType(str, Enum):
    """Types of rebuild state inconsistencies."""

    STALE_OWNERSHIP = "stale_ownership"
    ORPHANED_RUNNING = "orphaned_running"
    CRASH_SUSPICION = "crash_suspicion"
    NONE = "none"


@dataclass(frozen=True)
class RebuildInconsistency:
    """Detected rebuild state inconsistency."""

    inconsistency_type: InconsistencyType
    job_id: str | None
    reason: str
    detected_at: datetime


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

    current_time = now or datetime.now(timezone.utc)
    age = current_time - job.last_heartbeat_at
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
    if job.status != RebuildJobStatus.RUNNING:
        return False

    if not job.active_worker_id:
        # No worker assigned - not a crash, just not started
        return False

    if job.last_heartbeat_at is None:
        # Worker assigned but never heartbeat - suspicious
        return True

    current_time = now or datetime.now(timezone.utc)
    age = current_time - job.last_heartbeat_at
    return age.total_seconds() > heartbeat_stale_threshold_seconds


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

    Priority order:
    1. Orphaned running state (most critical - immediate divergence)
    2. Crash suspicion (indicates probable executor crash)
    3. Stale ownership (indicates lock/heartbeat expiry)
    4. None (consistent state)

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
    current_time = now or datetime.now(timezone.utc)
    heartbeat_threshold = heartbeat_threshold_seconds or lock_ttl_seconds

    # No job in DB - check if runtime thinks it's running
    if job is None:
        if runtime_has_active_executor:
            return RebuildInconsistency(
                inconsistency_type=InconsistencyType.ORPHANED_RUNNING,
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

    # Check for state divergence (highest priority)
    is_db_running = job.status == RebuildJobStatus.RUNNING

    if runtime_has_active_executor != is_db_running:
        # This covers both directions:
        # 1. Runtime active + DB NOT running (Zombie)
        # 2. Runtime inactive + DB says running (Ghost/Orphan)

        divergence_detail = (
            f"active executor found but DB is '{job.status}'"
            if runtime_has_active_executor
            else f"DB is 'RUNNING' but no active executor found"
        )

        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.ORPHANED_RUNNING,
            job_id=job.job_id,
            reason=f"Job {job.job_id} divergence: {divergence_detail}",
            detected_at=current_time,
        )

    # Check for crash suspicion (second priority)
    if detect_crash_suspicion(job, heartbeat_threshold, now=current_time):
        age_seconds = (current_time - job.last_heartbeat_at).total_seconds() if job.last_heartbeat_at else None
        reason = (
            f"Job {job.job_id} worker {job.active_worker_id} "
            f"has stale heartbeat (age: {age_seconds}s, threshold: {heartbeat_threshold}s)"
            if age_seconds is not None
            else f"Job {job.job_id} worker {job.active_worker_id} never sent heartbeat"
        )
        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.CRASH_SUSPICION,
            job_id=job.job_id,
            reason=reason,
            detected_at=current_time,
        )

    # Check for stale ownership (third priority)
    if detect_stale_ownership(job, lock_ttl_seconds, now=current_time):
        age_seconds = (current_time - job.last_heartbeat_at).total_seconds() if job.last_heartbeat_at else None
        reason = (
            f"Job {job.job_id} ownership stale " f"(heartbeat age: {age_seconds}s > TTL: {lock_ttl_seconds}s)"
            if age_seconds is not None
            else f"Job {job.job_id} ownership stale (no heartbeat recorded)"
        )
        return RebuildInconsistency(
            inconsistency_type=InconsistencyType.STALE_OWNERSHIP,
            job_id=job.job_id,
            reason=reason,
            detected_at=current_time,
        )

    # No inconsistency detected
    return RebuildInconsistency(
        inconsistency_type=InconsistencyType.NONE,
        job_id=job.job_id,
        reason="No inconsistency detected",
        detected_at=current_time,
    )

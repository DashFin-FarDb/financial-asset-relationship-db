"""Unit tests for rebuild failure detection logic (Stage 5C.1)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.data.db_models import RebuildJobORM, RebuildJobStatus
from src.logic.rebuild_failure_detection import (
    InconsistencyType,
    detect_crash_suspicion,
    detect_orphaned_running_state,
    detect_rebuild_inconsistency,
    detect_stale_ownership,
)


@pytest.fixture
def running_job():
    """Create a running rebuild job for testing."""
    now = datetime.now(timezone.utc)
    return RebuildJobORM(
        job_id="test-job-1",
        requested_by="operator@example.com",
        status=RebuildJobStatus.RUNNING,
        created_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(minutes=5),
        started_at=now - timedelta(minutes=5),
    )


@pytest.fixture
def pending_job():
    """Create a pending rebuild job for testing."""
    now = datetime.now(timezone.utc)
    return RebuildJobORM(
        job_id="test-job-2",
        requested_by="operator@example.com",
        status=RebuildJobStatus.PENDING,
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )


class TestDetectStaleOwnership:
    """Tests for detect_stale_ownership function."""

    def test_returns_false_for_non_running_job(self, pending_job):
        """Non-running jobs cannot have stale ownership."""
        assert detect_stale_ownership(pending_job, ttl_seconds=300) is False

    def test_returns_true_when_no_heartbeat_recorded(self, running_job):
        """Running job without heartbeat is stale."""
        running_job.last_heartbeat_at = None
        assert detect_stale_ownership(running_job, ttl_seconds=300) is True

    def test_returns_true_when_heartbeat_exceeds_ttl(self, running_job):
        """Running job with old heartbeat is stale."""
        now = datetime.now(timezone.utc)
        running_job.last_heartbeat_at = now - timedelta(seconds=400)
        assert detect_stale_ownership(running_job, ttl_seconds=300, now=now) is True

    def test_handles_naive_heartbeat_timestamp(self, running_job):
        """Naive SQLite heartbeat timestamps are normalized before comparison."""
        now = datetime.now(timezone.utc)
        running_job.last_heartbeat_at = (now - timedelta(seconds=400)).replace(tzinfo=None)
        assert detect_stale_ownership(running_job, ttl_seconds=300, now=now) is True

    def test_returns_false_when_heartbeat_within_ttl(self, running_job):
        """Running job with recent heartbeat is not stale."""
        now = datetime.now(timezone.utc)
        running_job.last_heartbeat_at = now - timedelta(seconds=100)
        assert detect_stale_ownership(running_job, ttl_seconds=300, now=now) is False

    def test_boundary_condition_at_exactly_ttl(self, running_job):
        """Heartbeat exactly at TTL threshold is not stale."""
        now = datetime.now(timezone.utc)
        running_job.last_heartbeat_at = now - timedelta(seconds=300)
        # At exactly TTL, age equals TTL, should NOT be stale (>= would make it stale)
        assert detect_stale_ownership(running_job, ttl_seconds=300, now=now) is False

        # Just over TTL should be stale
        running_job.last_heartbeat_at = now - timedelta(seconds=301)
        assert detect_stale_ownership(running_job, ttl_seconds=300, now=now) is True


class TestDetectOrphanedRunningState:
    """Tests for detect_orphaned_running_state function."""

    def test_returns_false_for_non_running_job(self, pending_job):
        """Non-running jobs cannot be orphaned."""
        assert detect_orphaned_running_state(pending_job, runtime_has_active_executor=False) is False

    def test_returns_false_when_executor_active(self, running_job):
        """Running job with active executor is not orphaned."""
        assert detect_orphaned_running_state(running_job, runtime_has_active_executor=True) is False

    def test_returns_true_when_running_without_executor(self, running_job):
        """Running job without active executor is orphaned."""
        assert detect_orphaned_running_state(running_job, runtime_has_active_executor=False) is True


class TestDetectCrashSuspicion:
    """Tests for detect_crash_suspicion function."""

    def test_returns_false_for_non_running_job(self, pending_job):
        """Non-running jobs cannot have crash suspicion."""
        pending_job.active_worker_id = "worker-1"
        assert detect_crash_suspicion(pending_job, heartbeat_stale_threshold_seconds=60) is False

    def test_returns_false_when_no_worker_assigned(self, running_job):
        """Running job without worker assignment is not a crash."""
        running_job.active_worker_id = None
        running_job.last_heartbeat_at = None
        assert detect_crash_suspicion(running_job, heartbeat_stale_threshold_seconds=60) is False

    def test_returns_true_when_worker_assigned_but_no_heartbeat(self, running_job):
        """Worker assigned but no heartbeat indicates crash."""
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = None
        assert detect_crash_suspicion(running_job, heartbeat_stale_threshold_seconds=60) is True

    def test_returns_true_when_heartbeat_exceeds_threshold(self, running_job):
        """Worker with stale heartbeat indicates crash."""
        now = datetime.now(timezone.utc)
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = now - timedelta(seconds=120)
        assert (
            detect_crash_suspicion(
                running_job,
                heartbeat_stale_threshold_seconds=60,
                now=now,
            )
            is True
        )

    def test_handles_naive_heartbeat_timestamp(self, running_job):
        """Naive SQLite heartbeat timestamps are normalized before comparison."""
        now = datetime.now(timezone.utc)
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = (now - timedelta(seconds=120)).replace(tzinfo=None)
        assert detect_crash_suspicion(running_job, heartbeat_stale_threshold_seconds=60, now=now) is True

    def test_returns_false_when_heartbeat_fresh(self, running_job):
        """Worker with recent heartbeat is not crashed."""
        now = datetime.now(timezone.utc)
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = now - timedelta(seconds=30)
        assert (
            detect_crash_suspicion(
                running_job,
                heartbeat_stale_threshold_seconds=60,
                now=now,
            )
            is False
        )


class TestDetectRebuildInconsistency:
    """Tests for detect_rebuild_inconsistency main service function."""

    def test_returns_none_when_no_job_and_no_executor(self):
        """No inconsistency when no job and no executor."""
        inconsistency = detect_rebuild_inconsistency(
            job=None,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.NONE
        assert inconsistency.job_id is None

    def test_detects_zombie_executor_when_no_job_but_executor_active(self):
        """Zombie executor state when executor exists but no DB job."""
        inconsistency = detect_rebuild_inconsistency(
            job=None,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.ZOMBIE_EXECUTOR
        assert inconsistency.job_id is None
        assert "no DB job exists" in inconsistency.reason

    def test_detects_orphaned_running_when_job_running_but_no_executor(self, running_job):
        """Orphaned running state when job running but no executor."""
        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.ORPHANED_RUNNING
        assert inconsistency.job_id == running_job.job_id
        assert "no active executor" in inconsistency.reason

    def test_detects_zombie_executor_when_runtime_active_but_db_not_running(self, pending_job):
        """Runtime active while DB job is not running should be zombie executor."""
        inconsistency = detect_rebuild_inconsistency(
            job=pending_job,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.ZOMBIE_EXECUTOR
        assert inconsistency.job_id == pending_job.job_id
        assert "active executor found but DB is" in inconsistency.reason

    def test_detects_crash_suspicion_when_worker_assigned_no_heartbeat(self, running_job):
        """Crash suspicion when worker assigned but no heartbeat."""
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = None

        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
            heartbeat_threshold_seconds=60,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.CRASH_SUSPICION
        assert inconsistency.job_id == running_job.job_id
        assert "never sent heartbeat" in inconsistency.reason

    def test_detects_crash_suspicion_when_heartbeat_stale(self, running_job):
        """Crash suspicion when heartbeat is stale."""
        now = datetime.now(timezone.utc)
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = now - timedelta(seconds=120)

        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
            heartbeat_threshold_seconds=60,
            now=now,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.CRASH_SUSPICION
        assert inconsistency.job_id == running_job.job_id
        assert "stale heartbeat" in inconsistency.reason

    def test_detects_stale_ownership_when_no_heartbeat(self, running_job):
        """Stale ownership when no heartbeat recorded."""
        running_job.last_heartbeat_at = None

        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.STALE_OWNERSHIP
        assert inconsistency.job_id == running_job.job_id
        assert "no heartbeat recorded" in inconsistency.reason

    def test_detects_stale_ownership_when_heartbeat_exceeds_ttl(self, running_job):
        """Stale ownership when heartbeat exceeds TTL."""
        now = datetime.now(timezone.utc)
        running_job.last_heartbeat_at = now - timedelta(seconds=400)

        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
            now=now,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.STALE_OWNERSHIP
        assert inconsistency.job_id == running_job.job_id
        assert "ownership stale" in inconsistency.reason

    def test_returns_none_when_all_consistent(self, running_job):
        """No inconsistency when everything is consistent."""
        now = datetime.now(timezone.utc)
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = now - timedelta(seconds=30)

        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
            heartbeat_threshold_seconds=60,
            now=now,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.NONE
        assert inconsistency.job_id == running_job.job_id

    def test_priority_orphaned_over_crash(self, running_job):
        """Orphaned running has higher priority than crash suspicion."""
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = None

        # Should detect orphaned running (no executor) not crash
        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
            heartbeat_threshold_seconds=60,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.ORPHANED_RUNNING

    def test_priority_crash_over_stale(self, running_job):
        """Crash suspicion has higher priority than stale ownership."""
        now = datetime.now(timezone.utc)
        running_job.active_worker_id = "worker-1"
        running_job.last_heartbeat_at = now - timedelta(seconds=400)

        # Should detect crash (threshold 60s) not stale (TTL 300s)
        inconsistency = detect_rebuild_inconsistency(
            job=running_job,
            runtime_has_active_executor=True,
            lock_ttl_seconds=300,
            heartbeat_threshold_seconds=60,
            now=now,
        )
        assert inconsistency.inconsistency_type == InconsistencyType.CRASH_SUSPICION

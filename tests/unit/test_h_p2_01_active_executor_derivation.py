"""Unit tests for H-P2-01: derive active executor from distributed lock + heartbeat."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import DistributedLockORM, RebuildJobORM, RebuildJobStatus
from src.data.distributed_lock import DistributedLock
from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator
from src.logic.rebuild_failure_detection import InconsistencyType
from src.logic.reconciliation_engine import Severity

UTC = timezone.utc


def _setup_db(tmp_path: Path):
    """Initialize an isolated SQLite DB and return (engine, session_factory)."""
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'hp201.db'}")
    init_db(engine)
    return engine, create_session_factory(engine)


def test_peer_with_live_lock_and_fresh_heartbeat_is_recognized_as_active_executor(tmp_path: Path) -> None:
    """A healthy peer holding the lock with a fresh heartbeat must not be flagged as orphaned."""
    engine, session_factory = _setup_db(tmp_path)
    now = datetime.now(UTC)
    try:
        with session_factory() as session:
            session.add(
                DistributedLockORM(
                    lock_name="graph_rebuild",
                    holder_id="peer-worker-1",
                    created_at=now,
                    updated_at=now,
                    expires_at=now + timedelta(seconds=300),
                )
            )
            session.add(
                RebuildJobORM(
                    job_id="job-live-peer",
                    requested_by="operator",
                    status=RebuildJobStatus.RUNNING.value,
                    active_worker_id="peer-worker-1",
                    last_heartbeat_at=now - timedelta(seconds=5),
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

        observer_lock = DistributedLock(
            coordination_session_factory=session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=300,
            holder_id="observer-instance-2",
        )
        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=observer_lock,
            runtime_has_active_executor=None,
            lock_ttl_seconds=300,
        )
        drift_type, severity, metadata = evaluator.evaluate_drift()

        assert drift_type == InconsistencyType.NONE.value
        assert severity == Severity.NONE
        assert metadata["runtime_has_active_executor"] is True
    finally:
        engine.dispose()


def test_stale_heartbeat_or_expired_lock_is_detected_as_orphaned_running(tmp_path: Path) -> None:
    """When heartbeat is stale or lock is expired/unheld, derived active executor is False."""
    engine, session_factory = _setup_db(tmp_path)
    now = datetime.now(UTC)
    try:
        with session_factory() as session:
            session.add(
                DistributedLockORM(
                    lock_name="graph_rebuild",
                    holder_id="crashed-worker-1",
                    created_at=now - timedelta(seconds=600),
                    updated_at=now - timedelta(seconds=600),
                    expires_at=now - timedelta(seconds=300),
                )
            )
            session.add(
                RebuildJobORM(
                    job_id="job-stale-peer",
                    requested_by="operator",
                    status=RebuildJobStatus.RUNNING.value,
                    active_worker_id="crashed-worker-1",
                    last_heartbeat_at=now - timedelta(seconds=400),
                    created_at=now - timedelta(seconds=600),
                    updated_at=now - timedelta(seconds=400),
                )
            )
            session.commit()

        observer_lock = DistributedLock(
            coordination_session_factory=session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=300,
            holder_id="observer-instance-2",
        )
        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=observer_lock,
            runtime_has_active_executor=None,
            lock_ttl_seconds=300,
        )
        drift_type, severity, metadata = evaluator.evaluate_drift()

        assert drift_type == InconsistencyType.ORPHANED_RUNNING.value
        assert severity == Severity.HIGH
        assert metadata["runtime_has_active_executor"] is False
    finally:
        engine.dispose()


def test_lock_held_by_different_worker_than_job_owner_is_orphaned_running(tmp_path: Path) -> None:
    """If the lock holder does not match job.active_worker_id, active executor derives to False."""
    engine, session_factory = _setup_db(tmp_path)
    now = datetime.now(UTC)
    try:
        with session_factory() as session:
            session.add(
                DistributedLockORM(
                    lock_name="graph_rebuild",
                    holder_id="new-worker-2",
                    created_at=now,
                    updated_at=now,
                    expires_at=now + timedelta(seconds=300),
                )
            )
            session.add(
                RebuildJobORM(
                    job_id="job-old-worker",
                    requested_by="operator",
                    status=RebuildJobStatus.RUNNING.value,
                    active_worker_id="old-worker-1",
                    last_heartbeat_at=now - timedelta(seconds=10),
                    created_at=now - timedelta(seconds=30),
                    updated_at=now - timedelta(seconds=10),
                )
            )
            session.commit()

        new_lock = DistributedLock(
            coordination_session_factory=session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=300,
            holder_id="new-worker-2",
        )
        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=new_lock,
            runtime_has_active_executor=None,
            lock_ttl_seconds=300,
        )
        drift_type, severity, metadata = evaluator.evaluate_drift()

        assert drift_type == InconsistencyType.ORPHANED_RUNNING.value
        assert metadata["runtime_has_active_executor"] is False
    finally:
        engine.dispose()

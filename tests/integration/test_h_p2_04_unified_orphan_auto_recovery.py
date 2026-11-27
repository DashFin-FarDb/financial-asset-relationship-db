"""Integration tests for H-P2-04: unified startup & periodic stale-only orphan auto-recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from api.app_factory import _execute_recovery_gate
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import DistributedLockORM, RebuildJobORM, RebuildJobStatus
from src.logic.reconciliation_loop import _run_sync_reconciliation
from src.logic.recovery_gate import ExecutionBlockedError

UTC = timezone.utc


def _seed_stale_orphan(tmp_path: Path, name: str):
    """Create a SQLite DB containing one stale orphaned RUNNING job and an expired lock."""
    engine = create_engine_from_url(f"sqlite:///{tmp_path / name}")
    init_db(engine)
    session_factory = create_session_factory(engine)
    now = datetime.now(UTC)
    with session_factory() as session:
        session.add(
            RebuildJobORM(
                job_id="stale-orphan-job",
                requested_by="operator",
                status=RebuildJobStatus.RUNNING.value,
                execution_id="exec-stale-1",
                active_worker_id="dead-worker-1",
                last_heartbeat_at=now - timedelta(seconds=600),
                created_at=now - timedelta(seconds=700),
                updated_at=now - timedelta(seconds=600),
            )
        )
        session.commit()
    return engine, session_factory


def test_startup_and_periodic_auto_recover_stale_orphan_under_lock(tmp_path: Path) -> None:
    """Both startup (_execute_recovery_gate) and periodic (_run_sync_reconciliation) reset stale orphans."""
    for label, runner in (
        ("startup", lambda eng: _execute_recovery_gate(eng, eng)),
        ("periodic", lambda eng: _run_sync_reconciliation(eng, eng, cancel_event=None, lock_ttl=60)),
    ):
        engine, session_factory = _seed_stale_orphan(tmp_path, f"hp204_{label}.db")
        try:
            runner(engine)
            with session_factory() as session:
                job = session.get(RebuildJobORM, "stale-orphan-job")
                assert job is not None
                assert job.status == RebuildJobStatus.FAILED.value
                # Distributed lock must be released cleanly after recovery
                lock_row = session.get(DistributedLockORM, "graph_rebuild")
                assert lock_row is None
        finally:
            engine.dispose()


def test_unified_auto_recovery_refuses_to_reset_fresh_heartbeat_job(tmp_path: Path) -> None:
    """Auto-recovery never resets a RUNNING job with a fresh heartbeat (stale-only guard)."""
    engine = create_engine_from_url(f"sqlite:///{tmp_path / 'hp204_fresh.db'}")
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        now = datetime.now(UTC)
        with session_factory() as session:
            session.add(
                RebuildJobORM(
                    job_id="fresh-running-job",
                    requested_by="operator",
                    status=RebuildJobStatus.RUNNING.value,
                    execution_id="exec-fresh-1",
                    active_worker_id="live-worker-1",
                    last_heartbeat_at=now - timedelta(seconds=2),
                    created_at=now - timedelta(seconds=5),
                    updated_at=now - timedelta(seconds=2),
                )
            )
            session.commit()

        with pytest.raises(ExecutionBlockedError):
            _execute_recovery_gate(engine, engine)

        with session_factory() as session:
            job = session.get(RebuildJobORM, "fresh-running-job")
            assert job is not None
            assert job.status == RebuildJobStatus.RUNNING.value
    finally:
        engine.dispose()

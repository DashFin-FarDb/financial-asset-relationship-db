"""Clean restart-recovery path using the real lifecycle and persistence seams."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import api.graph_lifecycle as graph_lifecycle
import api.graph_lifecycle_providers as graph_lifecycle_providers
from src.data.db_models import DistributedLockORM, RebuildJobORM, RebuildJobStatus
from src.data.distributed_lock import DistributedLock, LockState
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate
from tests.integration import restart_recovery_helpers as helpers
from tests.integration.facade import (
    AssetGraphRepository,
    session_scope,
)

pytestmark = pytest.mark.integration


def _create_stale_running_job(session_factory, *, worker_id: str) -> str:
    """Create a running rebuild job with a heartbeat older than the lock TTL."""
    execution_id = f"{worker_id}-exec"
    stale_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=helpers.LOCK_TTL + 30)
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by=worker_id)
        repo.mark_rebuild_job_running(job_id, execution_id)
        repo.update_rebuild_heartbeat(job_id, execution_id, worker_id)
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        job.last_heartbeat_at = stale_heartbeat_at
        session.commit()
    return job_id


def _expire_lock(session_factory) -> None:
    """Force the rebuild lock row to appear expired for the next owner."""
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with session_scope(session_factory) as session:
        lock = session.get(DistributedLockORM, helpers.LOCK_NAME)
        assert lock is not None
        lock.expires_at = expired_at
        lock.updated_at = expired_at
        session.commit()


def test_clean_restart_pipeline_loads_graph_after_gate_and_lock_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Load persisted graph truth after acquiring the rebuild lock."""
    db_url, engine, session_factory = helpers.database(tmp_path)
    lock = None
    try:
        helpers.persist_graph(session_factory, helpers.graph())
        monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", db_url)
        graph_lifecycle.reset_graph()
        graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

        lock = DistributedLock(
            session_factory,
            helpers.LOCK_NAME,
            ttl_seconds=helpers.LOCK_TTL,
        )
        lock.acquire()
        assert lock.check_state() == LockState.VALID

        RecoveryGate(
            session_factory=session_factory,
            lock=lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=helpers.LOCK_TTL,
            enable_automatic_recovery=True,
        ).ensure_safe_to_execute()
        assert lock.check_state() == LockState.VALID

        startup_graph, startup_source = graph_lifecycle.get_graph_with_startup_source()
        assert startup_source is not None
        assert startup_source.source == graph_lifecycle.GraphStartupSource.PERSISTED
        helpers.assert_graph_contents(startup_graph)

        with session_scope(session_factory) as session:
            durable_graph = AssetGraphRepository(session).load_graph()
        helpers.assert_graph_contents(durable_graph)
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:  # noqa: BLE001
                pass
        graph_lifecycle.reset_graph()
        graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
        engine.dispose()


def test_clean_restart_pipeline_reacquires_lock_and_fences_stale_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup reconciliation should fail closed for a stale owner under the production recovery setting."""
    db_url, engine, session_factory = helpers.database(tmp_path)
    owner_a_lock = None
    owner_b_lock = None
    try:
        helpers.persist_graph(session_factory, helpers.graph())
        job_id = _create_stale_running_job(session_factory, worker_id="owner-a")
        owner_a_lock = DistributedLock(
            session_factory,
            helpers.LOCK_NAME,
            ttl_seconds=helpers.LOCK_TTL,
            holder_id="owner-a",
        )
        owner_a_lock.acquire()
        assert owner_a_lock.check_state() == LockState.VALID

        _expire_lock(session_factory)
        monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", db_url)
        graph_lifecycle.reset_graph()
        graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()

        owner_b_lock = DistributedLock(
            session_factory,
            helpers.LOCK_NAME,
            ttl_seconds=helpers.LOCK_TTL,
            holder_id="owner-b",
        )
        owner_b_lock.acquire()
        gate = RecoveryGate(
            session_factory=session_factory,
            lock=owner_b_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=helpers.LOCK_TTL,
            enable_automatic_recovery=False,
        )
        with pytest.raises(ExecutionBlockedError) as exc_info:
            gate.ensure_safe_to_execute()

        assert exc_info.value.action == "wait"
        assert exc_info.value.inconsistency_type == "orphaned_running"
        assert owner_b_lock.check_state() == LockState.VALID
        assert owner_a_lock.check_state() == LockState.UNKNOWN

        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job = repo.get_rebuild_job(job_id)
            assert job is not None
            assert job.status == RebuildJobStatus.RUNNING
            assert job.active_worker_id == "owner-a"

        startup_graph, startup_source = graph_lifecycle.get_graph_with_startup_source()
        assert startup_source is not None
        assert startup_source.source == graph_lifecycle.GraphStartupSource.PERSISTED
        helpers.assert_graph_contents(startup_graph)

        assert gate.lock_was_reacquired is False
    finally:
        if owner_b_lock is not None:
            owner_b_lock.release()
        if owner_a_lock is not None:
            owner_a_lock.release()
        graph_lifecycle.reset_graph()
        graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
        engine.dispose()

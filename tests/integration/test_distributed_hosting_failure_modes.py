"""Distributed hosting failure-mode validation for rebuild coordination."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import api.routers.graph_admin as graph_admin
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.db_models import RebuildJobORM, RebuildJobStatus
from src.data.distributed_lock import DistributedLock
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate
from tests.helpers.graph_scale_factory import build_scale_graph

UTC = timezone.utc

pytestmark = pytest.mark.integration

_LOCK_NAME = "graph_rebuild"
_LOCK_TTL = 300


@pytest.fixture()
def sqlite_session_factory():
    """Return a schema-initialized in-memory SQLite session factory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(engine)
    try:
        yield create_session_factory(engine)
    finally:
        engine.dispose()


def _sqlite_url(tmp_path: Path, name: str) -> str:
    """Return a file-backed SQLite URL."""
    return f"sqlite:///{tmp_path / name}"


def _create_running_job(session_factory, *, worker_id: str, heartbeat_at: datetime) -> str:
    """Create a running rebuild job with an explicit owner heartbeat."""
    execution_id = f"exec-{worker_id}"
    with session_scope(session_factory) as session:
        repo = AssetGraphRepository(session)
        job_id = repo.create_rebuild_job(requested_by=worker_id)
        repo.mark_rebuild_job_running(job_id, execution_id)
        repo.update_rebuild_heartbeat(job_id, execution_id, worker_id)
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        job.last_heartbeat_at = heartbeat_at
        session.commit()
    return job_id


def _load_job(session_factory, job_id: str) -> RebuildJobORM:
    """Load a rebuild job and assert it exists."""
    with session_scope(session_factory) as session:
        job = session.get(RebuildJobORM, job_id)
        assert job is not None
        session.expunge(job)
        return job


def _assert_fresh_foreign_owner_is_not_reset(
    session_factory,
    *,
    enable_automatic_recovery: bool,
) -> ExecutionBlockedError:
    """Assert a live foreign rebuild owner blocks recovery and remains RUNNING."""
    job_id = _create_running_job(
        session_factory,
        worker_id="worker-a",
        heartbeat_at=datetime.now(UTC),
    )
    lock = DistributedLock(session_factory, _LOCK_NAME, ttl_seconds=_LOCK_TTL)
    assert lock.acquire()

    try:
        gate = RecoveryGate(
            session_factory=session_factory,
            lock=lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=_LOCK_TTL,
            enable_automatic_recovery=enable_automatic_recovery,
        )
        with pytest.raises(ExecutionBlockedError) as exc_info:
            gate.ensure_safe_to_execute()
    finally:
        lock.release()

    job = _load_job(session_factory, job_id)
    assert job.status == RebuildJobStatus.RUNNING
    assert job.active_worker_id == "worker-a"
    return exc_info.value


def test_recovery_does_not_reset_running_job_with_fresh_foreign_heartbeat(sqlite_session_factory) -> None:
    """A freshly heartbeating foreign rebuild owner must not be reset by this instance."""
    blocked = _assert_fresh_foreign_owner_is_not_reset(
        sqlite_session_factory,
        enable_automatic_recovery=True,
    )

    assert blocked.action in {"alert_only", "unsafe"}


def test_recovery_resets_stale_running_job_after_lock_reacquisition(sqlite_session_factory) -> None:
    """A stale owner may be reset only after RecoveryGate obtains valid lock ownership."""
    stale_at = datetime.now(UTC) - timedelta(seconds=_LOCK_TTL + 30)
    job_id = _create_running_job(sqlite_session_factory, worker_id="dead-worker", heartbeat_at=stale_at)
    lock = DistributedLock(sqlite_session_factory, _LOCK_NAME, ttl_seconds=_LOCK_TTL)

    gate = RecoveryGate(
        session_factory=sqlite_session_factory,
        lock=lock,
        runtime_has_active_executor=False,
        lock_ttl_seconds=_LOCK_TTL,
        enable_automatic_recovery=True,
    )
    try:
        gate.ensure_safe_to_execute()

        job = _load_job(sqlite_session_factory, job_id)
        assert job.status == RebuildJobStatus.FAILED
        assert job.sanitized_failure_category == "recovery_reset"
        assert gate.lock_was_reacquired is True
        assert lock.check_state().value == "valid"
    finally:
        lock.release()


def test_restart_during_live_rebuild_does_not_steal_fresh_owner(sqlite_session_factory) -> None:
    """A restarted instance must block instead of stealing a live foreign rebuild owner."""
    _assert_fresh_foreign_owner_is_not_reset(
        sqlite_session_factory,
        enable_automatic_recovery=False,
    )


def test_rebuild_crash_before_persist_marks_failed_without_partial_graph_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rebuild crash before persistence should fail the job without writing partial graph truth."""
    database_url = _sqlite_url(tmp_path, "crash-before-persist.db")
    engine = create_engine_from_url(database_url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(requested_by="crash-test")
            repo.mark_rebuild_job_running(job_id, "crash-exec")
            session.commit()

        def fail_build(*_args, **_kwargs):
            """Simulate a failure during graph building."""
            raise RuntimeError("synthetic crash before persist")

        monkeypatch.setattr(graph_admin, "build_rebuild_graph", fail_build)

        with pytest.raises(RuntimeError, match="synthetic crash before persist"):
            graph_admin._run_rebuild_pipeline(  # pylint: disable=protected-access
                session_factory,
                graph_admin.get_graph_lifecycle_settings(),
                database_url,
                job_id,
                "crash-exec",
                time.perf_counter(),
                threading.Event(),
                threading.Event(),
            )

        with session_factory() as session:
            repo = AssetGraphRepository(session)
            job = repo.get_rebuild_job(job_id)
            persisted = repo.load_graph()
            assert job is not None
            assert job.status == RebuildJobStatus.FAILED
            assert len(persisted.assets) == 0
            assert sum(len(items) for items in persisted.relationships.values()) == 0
    finally:
        engine.dispose()


def test_rebuild_failure_after_persist_does_not_corrupt_durable_graph_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A post-persist metadata failure should leave durable graph truth loadable and consistent."""
    database_url = _sqlite_url(tmp_path, "crash-after-persist.db")
    engine = create_engine_from_url(database_url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        known_good = build_scale_graph(asset_count=10, relationship_count=20, prefix="GOOD")
        with session_factory() as session:
            repo = AssetGraphRepository(session)
            repo.save_graph(known_good)
            job_id = repo.create_rebuild_job(requested_by="post-persist-test")
            repo.mark_rebuild_job_running(job_id, "post-persist-exec")
            session.commit()

        replacement = build_scale_graph(asset_count=12, relationship_count=24, prefix="NEW")
        monkeypatch.setattr(
            graph_admin,
            "build_rebuild_graph",
            lambda *_args, **_kwargs: (replacement, "sample"),
        )

        def fail_success(*_args, **_kwargs):
            """Simulate a failure while marking the job as succeeded."""
            raise RuntimeError("synthetic success metadata failure")

        monkeypatch.setattr(graph_admin, "_mark_job_succeeded_safe", fail_success)  # pylint: disable=protected-access

        with pytest.raises(graph_admin._RebuildExecutionError):  # pylint: disable=protected-access
            graph_admin._run_rebuild_pipeline(  # pylint: disable=protected-access
                session_factory,
                graph_admin.get_graph_lifecycle_settings(),
                database_url,
                job_id,
                "post-persist-exec",
                time.perf_counter(),
                threading.Event(),
                threading.Event(),
            )

        with session_factory() as session:
            repo = AssetGraphRepository(session)
            job = repo.get_rebuild_job(job_id)
            loaded = repo.load_graph()
            assert job is not None
            assert job.status == RebuildJobStatus.FAILED
            assert len(loaded.assets) == 10
            assert sum(len(items) for items in loaded.relationships.values()) == 20
    finally:
        engine.dispose()


def test_lock_lost_during_rebuild_aborts_before_success_marking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lost lock after graph construction should fail closed before persistence or success marking."""
    database_url = _sqlite_url(tmp_path, "lock-lost.db")
    engine = create_engine_from_url(database_url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(requested_by="lock-lost-test")
            repo.mark_rebuild_job_running(job_id, "lock-lost-exec")
            session.commit()

        lock_lost = threading.Event()
        graph_built = False
        save_called = False
        success_called = False
        built_graph = build_scale_graph(asset_count=5, relationship_count=10, prefix="LOST")

        def build_then_lose_lock(*_args, **_kwargs):
            """Build the graph and immediately simulate losing the distributed lock."""
            nonlocal graph_built
            graph_built = True
            lock_lost.set()
            return built_graph, "sample"

        def track_save(*_args, **_kwargs):
            """Track if the graph save function was called."""
            nonlocal save_called
            save_called = True

        def track_success(*_args, **_kwargs):
            """Track if the job success function was called."""
            nonlocal success_called
            success_called = True

        monkeypatch.setattr(graph_admin, "build_rebuild_graph", build_then_lose_lock)
        monkeypatch.setattr(graph_admin, "save_graph_to_persistence", track_save)
        monkeypatch.setattr(graph_admin, "_mark_job_succeeded_safe", track_success)  # pylint: disable=protected-access

        with pytest.raises(graph_admin._RebuildExecutionError) as exc_info:  # pylint: disable=protected-access
            graph_admin._run_rebuild_pipeline(  # pylint: disable=protected-access
                session_factory,
                graph_admin.get_graph_lifecycle_settings(),
                database_url,
                job_id,
                "lock-lost-exec",
                time.perf_counter(),
                lock_lost,
                threading.Event(),
            )

        assert isinstance(exc_info.value.cause, graph_admin._DistributedLockLostError)  # pylint: disable=protected-access
        assert "pre-persistence" in str(exc_info.value.cause)
        assert graph_built is True
        with session_factory() as session:
            job = AssetGraphRepository(session).get_rebuild_job(job_id)
            assert job is not None
            assert job.status == RebuildJobStatus.FAILED
        assert save_called is False
        assert success_called is False
    finally:
        engine.dispose()

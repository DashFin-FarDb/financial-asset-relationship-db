"""Integration tests for lock refresh and heartbeat keeper flow.

This module tests the end-to-end lock refresh implementation including:
- Heartbeat keeper background thread operation during rebuild
- Lock refresh at periodic intervals
- Lock-lost detection via threading.Event
- Pre-commit safety checks at persistence boundaries
- Thread cleanup on rebuild completion
"""

# pylint: disable=redefined-outer-name

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest  # pylint: disable=import-error

from api.routers import graph_admin
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.distributed_lock import DistributedLock
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.integration

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _lock_refresh_db_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[sessionmaker]:
    """Provide a clean, initialized database and session factory for lock refresh tests."""
    db_file = tmp_path / "test_lock_refresh.db"
    monkeypatch.setenv("ASSET_GRAPH_DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()

    settings = get_settings()
    engine = create_engine_from_url(settings.asset_graph_database_url)
    try:
        init_db(engine)
        session_factory = create_session_factory(engine)
        yield session_factory
    finally:
        engine.dispose()
        get_settings.cache_clear()


def _create_test_graph() -> AssetRelationshipGraph:
    """Create a minimal test graph for persistence operations."""
    graph = AssetRelationshipGraph()
    return graph


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


def test_heartbeat_keeper_refreshes_lock_during_rebuild(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Heartbeat keeper should refresh the lock at regular intervals during rebuild.

    This test verifies that:
    1. Lock refresh occurs at ~TTL/3 intervals (e.g., every 3s for TTL=10s)
    2. Rebuild completes successfully when lock is continuously refreshed
    3. Lock refresh events are logged at DEBUG level
    """
    with _lock_refresh_db_context(tmp_path, monkeypatch) as session_factory:
        # Use short TTL for faster test execution
        lock_ttl = 10
        expected_refresh_interval = max(1, lock_ttl // 3)  # 3 seconds

        # Create and acquire lock
        dist_lock = DistributedLock(
            session_factory,
            "test_lock",
            ttl_seconds=lock_ttl,
        )
        assert dist_lock.acquire(), "Failed to acquire initial lock"

        # Set up heartbeat keeper coordination
        stop_event = threading.Event()
        lock_lost_event = threading.Event()
        job_id = "test-job-refresh"

        # Create rebuild job
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id)

        # Track refresh events
        refresh_count = 0
        original_refresh = dist_lock.refresh

        def counting_refresh() -> bool:
            nonlocal refresh_count
            result = original_refresh()
            if result:
                refresh_count += 1
            return result

        dist_lock.refresh = counting_refresh

        # Start heartbeat keeper thread
        with caplog.at_level(logging.DEBUG):
            heartbeat_thread = threading.Thread(
                target=graph_admin._heartbeat_keeper,  # pylint: disable=protected-access
                kwargs={
                    "session_factory": session_factory,
                    "dist_lock": dist_lock,
                    "job_id": job_id,
                    "worker_id": dist_lock.holder_id,
                    "stop_event": stop_event,
                    "lock_lost_event": lock_lost_event,
                    "interval_seconds": expected_refresh_interval,
                },
                daemon=True,
                name="test-heartbeat-keeper",
            )
            heartbeat_thread.start()

            try:
                # Run for slightly longer than 2 refresh intervals to see at least 2 refreshes
                # First refresh happens immediately after the first interval, second after the next
                test_duration = expected_refresh_interval * 2.5
Use a threading.Event or a small polling loop instead of a fixed sleep:

refreshed = threading.Event()

def counting_refresh() -> bool:
    nonlocal refresh_count
    result = original_refresh()
    if result:
        refresh_count += 1
        if refresh_count >= 2:
            refreshed.set()
    return result

dist_lock.refresh = counting_refresh
# ... start thread ...
assert refreshed.wait(timeout=30), f'Expected 2 refreshes within 30s, got {refresh_count}'

                # Stop the heartbeat keeper
                stop_event.set()
                heartbeat_thread.join(timeout=2.0)

                # Verify lock was not lost
                assert not lock_lost_event.is_set(), "Lock should not be lost during normal operation"

                # Verify refresh occurred at least twice (once per interval)
                # We expect at least 2 refreshes over 2.5 intervals
                assert refresh_count >= 2, f"Expected at least 2 refreshes, got {refresh_count}"

                # Verify refresh logs were emitted
                refresh_logs = [
                    record for record in caplog.records
                    if "Refreshed distributed lock" in record.message
                ]
                assert len(refresh_logs) >= 2, "Expected refresh DEBUG logs"

            finally:
                # Clean up
                stop_event.set()
                if heartbeat_thread.is_alive():
                    heartbeat_thread.join(timeout=2.0)
                dist_lock.release()


def test_lock_loss_mid_rebuild_aborts_with_503(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lock loss mid-rebuild should set lock_lost Event and log error.

    This test simulates a scenario where the lock is taken by another holder
    mid-rebuild, causing the heartbeat keeper to detect lock loss.

    Verifies:
    1. lock_lost Event is set when refresh fails
    2. ERROR log is emitted
    3. Heartbeat keeper thread terminates
    """
    with _lock_refresh_db_context(tmp_path, monkeypatch) as session_factory:
        lock_ttl = 10
        interval_seconds = max(1, lock_ttl // 3)

        # Create and acquire lock
        dist_lock = DistributedLock(
            session_factory,
            "test_lock_loss",
            ttl_seconds=lock_ttl,
        )
        assert dist_lock.acquire(), "Failed to acquire initial lock"

        # Create rebuild job
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id)

        stop_event = threading.Event()
        lock_lost_event = threading.Event()

        # Start heartbeat keeper
        with caplog.at_level(logging.ERROR):
            heartbeat_thread = threading.Thread(
                target=graph_admin._heartbeat_keeper,  # pylint: disable=protected-access
                kwargs={
                    "session_factory": session_factory,
                    "dist_lock": dist_lock,
                    "job_id": job_id,
                    "worker_id": dist_lock.holder_id,
                    "stop_event": stop_event,
                    "lock_lost_event": lock_lost_event,
                    "interval_seconds": interval_seconds,
                },
                daemon=True,
                name="test-heartbeat-loss",
            )
            heartbeat_thread.start()

            try:
                # Wait for first refresh cycle
                time.sleep(interval_seconds + 0.5)

                # Simulate lock loss by manually releasing and acquiring with different holder
                dist_lock.release()

                # Another holder takes the lock
                other_lock = DistributedLock(
                    session_factory,
                    "test_lock_loss",
                    holder_id="other-holder",
                    ttl_seconds=lock_ttl,
                )
                assert other_lock.acquire(), "Other holder should acquire lock"

                # Wait for next refresh cycle to detect loss
                time.sleep(interval_seconds + 1.0)

                # Verify lock_lost Event was set
                assert lock_lost_event.is_set(), "lock_lost Event should be set when refresh fails"

                # Verify heartbeat thread terminated
                heartbeat_thread.join(timeout=2.0)
                assert not heartbeat_thread.is_alive(), "Heartbeat thread should terminate after lock loss"

                # Verify ERROR log was emitted
                error_logs = [
                    record for record in caplog.records
                    if record.levelname == "ERROR" and "lost distributed lock" in record.message.lower()
                ]
                assert len(error_logs) >= 1, "Expected ERROR log for lock loss"

            finally:
                stop_event.set()
                if heartbeat_thread.is_alive():
                    heartbeat_thread.join(timeout=2.0)
                other_lock.release()


def test_lock_loss_before_commit_prevents_partial_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lock loss before commit should raise error and prevent persistence.

    This test verifies the pre-commit safety check that prevents committing graph state
    if the lock was lost between staging changes and commit.

    Verifies:
    1. Pre-commit callback detects lock_lost Event
    2. Exception is raised (wrapped as GraphPersistenceSaveError)
    3. Graph state is not persisted (rollback occurs)
    4. Pre-commit check failure is logged
    """
    with _lock_refresh_db_context(tmp_path, monkeypatch) as session_factory:
        # Simulate lock_lost Event being set before commit
        lock_lost = threading.Event()

        # Create pre-commit check that verifies lock status
        def _ensure_lock_not_lost_before_commit() -> None:
            if lock_lost.is_set():
                raise graph_admin._DistributedLockLostError(  # pylint: disable=protected-access
                    "Lost distributed lock at stage=graph-commit"
                )

        # Load initial graph state snapshot
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            initial_graph = repo.load_graph()
            initial_asset_count = len(initial_graph.assets)

        # Create a new graph to persist
        test_graph = _create_test_graph()

        # Get persistence URL
        settings = get_settings()
        resolved_url = settings.asset_graph_database_url

        # Simulate lock loss during persistence preparation
        lock_lost.set()

        # Attempt to save graph with pre-commit check
        from api.graph_lifecycle_providers import (  # pylint: disable=import-outside-toplevel
            GraphPersistenceSaveError,
            save_graph_to_persistence,
        )

        with caplog.at_level(logging.ERROR):
            with pytest.raises(GraphPersistenceSaveError):
                save_graph_to_persistence(
                    resolved_url,
                    test_graph,
                    pre_commit_check=_ensure_lock_not_lost_before_commit,
                )

        # Verify pre-commit check failure was logged
        error_logs = [
            record for record in caplog.records
            if "Pre-commit persistence safety check failed" in record.message
        ]
        assert len(error_logs) >= 1, "Expected ERROR log for pre-commit check failure"

        # Verify the underlying error type was _DistributedLockLostError
        lock_lost_logs = [
            record for record in caplog.records
            if "_DistributedLockLostError" in record.message
        ]
        assert len(lock_lost_logs) >= 1, "Expected log mentioning _DistributedLockLostError"

        # Verify graph state was not persisted (rollback occurred)
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            current_graph = repo.load_graph()
            current_asset_count = len(current_graph.assets)

        assert current_asset_count == initial_asset_count, (
            "Graph state should be unchanged after lock loss during commit"
        )


def test_heartbeat_thread_stops_cleanly_on_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Heartbeat thread should terminate cleanly within timeout after rebuild completion.

    This test verifies the _orchestrate_heartbeat context manager properly:
    1. Starts the heartbeat thread before rebuild
    2. Yields lock_lost Event to pipeline
    3. Stops the thread cleanly on exit with 2s timeout
    """
    with _lock_refresh_db_context(tmp_path, monkeypatch) as session_factory:
        lock_ttl = 10

        # Create and acquire lock
        dist_lock = DistributedLock(
            session_factory,
            "test_lock_cleanup",
            ttl_seconds=lock_ttl,
        )
        assert dist_lock.acquire(), "Failed to acquire initial lock"

        # Create rebuild job
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id)

        # Use _orchestrate_heartbeat context manager
        with graph_admin._orchestrate_heartbeat(  # pylint: disable=protected-access
            session_factory,
            dist_lock,
            job_id,
            lock_ttl,
        ) as lock_lost:
            # Verify lock_lost Event is provided
            assert isinstance(lock_lost, threading.Event)
            assert not lock_lost.is_set(), "lock_lost should not be set initially"

            # Find the heartbeat thread
            heartbeat_thread = None
            for thread in threading.enumerate():
                if thread.name.startswith(f"heartbeat-keeper-{job_id}"):
                    heartbeat_thread = thread
                    break

            assert heartbeat_thread is not None, "Heartbeat thread should be running"
            assert heartbeat_thread.is_alive(), "Heartbeat thread should be alive during context"

            # Simulate some work
            time.sleep(1.0)

        # After context exit, thread should be stopped
        # The context manager joins with 2s timeout
        time.sleep(0.5)  # Small buffer to ensure join completes

        if heartbeat_thread is not None:
            assert not heartbeat_thread.is_alive(), (
                "Heartbeat thread should terminate within 2s after context exit"
            )

        # Clean up
        dist_lock.release()


def test_heartbeat_keeper_updates_database_heartbeat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Heartbeat keeper should update database heartbeat timestamp periodically.

    This test verifies that:
    1. update_rebuild_heartbeat is called during each refresh cycle
    2. last_heartbeat_at timestamp is updated in the database
    """
    with _lock_refresh_db_context(tmp_path, monkeypatch) as session_factory:
        lock_ttl = 10
        interval_seconds = max(1, lock_ttl // 3)

        # Create and acquire lock
        dist_lock = DistributedLock(
            session_factory,
            "test_lock_heartbeat",
            ttl_seconds=lock_ttl,
        )
        assert dist_lock.acquire(), "Failed to acquire initial lock"

        # Create rebuild job
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id)

            # Get initial heartbeat timestamp (should be None initially)
            job = repo.get_rebuild_job(job_id)
            initial_heartbeat = job.last_heartbeat_at if job else None

        stop_event = threading.Event()
        lock_lost_event = threading.Event()

        # Start heartbeat keeper
        heartbeat_thread = threading.Thread(
            target=graph_admin._heartbeat_keeper,  # pylint: disable=protected-access
            kwargs={
                "session_factory": session_factory,
                "dist_lock": dist_lock,
                "job_id": job_id,
                "worker_id": dist_lock.holder_id,
                "stop_event": stop_event,
                "lock_lost_event": lock_lost_event,
                "interval_seconds": interval_seconds,
            },
            daemon=True,
            name="test-heartbeat-db",
        )
        heartbeat_thread.start()

        try:
            # Wait for at least one refresh cycle
            time.sleep(interval_seconds + 0.5)

            # Check that heartbeat was updated
            with session_scope(session_factory) as session:
                repo = AssetGraphRepository(session)
                job = repo.get_rebuild_job(job_id)
                updated_heartbeat = job.last_heartbeat_at if job else None

            assert updated_heartbeat is not None, "Heartbeat timestamp should be set"
            if initial_heartbeat is not None:
                assert updated_heartbeat > initial_heartbeat, (
                    "Heartbeat timestamp should be updated"
                )

            # Wait for another cycle
            time.sleep(interval_seconds)

            # Verify heartbeat continues to update
            with session_scope(session_factory) as session:
                repo = AssetGraphRepository(session)
                job = repo.get_rebuild_job(job_id)
                second_update = job.last_heartbeat_at if job else None

            assert second_update >= updated_heartbeat, (
                "Heartbeat should continue updating"
            )

        finally:
            stop_event.set()
            if heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=2.0)
            dist_lock.release()

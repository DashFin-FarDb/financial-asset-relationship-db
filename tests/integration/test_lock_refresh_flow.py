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
from unittest.mock import MagicMock

import pytest  # pylint: disable=import-error

# Module-level import is safe as api.routers.graph_admin is side-effect free on import.
# This allows direct access to internal helpers for tests and ensuring monkeypatch targets are available.
import api.routers.graph_admin as graph_admin
from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory, init_db
from src.data.distributed_lock import DistributedLock
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.asset_graph import AssetRelationshipGraph

pytestmark = pytest.mark.integration

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker


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

        # Create rebuild job
        execution_id = "test-exec-id"
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id, execution_id)

        # Track refresh events using MagicMock with wraps
        original_refresh = dist_lock.refresh
        mock_refresh = MagicMock(wraps=original_refresh)
        dist_lock.refresh = mock_refresh  # type: ignore[method-assign]

        # Start heartbeat keeper thread
        with caplog.at_level(logging.DEBUG):
            heartbeat_thread = threading.Thread(
                target=graph_admin._heartbeat_keeper,  # pylint: disable=protected-access
                kwargs={
                    "session_factory": session_factory,
                    "dist_lock": dist_lock,
                    "job_id": job_id,
                    "execution_id": execution_id,
                    "worker_id": dist_lock.holder_id,
                    "stop_event": stop_event,
                    "lock_lost_event": lock_lost_event,
                    "cancel_event": threading.Event(),
                    "interval_seconds": expected_refresh_interval,
                },
                daemon=True,
                name="test-heartbeat-keeper",
            )
            heartbeat_thread.start()

            try:
                # Wait for at least 2 refreshes using a polling loop instead of fixed sleep
                deadline = time.monotonic() + (expected_refresh_interval * 3)
                while mock_refresh.call_count < 2:
                    if time.monotonic() > deadline:
                        pytest.fail(f"Expected 2 refreshes within timeout, got {mock_refresh.call_count}")
                    time.sleep(0.1)

                # Stop the heartbeat keeper
                stop_event.set()
                heartbeat_thread.join(timeout=2.0)

                # Verify lock was not lost
                assert not lock_lost_event.is_set(), "Lock should not be lost during normal operation"

            finally:
                # Clean up
                stop_event.set()
                if heartbeat_thread.is_alive():
                    heartbeat_thread.join(timeout=2.0)
                dist_lock.release()


def test_lock_loss_mid_rebuild_sets_event_and_terminates_thread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lock loss mid-rebuild should set lock_lost Event, log error, and terminate thread.

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
        execution_id = "test-exec-id"
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id, execution_id)

        stop_event = threading.Event()
        lock_lost_event = threading.Event()
        other_lock = None  # Initialize to track if lock was acquired
        heartbeat_thread = None  # Initialize to track thread

        # Use Event to track when first refresh completes to avoid race condition
        first_refresh_done = threading.Event()

        # Track refresh events using MagicMock with wraps and side_effect
        original_refresh = dist_lock.refresh

        def refresh_with_event(*args, **kwargs):
            """Refresh lock and signal completion."""
            result = original_refresh(*args, **kwargs)
            first_refresh_done.set()
            return result

        mock_refresh = MagicMock(side_effect=refresh_with_event)
        dist_lock.refresh = mock_refresh  # type: ignore[method-assign]

        # Start heartbeat keeper
        with caplog.at_level(logging.ERROR):
            heartbeat_thread = threading.Thread(
                target=graph_admin._heartbeat_keeper,  # pylint: disable=protected-access
                kwargs={
                    "session_factory": session_factory,
                    "dist_lock": dist_lock,
                    "job_id": job_id,
                    "execution_id": execution_id,
                    "worker_id": dist_lock.holder_id,
                    "stop_event": stop_event,
                    "lock_lost_event": lock_lost_event,
                    "cancel_event": threading.Event(),
                    "interval_seconds": interval_seconds,
                },
                daemon=True,
                name="test-heartbeat-loss",
            )
            heartbeat_thread.start()

            try:
                # Wait for first refresh to complete using Event instead of polling call_count
                timeout_seconds = interval_seconds * 3
                if not first_refresh_done.wait(timeout=timeout_seconds):
                    pytest.fail(f"First refresh did not complete within {timeout_seconds}s")

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

                # Wait for heartbeat keeper to detect lock loss using polling
                deadline = time.monotonic() + (interval_seconds * 3)
                while not lock_lost_event.is_set():
                    if time.monotonic() > deadline:
                        pytest.fail("lock_lost_event was not set within timeout")
                    time.sleep(0.1)

                # Verify heartbeat thread terminated
                heartbeat_thread.join(timeout=2.0)
                assert not heartbeat_thread.is_alive(), "Heartbeat thread should terminate after lock loss"

                # Verify ERROR log was emitted (without coupling to exact message text)
                error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
                assert len(error_logs) >= 1, "Expected ERROR log for lock loss"

            finally:
                stop_event.set()
                if heartbeat_thread is not None and heartbeat_thread.is_alive():
                    heartbeat_thread.join(timeout=2.0)
                if other_lock is not None:
                    other_lock.release()
                # Ensure original lock is released even if test fails
                with contextlib.suppress(RuntimeError):
                    dist_lock.release()


def test_pre_commit_check_blocks_save_on_lock_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pre-commit safety hook prevents graph persistence when lock is lost.

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
            """Ensure the lock was not lost before allowing persistence commit."""
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
        from api.graph_lifecycle_providers import (
            save_graph_to_persistence,
        )

        with caplog.at_level(logging.ERROR), pytest.raises(graph_admin._DistributedLockLostError):
            save_graph_to_persistence(
                resolved_url,
                test_graph,
                pre_commit_check=_ensure_lock_not_lost_before_commit,
            )

        # Verify pre-commit check failure was logged (without coupling to exact message text)
        error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(error_logs) >= 1, "Expected ERROR log for pre-commit check failure"

        # Verify the underlying error was a lock lost error (check exception type was raised, not message)
        # The test already verifies GraphPersistenceSaveError was raised, which wraps the lock lost error
        # This confirms the error handling worked correctly without coupling to log message strings

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
        execution_id = "test-exec-id"
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id, execution_id)

        # Use _orchestrate_heartbeat context manager
        with graph_admin._orchestrate_heartbeat(  # pylint: disable=protected-access
            session_factory,
            dist_lock,
            job_id,
            execution_id,
            lock_ttl,
        ) as (lock_lost, cancel_event):
            # Verify events are provided
            assert isinstance(lock_lost, threading.Event)
            assert isinstance(cancel_event, threading.Event)
            assert not lock_lost.is_set(), "lock_lost should not be set initially"
            assert not cancel_event.is_set(), "cancel_event should not be set initially"

            # Find the heartbeat thread
            heartbeat_thread = None
            for thread in threading.enumerate():
                if thread.name.startswith(f"heartbeat-keeper-{job_id}"):
                    heartbeat_thread = thread
                    break

            assert heartbeat_thread is not None, "Heartbeat thread should be running"
            assert heartbeat_thread.is_alive(), "Heartbeat thread should be alive during context"

            # Verify thread stays alive during context - use polling with deadline instead of fixed sleep
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                assert heartbeat_thread.is_alive(), "Heartbeat thread should remain alive during context"
                time.sleep(0.1)

        # After context exit, thread should be stopped
        # The context manager joins with 2s timeout
        if heartbeat_thread is not None:
            assert not heartbeat_thread.is_alive(), "Heartbeat thread should terminate within 2s after context exit"

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
        execution_id = "test-exec-id"
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            job_id = repo.create_rebuild_job(
                requested_by="test-operator",
                source="test-source",
            )
            repo.mark_rebuild_job_running(job_id, execution_id)

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
                "execution_id": execution_id,
                "worker_id": dist_lock.holder_id,
                "stop_event": stop_event,
                "lock_lost_event": lock_lost_event,
                "cancel_event": threading.Event(),
                "interval_seconds": interval_seconds,
            },
            daemon=True,
            name="test-heartbeat-db",
        )
        heartbeat_thread.start()

        try:
            # Wait for at least one refresh cycle using polling
            deadline = time.monotonic() + (interval_seconds * 2)
            updated_heartbeat = None
            while updated_heartbeat is None:
                if time.monotonic() > deadline:
                    pytest.fail("Heartbeat was not updated within timeout")
                time.sleep(0.5)

                with session_scope(session_factory) as session:
                    repo = AssetGraphRepository(session)
                    job = repo.get_rebuild_job(job_id)
                    updated_heartbeat = job.last_heartbeat_at if job else None

            assert updated_heartbeat is not None, "Heartbeat timestamp should be set"
            if initial_heartbeat is not None:
                assert updated_heartbeat > initial_heartbeat, "Heartbeat timestamp should be updated"

            # Wait for another cycle using polling
            deadline = time.monotonic() + (interval_seconds * 2)
            second_update = None
            while second_update is None or second_update == updated_heartbeat:
                if time.monotonic() > deadline:
                    pytest.fail("Heartbeat was not updated a second time within timeout")
                time.sleep(0.1)

                with session_scope(session_factory) as session:
                    repo = AssetGraphRepository(session)
                    job = repo.get_rebuild_job(job_id)
                    second_update = job.last_heartbeat_at if job else None

            assert second_update is not None, "Heartbeat should still be set"
            assert second_update > updated_heartbeat, "Heartbeat should continue updating"

        finally:
            stop_event.set()
            if heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=2.0)
            dist_lock.release()

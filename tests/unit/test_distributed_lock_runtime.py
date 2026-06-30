"""Unit tests for DistributedLock runtime behavior."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.distributed_lock import DistributedLock, LockAcquisitionTimeout, LockLease, LockLifecycleState


@contextmanager
def _mock_session_scope(factory):
    """Mock session_scope that yields a MagicMock session with Session spec."""
    yield MagicMock(spec=Session)


@pytest.mark.unit
def test_acquire_raises_on_persistence_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Database exceptions during acquisition should not be reported as contention."""

    class _FailingScope:
        def __enter__(self):
            raise RuntimeError("db unavailable")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.data.distributed_lock.session_scope", lambda _factory: _FailingScope())
    lock = DistributedLock(lambda: None, "graph_rebuild")  # type: ignore[return-value]

    with pytest.raises(RuntimeError, match="db unavailable"):
        lock.acquire()


@pytest.mark.unit
def test_check_state_reraises_unexpected_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """check_state should re-raise unexpected runtime errors as programming bugs."""

    class _FailingScope:
        def __enter__(self):
            raise RuntimeError("db unavailable")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.data.distributed_lock.session_scope", lambda _factory: _FailingScope())
    lock = DistributedLock(lambda: None, "graph_rebuild")  # type: ignore[return-value]

    with pytest.raises(RuntimeError, match="db unavailable"):
        lock.check_state()


@pytest.fixture
def mock_lock_env(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, DistributedLock]:
    """Create a mocked lock environment.

    Create and return a mocked CoordinationLockRepository and a DistributedLock
    with session scope and sleep patched for tests.

    Parameters:
        monkeypatch (pytest.MonkeyPatch): Pytest fixture used to apply required monkeypatches.

    Returns:
        tuple[MagicMock, DistributedLock]: A tuple where the first element is a
            MagicMock acting as the CoordinationLockRepository, and the second
            element is a DistributedLock instance configured to use the mocked
            session scope and no-op sleep.
    """
    mock_repo = MagicMock()
    monkeypatch.setattr("src.data.distributed_lock.session_scope", _mock_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.CoordinationLockRepository", lambda session: mock_repo)
    monkeypatch.setattr("src.data.distributed_lock.sleep", lambda seconds: None)
    lock = DistributedLock(lambda: None, "test_lock")  # type: ignore[return-value]
    return mock_repo, lock


@pytest.mark.unit
def test_refresh_success_after_transient_failures(mock_lock_env: tuple[MagicMock, DistributedLock]) -> None:
    """Verify refresh succeeds after recovering from transient failures."""
    mock_repo, lock = mock_lock_env
    # Attempt 1 -> SQLAlchemyError
    # Attempt 2 -> SQLAlchemyError
    # Attempt 3 -> Success
    mock_repo.refresh_lock.side_effect = [
        SQLAlchemyError("transient 1"),
        SQLAlchemyError("transient 2"),
        SimpleNamespace(success=True, fencing_token=123),
    ]

    res = lock.refresh(max_retries=2)

    assert isinstance(res, LockLease)
    assert res.state == LockLifecycleState.REFRESHED
    assert res.fencing_token == 123
    assert mock_repo.refresh_lock.call_count == 3


@pytest.mark.unit
def test_refresh_retry_budget_exhausted(mock_lock_env: tuple[MagicMock, DistributedLock]) -> None:
    """Verify refresh fails when retry budget for transient errors is exhausted."""
    mock_repo, lock = mock_lock_env
    # Always raise SQLAlchemyError
    mock_repo.refresh_lock.side_effect = SQLAlchemyError("persistent failure")

    res = lock.refresh(max_retries=2)

    assert res is False
    assert mock_repo.refresh_lock.call_count == 3


@pytest.mark.unit
def test_refresh_no_retry_on_contention(mock_lock_env: tuple[MagicMock, DistributedLock]) -> None:
    """Verify refresh does not retry when the lock is held by another owner."""
    mock_repo, lock = mock_lock_env
    # Return success=False (contention), not an exception
    mock_repo.refresh_lock.return_value = SimpleNamespace(success=False)
    res = lock.refresh(max_retries=2)

    assert res is False
    assert mock_repo.refresh_lock.call_count == 1


@pytest.mark.unit
def test_refresh_no_retry_on_unexpected_exception(mock_lock_env: tuple[MagicMock, DistributedLock]) -> None:
    """Verify refresh fails immediately on unexpected non-transient exceptions."""
    mock_repo, lock = mock_lock_env
    # Raise an exception not in (SQLAlchemyError, OSError)
    mock_repo.refresh_lock.side_effect = ValueError("unexpected bug")

    # In the current implementation, unexpected exceptions are caught and return False
    res = lock.refresh(max_retries=2)

    assert res is False
    assert mock_repo.refresh_lock.call_count == 1


@pytest.mark.unit
def test_acquire_timeout_after_30s(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LockAcquisitionTimeout is raised after 30s of contention."""
    mock_repo = MagicMock()
    monkeypatch.setattr("src.data.distributed_lock.session_scope", _mock_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.CoordinationLockRepository", lambda session: mock_repo)
    monkeypatch.setattr("src.data.distributed_lock.sleep", lambda s: None)

    # Contention: success=False
    mock_repo.acquire_lock.return_value = SimpleNamespace(success=False)

    # Mock time to advance exactly 10s per call to DistributedLock.time
    # DistributedLock.acquire calls time() at start, then in each loop to check elapsed.
    times = [1000.0, 1005.0, 1015.0, 1025.0, 1035.0]
    time_iter = iter(times)
    monkeypatch.setattr("src.data.distributed_lock.time", lambda: next(time_iter, 1035.0))

    lock = DistributedLock(lambda: None, "test_lock")  # type: ignore[return-value]

    with pytest.raises(LockAcquisitionTimeout, match="Failed to acquire lock 'test_lock' within 30s ceiling"):
        lock.acquire(max_retries=10)

    # Should have tried multiple times until time exceeded 30s
    assert mock_repo.acquire_lock.call_count > 1


@pytest.mark.unit
def test_ttl_validation_in_init() -> None:
    """Verify DistributedLock rejects TTLs exceeding 300s."""

    def factory():
        """Return None for testing."""
        return None

    # 300 is fine
    DistributedLock(factory, "test", ttl_seconds=300)  # type: ignore[arg-type]

    # 301 is not
    with pytest.raises(ValueError, match="exceeds maximum allowed value of 300"):
        DistributedLock(factory, "test", ttl_seconds=301)  # type: ignore[arg-type]


@pytest.mark.unit
def test_acquire_timeout_seconds_clamping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify DistributedLock.acquire clamps timeout_seconds to 30.0s."""
    mock_repo = MagicMock()
    monkeypatch.setattr("src.data.distributed_lock.session_scope", _mock_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.CoordinationLockRepository", lambda session: mock_repo)
    monkeypatch.setattr("src.data.distributed_lock.sleep", lambda s: None)

    # Contention: success=False
    mock_repo.acquire_lock.return_value = SimpleNamespace(success=False)

    times = [1000.0, 1035.0]
    time_iter = iter(times)
    monkeypatch.setattr("src.data.distributed_lock.time", lambda: next(time_iter, 1035.0))

    lock = DistributedLock(lambda: None, "test_lock")  # type: ignore[return-value]

    with pytest.raises(LockAcquisitionTimeout, match="within 30s ceiling"):
        lock.acquire(max_retries=5, timeout_seconds=100.0)

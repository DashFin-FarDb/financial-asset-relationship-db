"""Unit tests for DistributedLock runtime behavior."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.data.distributed_lock import DistributedLock, LockLifecycleState


@contextmanager
def _mock_session_scope(factory):
    """Mock session_scope that yields a MagicMock session."""
    yield MagicMock()


@pytest.mark.unit
def test_acquire_raises_on_persistence_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Database exceptions during acquisition should not be reported as contention."""

    class _FailingScope:
        def __enter__(self):
            raise RuntimeError("db unavailable")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("src.data.distributed_lock.session_scope", lambda _factory: _FailingScope())
    lock = DistributedLock(lambda: None, "graph_rebuild")  # type: ignore[arg-type]

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
    lock = DistributedLock(lambda: None, "graph_rebuild")  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="db unavailable"):
        lock.check_state()


@pytest.mark.unit
def test_refresh_success_after_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify refresh succeeds after recovering from transient failures."""
    mock_repo = MagicMock()
    # Attempt 1 -> SQLAlchemyError
    # Attempt 2 -> SQLAlchemyError
    # Attempt 3 -> Success
    mock_repo.refresh_lock.side_effect = [
        SQLAlchemyError("transient 1"),
        SQLAlchemyError("transient 2"),
        MagicMock(success=True, fencing_token=123),
    ]

    monkeypatch.setattr("src.data.distributed_lock.session_scope", _mock_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.CoordinationLockRepository", lambda session: mock_repo)
    monkeypatch.setattr("src.data.distributed_lock.sleep", lambda seconds: None)

    # DistributedLock requires a session factory
    lock = DistributedLock(lambda: None, "test_lock")  # type: ignore[arg-type]
    res = lock.refresh(max_retries=2)

    assert res is not False
    assert res.state == LockLifecycleState.REFRESHED
    assert res.fencing_token == 123
    assert mock_repo.refresh_lock.call_count == 3


@pytest.mark.unit
def test_refresh_retry_budget_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify refresh fails when retry budget for transient errors is exhausted."""
    mock_repo = MagicMock()
    # Always raise SQLAlchemyError
    mock_repo.refresh_lock.side_effect = SQLAlchemyError("persistent failure")

    monkeypatch.setattr("src.data.distributed_lock.session_scope", _mock_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.CoordinationLockRepository", lambda session: mock_repo)
    monkeypatch.setattr("src.data.distributed_lock.sleep", lambda seconds: None)

    lock = DistributedLock(lambda: None, "test_lock")  # type: ignore[arg-type]
    res = lock.refresh(max_retries=2)

    assert res is False
    assert mock_repo.refresh_lock.call_count == 3


@pytest.mark.unit
def test_refresh_no_retry_on_contention(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify refresh does not retry when the lock is held by another owner."""
    mock_repo = MagicMock()
    # Return success=False (contention), not an exception
    mock_repo.refresh_lock.return_value = MagicMock(success=False)

    monkeypatch.setattr("src.data.distributed_lock.session_scope", _mock_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.CoordinationLockRepository", lambda session: mock_repo)
    monkeypatch.setattr("src.data.distributed_lock.sleep", lambda seconds: None)

    lock = DistributedLock(lambda: None, "test_lock")  # type: ignore[arg-type]
    res = lock.refresh(max_retries=2)

    assert res is False
    assert mock_repo.refresh_lock.call_count == 1


@pytest.mark.unit
def test_refresh_no_retry_on_unexpected_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify refresh fails immediately on unexpected non-transient exceptions."""
    mock_repo = MagicMock()
    # Raise an exception not in (SQLAlchemyError, OSError)
    mock_repo.refresh_lock.side_effect = ValueError("unexpected bug")

    monkeypatch.setattr("src.data.distributed_lock.session_scope", _mock_session_scope)
    monkeypatch.setattr("src.data.distributed_lock.CoordinationLockRepository", lambda session: mock_repo)
    monkeypatch.setattr("src.data.distributed_lock.sleep", lambda seconds: None)

    lock = DistributedLock(lambda: None, "test_lock")  # type: ignore[arg-type]

    # In the current implementation, unexpected exceptions are caught and return False
    res = lock.refresh(max_retries=2)

    assert res is False
    assert mock_repo.refresh_lock.call_count == 1

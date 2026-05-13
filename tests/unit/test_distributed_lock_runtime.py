"""Unit tests for DistributedLock runtime behavior."""

from __future__ import annotations

import pytest

from src.data.distributed_lock import DistributedLock


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

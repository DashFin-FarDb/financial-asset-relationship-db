"""Unit tests for Idempotency-Key support on POST /api/graph/rebuild."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from api.idempotency import (
    IdempotencyConflictError,
    IdempotencyStore,
    InvalidIdempotencyKeyError,
    fingerprint_request,
    normalize_idempotency_key,
    rebuild_idempotency_store,
)
from api.models import User
from api.routers import graph_admin

UTC = timezone.utc


def test_idempotency_store_replay_conflict_abort_and_expiry() -> None:
    """IdempotencyStore replays completed responses, detects conflicts, releases aborts, and expires TTL."""
    now = datetime(2026, 11, 27, 8, 0, 0, tzinfo=UTC)
    store = IdempotencyStore(ttl_seconds=60.0, clock=lambda: now)
    fp_a = fingerprint_request("/api/graph/rebuild", "False")
    fp_b = fingerprint_request("/api/graph/rebuild", "True")

    is_replay, cached = store.begin(scope="rebuild", actor="admin", key="req-1", fingerprint=fp_a)
    assert not is_replay
    assert cached is None

    # Concurrent duplicate while in-progress raises conflict
    with pytest.raises(IdempotencyConflictError, match="already in progress"):
        store.begin(scope="rebuild", actor="admin", key="req-1", fingerprint=fp_a)

    store.complete(scope="rebuild", actor="admin", key="req-1", fingerprint=fp_a, response={"job_id": "job-123"})

    # Duplicate after completion replays original response
    is_replay, cached = store.begin(scope="rebuild", actor="admin", key="req-1", fingerprint=fp_a)
    assert is_replay
    assert cached == {"job_id": "job-123"}

    # Reusing same key with different parameters raises conflict
    with pytest.raises(IdempotencyConflictError, match="different request parameters"):
        store.begin(scope="rebuild", actor="admin", key="req-1", fingerprint=fp_b)

    # Aborted key can be retried cleanly
    store.begin(scope="rebuild", actor="admin", key="req-2", fingerprint=fp_a)
    store.abort(scope="rebuild", actor="admin", key="req-2")
    is_replay, cached = store.begin(scope="rebuild", actor="admin", key="req-2", fingerprint=fp_a)
    assert not is_replay

    # Expired key is pruned and treated as fresh
    now = now + timedelta(seconds=61)
    is_replay, cached = store.begin(scope="rebuild", actor="admin", key="req-1", fingerprint=fp_a)
    assert not is_replay


def test_normalize_idempotency_key_rejects_invalid_values() -> None:
    """Malformed or oversized Idempotency-Key values raise InvalidIdempotencyKeyError."""
    assert normalize_idempotency_key(None) is None
    assert normalize_idempotency_key("   ") is None
    assert normalize_idempotency_key("rebuild-2026-11-27:001") == "rebuild-2026-11-27:001"

    with pytest.raises(InvalidIdempotencyKeyError):
        normalize_idempotency_key("x" * 129)
    with pytest.raises(InvalidIdempotencyKeyError):
        normalize_idempotency_key("bad key with spaces!")


@pytest.mark.asyncio
async def test_rebuild_graph_replays_cached_response_for_same_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate POST /api/graph/rebuild with the same Idempotency-Key replays without re-executing."""
    rebuild_idempotency_store.clear()
    calls = 0

    class _DummyLock:
        async def acquire(self) -> None:
            return None

        def release(self) -> None:
            return None

    async def _fake_execute(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {"status": "rebuilt", "job_id": f"job-{calls}"}

    monkeypatch.setattr(graph_admin, "_claim_rebuild_or_raise", lambda: _DummyLock())
    monkeypatch.setattr(graph_admin, "_execute_rebuild_with_error_handling", _fake_execute)
    user = User(username="admin", disabled=False)

    try:
        first = await graph_admin.rebuild_graph(current_user=user, idempotency_key="idem-rebuild-001")
        second = await graph_admin.rebuild_graph(current_user=user, idempotency_key="idem-rebuild-001")
        assert first == second == {"status": "rebuilt", "job_id": "job-1"}
        assert calls == 1

        # Malformed key returns 400
        with pytest.raises(HTTPException) as exc_info:
            await graph_admin.rebuild_graph(current_user=user, idempotency_key="invalid key!")
        assert exc_info.value.status_code == 400
    finally:
        rebuild_idempotency_store.clear()

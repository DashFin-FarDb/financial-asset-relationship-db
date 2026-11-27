"""Unit tests for security, rate-limit, idempotency, and ingestion Prometheus metrics."""

from __future__ import annotations

import pytest

from api.idempotency import IdempotencyConflictError, IdempotencyStore
from api.metrics import (
    AUTH_LOGIN_TOTAL,
    AUTH_TOKEN_REVOCATIONS_TOTAL,
    HTTP_RATE_LIMIT_EXCEEDED_TOTAL,
    INGESTION_RESILIENCE_EVENTS_TOTAL,
    RATE_LIMIT_STORE_BACKEND_INFO,
    REBUILD_IDEMPOTENCY_TOTAL,
    record_auth_login,
    record_auth_token_revocation,
    record_ingestion_resilience_event,
    record_rate_limit_backend,
    record_rate_limit_exceeded,
)


def test_auth_login_and_revocation_metrics() -> None:
    """Auth login outcomes and token revocations increment bounded counters."""
    before_ok = AUTH_LOGIN_TOTAL.labels(outcome="success")._value.get()  # pylint: disable=protected-access
    before_fail = AUTH_LOGIN_TOTAL.labels(outcome="failure")._value.get()  # pylint: disable=protected-access
    before_rev = AUTH_TOKEN_REVOCATIONS_TOTAL._value.get()  # pylint: disable=protected-access

    record_auth_login("success")
    record_auth_login("failure")
    record_auth_login("unexpected")
    record_auth_token_revocation()

    assert AUTH_LOGIN_TOTAL.labels(outcome="success")._value.get() == before_ok + 1  # pylint: disable=protected-access
    assert (
        AUTH_LOGIN_TOTAL.labels(outcome="failure")._value.get() == before_fail + 2
    )  # pylint: disable=protected-access
    assert AUTH_TOKEN_REVOCATIONS_TOTAL._value.get() == before_rev + 1  # pylint: disable=protected-access


def test_rate_limit_backend_and_exceeded_metrics() -> None:
    """Rate-limit backend info gauge activates exactly one backend and counts 429s."""
    record_rate_limit_backend("redis")
    assert RATE_LIMIT_STORE_BACKEND_INFO.labels(backend="redis")._value.get() == 1.0  # pylint: disable=protected-access
    assert (
        RATE_LIMIT_STORE_BACKEND_INFO.labels(backend="memory")._value.get() == 0.0
    )  # pylint: disable=protected-access

    before_429 = HTTP_RATE_LIMIT_EXCEEDED_TOTAL.labels(route="/token")._value.get()  # pylint: disable=protected-access
    record_rate_limit_exceeded("/token")
    assert (
        HTTP_RATE_LIMIT_EXCEEDED_TOTAL.labels(route="/token")._value.get() == before_429 + 1
    )  # pylint: disable=protected-access


def test_idempotency_store_records_miss_hit_and_conflict_metrics() -> None:
    """IdempotencyStore emits miss, hit, and conflict counters."""
    store = IdempotencyStore(ttl_seconds=60.0)
    before_miss = REBUILD_IDEMPOTENCY_TOTAL.labels(outcome="miss")._value.get()  # pylint: disable=protected-access
    before_hit = REBUILD_IDEMPOTENCY_TOTAL.labels(outcome="hit")._value.get()  # pylint: disable=protected-access
    before_conflict = REBUILD_IDEMPOTENCY_TOTAL.labels(
        outcome="conflict"
    )._value.get()  # pylint: disable=protected-access

    is_replay, _ = store.begin(scope="rebuild", actor="admin", key="k1", fingerprint="fp1")
    assert is_replay is False
    store.complete(scope="rebuild", actor="admin", key="k1", fingerprint="fp1", response={"ok": True})

    is_replay, cached = store.begin(scope="rebuild", actor="admin", key="k1", fingerprint="fp1")
    assert is_replay is True and cached == {"ok": True}

    with pytest.raises(IdempotencyConflictError):
        store.begin(scope="rebuild", actor="admin", key="k1", fingerprint="fp2")

    assert (
        REBUILD_IDEMPOTENCY_TOTAL.labels(outcome="miss")._value.get() == before_miss + 1
    )  # pylint: disable=protected-access
    assert (
        REBUILD_IDEMPOTENCY_TOTAL.labels(outcome="hit")._value.get() == before_hit + 1
    )  # pylint: disable=protected-access
    assert (
        REBUILD_IDEMPOTENCY_TOTAL.labels(outcome="conflict")._value.get() == before_conflict + 1
    )  # pylint: disable=protected-access


def test_ingestion_resilience_event_metric_clamps_labels() -> None:
    """Ingestion resilience counter normalizes provider names and clamps outcomes."""
    before = INGESTION_RESILIENCE_EVENTS_TOTAL.labels(
        provider="yfinance", outcome="retry"
    )._value.get()  # pylint: disable=protected-access
    record_ingestion_resilience_event("YFinance", "retry")
    assert (
        INGESTION_RESILIENCE_EVENTS_TOTAL.labels(provider="yfinance", outcome="retry")._value.get() == before + 1
    )  # pylint: disable=protected-access

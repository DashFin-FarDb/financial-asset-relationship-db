"""Unit tests for resilient data ingestion (retries, circuit breaker, schema & freshness SLA)."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest

from src.data.ingestion_resilience import (
    CircuitBreakerOpenError,
    CircuitState,
    FreshnessSLA,
    PayloadSchemaError,
    ProviderCircuitBreaker,
    ResilientIngestionAdapter,
    RetryPolicy,
    StaleDataError,
)
from src.logic.reconciliation_engine import RebuildCancelledError

UTC = timezone.utc


def test_resilient_adapter_retries_transient_error_and_succeeds() -> None:
    """Transient provider errors retry with bounded backoff and succeed once provider recovers."""
    attempts = 0
    delays: list[float] = []
    now = datetime(2026, 11, 27, 6, 0, 0, tzinfo=UTC)

    def flaky_fetcher() -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("upstream timeout")
        return {"symbol": "AAPL", "price": 225.50, "fetched_at": now - timedelta(seconds=12)}

    adapter = ResilientIngestionAdapter(
        "yfinance",
        circuit_breaker=ProviderCircuitBreaker("yfinance", failure_threshold=5),
        retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0.1, max_delay_seconds=1.0),
        freshness_sla=FreshnessSLA(max_staleness_seconds=300.0),
        sleep_fn=delays.append,
    )
    result = adapter.fetch(flaky_fetcher, now_fn=lambda: now)

    assert result.attempts == 3
    assert result.payload["symbol"] == "AAPL"
    assert result.age_seconds == pytest.approx(12.0)
    assert result.circuit_state == CircuitState.CLOSED
    assert delays == [pytest.approx(0.1), pytest.approx(0.2)]


def test_circuit_breaker_trips_open_half_open_and_recovers() -> None:
    """Circuit trips OPEN at threshold, rejects fast, probes HALF_OPEN after timeout, and closes on success."""
    clock_value = 100.0
    breaker = ProviderCircuitBreaker(
        "market_feed",
        failure_threshold=2,
        reset_timeout_seconds=10.0,
        monotonic_clock=lambda: clock_value,
    )
    adapter = ResilientIngestionAdapter(
        "market_feed",
        circuit_breaker=breaker,
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_seconds=0.0),
    )

    def always_fail() -> dict[str, object]:
        raise RuntimeError("503 service unavailable")

    with pytest.raises(RuntimeError):
        adapter.fetch(always_fail)
    assert breaker.state == CircuitState.CLOSED

    with pytest.raises(RuntimeError):
        adapter.fetch(always_fail)
    assert breaker.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpenError):
        adapter.fetch(lambda: {"symbol": "MSFT", "price": 410.0})

    # Advance past reset timeout -> HALF_OPEN probe succeeds -> CLOSED
    clock_value = 115.0
    assert breaker.state == CircuitState.HALF_OPEN
    recovered = adapter.fetch(lambda: {"symbol": "MSFT", "price": 410.0})
    assert recovered.circuit_state == CircuitState.CLOSED


def test_schema_validation_and_freshness_sla_enforcement() -> None:
    """Invalid schemas, non-finite/non-positive prices, and stale timestamps are rejected."""
    now = datetime(2026, 11, 27, 6, 0, 0, tzinfo=UTC)
    adapter = ResilientIngestionAdapter(
        "yfinance",
        retry_policy=RetryPolicy(max_attempts=1, initial_delay_seconds=0.0),
        freshness_sla=FreshnessSLA(max_staleness_seconds=60.0),
    )

    with pytest.raises(PayloadSchemaError, match="missing required fields"):
        adapter.fetch(lambda: {"symbol": "AAPL"}, now_fn=lambda: now)

    with pytest.raises(PayloadSchemaError, match="positive finite number"):
        adapter.fetch(lambda: {"symbol": "AAPL", "price": float("nan")}, now_fn=lambda: now)

    with pytest.raises(PayloadSchemaError, match="positive finite number"):
        adapter.fetch(lambda: {"symbol": "AAPL", "price": -5.0}, now_fn=lambda: now)

    with pytest.raises(StaleDataError, match="stale"):
        adapter.fetch(
            lambda: {"symbol": "AAPL", "price": 225.0, "fetched_at": now - timedelta(seconds=120)},
            now_fn=lambda: now,
        )


def test_cancel_event_aborts_immediately_stage_5c() -> None:
    """Setting cancel_event immediately aborts ingestion with RebuildCancelledError (Stage 5C)."""
    cancel_event = threading.Event()
    cancel_event.set()
    adapter = ResilientIngestionAdapter("yfinance")

    with pytest.raises(RebuildCancelledError):
        adapter.fetch(lambda: {"symbol": "AAPL", "price": 225.0}, cancel_event=cancel_event)

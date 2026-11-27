"""Resilient market-data ingestion primitives (retries, circuit breaker, schema & freshness SLA).

Designed for production financial data adapters (e.g., Yahoo Finance or institutional market feeds):
- Thread-safe per-provider circuit breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
- Bounded exponential-backoff retries honoring Stage 5C ``cancel_event`` cancellation immediately.
- Strict payload schema validation (required fields, positive finite numeric checks).
- Data-freshness SLA enforcement (``max_staleness_seconds``).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.logic.reconciliation_engine import RebuildCancelledError
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

UTC = timezone.utc
logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Finite states for a provider circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a provider call is rejected because its circuit breaker is OPEN."""


class PayloadSchemaError(ValueError):
    """Raised when an ingested provider payload violates schema or numeric invariants."""


class StaleDataError(ValueError):
    """Raised when an ingested provider payload exceeds the configured freshness SLA."""


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential-backoff retry configuration."""

    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 5.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        """Validate retry policy bounds."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must be >= 0")
        if self.max_delay_seconds < 0:
            raise ValueError("max_delay_seconds must be >= 0")
        if self.backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be >= 1.0")

    def delay_for_attempt(self, attempt_number: int) -> float:
        """Compute bounded backoff delay after a failed 1-indexed attempt."""
        exponent = max(0, attempt_number - 1)
        raw = self.initial_delay_seconds * (self.backoff_multiplier**exponent)
        return float(min(self.max_delay_seconds, raw))


@dataclass(frozen=True)
class FreshnessSLA:
    """Data-freshness SLA bounds for ingested market payloads."""

    max_staleness_seconds: float = 900.0
    max_future_skew_seconds: float = 60.0

    def __post_init__(self) -> None:
        """Validate freshness SLA bounds."""
        if self.max_staleness_seconds <= 0:
            raise ValueError("max_staleness_seconds must be > 0")
        if self.max_future_skew_seconds < 0:
            raise ValueError("max_future_skew_seconds must be >= 0")


@dataclass(frozen=True)
class IngestionResult:
    """Validated result returned by ``ResilientIngestionAdapter.fetch``."""

    provider: str
    payload: Mapping[str, Any]
    fetched_at: datetime
    age_seconds: float
    attempts: int
    circuit_state: CircuitState


class ProviderCircuitBreaker:
    """Thread-safe circuit breaker guarding an external data provider."""

    def __init__(
        self,
        provider_name: str,
        *,
        failure_threshold: int = 5,
        reset_timeout_seconds: float = 30.0,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the circuit breaker in the CLOSED state."""
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if reset_timeout_seconds <= 0:
            raise ValueError("reset_timeout_seconds must be > 0")
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.reset_timeout_seconds = reset_timeout_seconds
        self._clock = monotonic_clock or time.monotonic
        self._lock = threading.RLock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> CircuitState:
        """Return the current circuit state, transitioning OPEN -> HALF_OPEN when timeout elapses."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            return self._state

    def _maybe_transition_to_half_open_locked(self) -> None:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if (self._clock() - self._opened_at) >= self.reset_timeout_seconds:
                self._state = CircuitState.HALF_OPEN

    def before_call(self) -> None:
        """Permit or reject an outgoing provider call based on current circuit state."""
        with self._lock:
            self._maybe_transition_to_half_open_locked()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(f"Circuit breaker for provider '{self.provider_name}' is OPEN.")

    def record_success(self) -> None:
        """Reset failure counters and close the circuit after a successful call."""
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None
            self._state = CircuitState.CLOSED

    def record_failure(self) -> CircuitState:
        """Record a provider failure and trip the circuit to OPEN when threshold is reached."""
        with self._lock:
            self._consecutive_failures += 1
            if self._state == CircuitState.HALF_OPEN or self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
            return self._state


def _validate_positive_numeric_fields(
    payload: Mapping[str, Any],
    positive_numeric_fields: Sequence[str],
) -> None:
    """Ensure every present numeric field is a positive finite number (not bool)."""
    for num_field in positive_numeric_fields:
        raw_val = payload.get(num_field)
        if raw_val is None:
            continue
        if isinstance(raw_val, bool):
            raise PayloadSchemaError(f"Field '{num_field}' must be numeric, not bool.")
        try:
            numeric = float(raw_val)
        except (TypeError, ValueError) as exc:
            raise PayloadSchemaError(f"Field '{num_field}' is not a valid number.") from exc
        if not math.isfinite(numeric) or numeric <= 0:
            raise PayloadSchemaError(f"Field '{num_field}' must be a positive finite number.")


def _parse_payload_timestamp(raw_ts: Any, timestamp_field: str, reference_now: datetime) -> datetime:
    """Normalize an optional datetime or ISO-8601 string payload timestamp to UTC."""
    if raw_ts is None:
        return reference_now
    if isinstance(raw_ts, datetime):
        return raw_ts if raw_ts.tzinfo is not None else raw_ts.replace(tzinfo=UTC)
    if isinstance(raw_ts, str):
        try:
            parsed = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PayloadSchemaError(f"Invalid ISO timestamp in '{timestamp_field}'.") from exc
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    raise PayloadSchemaError(f"Unsupported timestamp type for '{timestamp_field}'.")


def validate_provider_payload(
    payload: Mapping[str, Any],
    *,
    required_fields: Sequence[str] = ("symbol", "price"),
    positive_numeric_fields: Sequence[str] = ("price",),
    freshness_sla: FreshnessSLA | None = None,
    timestamp_field: str = "fetched_at",
    now: datetime | None = None,
) -> tuple[datetime, float]:
    """Validate payload schema, positive finite numbers, and freshness SLA.

    Returns ``(fetched_at_utc, age_seconds)``.
    """
    if not isinstance(payload, Mapping):
        raise PayloadSchemaError("Provider payload must be a mapping.")

    missing = [key for key in required_fields if key not in payload or payload[key] is None]
    if missing:
        raise PayloadSchemaError(f"Provider payload missing required fields: {', '.join(missing)}")

    _validate_positive_numeric_fields(payload, positive_numeric_fields)

    reference_now = now or datetime.now(UTC)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=UTC)

    fetched_at = _parse_payload_timestamp(payload.get(timestamp_field), timestamp_field, reference_now)
    age_seconds = (reference_now - fetched_at).total_seconds()
    sla = freshness_sla or FreshnessSLA()
    if age_seconds > sla.max_staleness_seconds:
        raise StaleDataError(f"Provider payload is stale ({age_seconds:.1f}s > SLA {sla.max_staleness_seconds:.1f}s).")
    if age_seconds < -sla.max_future_skew_seconds:
        raise StaleDataError(f"Provider payload timestamp is too far in the future ({-age_seconds:.1f}s skew).")

    return fetched_at, max(0.0, age_seconds)


class ResilientIngestionAdapter:
    """Resilient provider ingestion wrapper combining circuit breaker, retries, and SLA checks."""

    def __init__(
        self,
        provider_name: str,
        *,
        circuit_breaker: ProviderCircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        freshness_sla: FreshnessSLA | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        """Initialize the resilient ingestion adapter."""
        self.provider_name = provider_name
        self.circuit_breaker = circuit_breaker or ProviderCircuitBreaker(provider_name)
        self.retry_policy = retry_policy or RetryPolicy()
        self.freshness_sla = freshness_sla or FreshnessSLA()
        self._sleep = sleep_fn or time.sleep

    def _wait_with_cancel(self, delay: float, cancel_event: threading.Event | None) -> None:
        if delay <= 0:
            if cancel_event is not None and cancel_event.is_set():
                raise RebuildCancelledError("Data ingestion cancelled during retry.")
            return
        if cancel_event is not None:
            if cancel_event.wait(timeout=delay):
                raise RebuildCancelledError("Data ingestion cancelled during retry backoff.")
            return
        self._sleep(delay)

    def fetch(
        self,
        fetcher: Callable[[], Mapping[str, Any]],
        *,
        required_fields: Sequence[str] = ("symbol", "price"),
        positive_numeric_fields: Sequence[str] = ("price",),
        cancel_event: threading.Event | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> IngestionResult:
        """Execute ``fetcher`` with circuit breaking, bounded retries, and schema/freshness checks."""
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            if cancel_event is not None and cancel_event.is_set():
                raise RebuildCancelledError("Data ingestion cancelled before provider call.")

            self.circuit_breaker.before_call()
            try:
                payload = fetcher()
                fetched_at, age_seconds = validate_provider_payload(
                    payload,
                    required_fields=required_fields,
                    positive_numeric_fields=positive_numeric_fields,
                    freshness_sla=self.freshness_sla,
                    now=now_fn() if now_fn is not None else None,
                )
            except (PayloadSchemaError, StaleDataError):
                # Validation/SLA defects are recorded against the provider without blind retries.
                self.circuit_breaker.record_failure()
                raise
            except RebuildCancelledError:
                raise
            except Exception as exc:  # pylint: disable=broad-exception-caught
                last_error = exc
                new_state = self.circuit_breaker.record_failure()
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="ingestion_provider_attempt_failed",
                        message=f"Provider {self.provider_name} attempt {attempt} failed",
                        metadata={
                            "provider": self.provider_name,
                            "attempt": attempt,
                            "max_attempts": self.retry_policy.max_attempts,
                            "circuit_state": new_state.value,
                        },
                    ),
                )
                if new_state == CircuitState.OPEN or attempt >= self.retry_policy.max_attempts:
                    raise
                delay = self.retry_policy.delay_for_attempt(attempt)
                self._wait_with_cancel(delay, cancel_event)
                continue

            self.circuit_breaker.record_success()
            return IngestionResult(
                provider=self.provider_name,
                payload=payload,
                fetched_at=fetched_at,
                age_seconds=age_seconds,
                attempts=attempt,
                circuit_state=self.circuit_breaker.state,
            )

        if last_error is not None:  # pragma: no cover
            raise last_error
        raise RuntimeError(f"Provider '{self.provider_name}' failed without error details.")  # pragma: no cover

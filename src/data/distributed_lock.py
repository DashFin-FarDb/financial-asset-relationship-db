"""Database-backed distributed lock for rebuild coordination."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from time import sleep, time
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.repository import CoordinationLockRepository, LockStateSnapshot, LockWriteResult, session_scope
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

UTC = timezone.utc


logger = logging.getLogger(__name__)


class LockState(str, Enum):
    """Explicit states of a distributed lock returned from database check."""

    VALID = "valid"
    EXPIRED = "expired"
    UNKNOWN = "unknown"
    LOST = "lost"


class LockEventType(str, Enum):
    """Types of structured coordination lifecycle events."""

    ACQUIRE_ATTEMPT = "acquire_attempt"
    ACQUIRED = "acquired"
    REFRESHED = "refreshed"
    CONTENTED = "contented"
    RELEASED = "released"
    FAILED = "failed"
    STATE_CHECK = "state_check"
    TRANSIENT_ERROR = "transient_error"
    UNEXPECTED_ERROR = "unexpected_error"


@dataclass(frozen=True)
class LockEvent:
    """Immutable coordination event representation for structured observability."""

    event_type: LockEventType
    lock_name: str
    holder_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class LockMetrics:
    """Abstract metrics interface (Prometheus, OpenTelemetry, etc.)."""

    def inc(self, metric: str, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        raise NotImplementedError

    def observe(self, metric: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a histogram/summary metric."""
        raise NotImplementedError


class LockAcquisitionTimeout(Exception):
    """Raised when lock acquisition exceeds the deterministic wait ceiling."""


class LockLifecycleState(str, Enum):
    """Explicit lifecycle states of the coordination primitive state machine."""

    INITIAL = "initial"
    ACQUIRED = "acquired"
    REFRESHED = "refreshed"
    CONTENTED = "contented"
    LOST = "lost"
    RELEASED = "released"


MAX_TTL = 300


@dataclass(frozen=True)
class LockLease:
    """Represents an active, fenced distributed lock lease."""

    state: LockLifecycleState
    fencing_token: int


class DistributedLock:
    """
    A fully observable database-backed distributed lock coordination primitive.

    Features:
    - Explicit lifecycle state machine tracking.
    - Pluggable metrics hooks.
    - Structured immutable lifecycle event emission.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session] | None = None,
        lock_name: str | None = None,
        *,
        coordination_session_factory: Callable[[], Session] | None = None,
        metrics: LockMetrics | None = None,
        event_sink: Callable[[LockEvent], None] | None = None,
        holder_id: str | None = None,
        ttl_seconds: int = 300,
    ) -> None:
        """Create a DistributedLock configured with a database session factory.

        Configure with lock identity and optional observability hooks.

        Parameters:
            session_factory (Callable[[], Session] | None): Backward-compatible factory for DB sessions;
            used if `coordination_session_factory` is not provided.
            lock_name (str | None): Unique name for the lock; required.
            coordination_session_factory (Callable[[], Session] | None):
            Preferred factory for coordination (primary-only) sessions; takes precedence over `session_factory`.
            metrics (LockMetrics | None): Optional metrics collector; methods `inc`
            and `observe` will be called for lifecycle metrics.
            event_sink (Callable[[LockEvent], None] | None): Optional consumer for immutable structured lock events.
            holder_id (str | None): Optional identifier for the lock holder; a UUID will be generated when omitted.
            ttl_seconds (int): Time-to-live for the lock in seconds; defaults to 300. Max 300.

        Notes:
            Either `coordination_session_factory` or `session_factory` must be provided;
            a TypeError is raised if both are missing.
        """
        resolved_factory = coordination_session_factory or session_factory
        if resolved_factory is None:
            raise TypeError(
                "__init__() missing 1 required positional/keyword argument: "
                "'coordination_session_factory' or 'session_factory'"
            )
        if lock_name is None:
            raise TypeError("__init__() missing 1 required positional argument: 'lock_name'")

        if ttl_seconds > MAX_TTL:
            raise ValueError(f"ttl_seconds ({ttl_seconds}) exceeds maximum allowed value of {MAX_TTL}")

        self.coordination_session_factory = resolved_factory
        self.session_factory = resolved_factory
        self.lock_name = lock_name
        self.holder_id = holder_id or str(uuid.uuid4())
        self.ttl_seconds = ttl_seconds
        self.metrics = metrics
        self.event_sink = event_sink
        self._state = LockLifecycleState.INITIAL
        self._fencing_token = 0

    def _emit(self, event: LockEvent) -> None:
        """
        Emit a structured coordination lifecycle event to the configured event sink.

        If no event sink is configured this is a no-op. If the sink raises an exception, an `ObservabilityEvent`
        named `lock_event_sink_failed` is emitted via `log_event` describing the failure.

        Parameters:
            event (LockEvent): The immutable event payload to emit.
        """
        if self.event_sink:
            try:
                self.event_sink(event)
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="lock_event_sink_failed",
                        message=f"Failed to write coordination event to sink: {type(exc).__name__}",
                        metadata={"error": type(exc).__name__},
                    ),
                )

    def _metric(self, name: str, labels: dict[str, str] | None = None, value: float | None = None) -> None:
        """
        Publish a metric using the configured metrics interface when available.

        Parameters:
            name (str): Metric name.
            labels (dict[str, str] | None): Optional metric labels; pass None for no labels.
            value (float | None): If provided, record an observation with this value.
            If omitted and the metric name does not contain "latency", increment a counter.

        Notes:
            If a metrics backend is not configured, this is a no-op.
            On publication failure, emits an `ObservabilityEvent` via `log_event`.
        """
        if self.metrics:
            try:
                if value is not None or "latency" in name:
                    self.metrics.observe(name, value if value is not None else 0.0, labels)
                else:
                    self.metrics.inc(name, labels)
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="lock_metrics_publication_failed",
                        message=f"Failed to publish metric '{name}': {type(exc).__name__}",
                        metadata={"metric_name": name, "error": type(exc).__name__},
                    ),
                )

    def _set_state(self, state: LockLifecycleState) -> None:
        """
        Update the lock's internal lifecycle state.

        Parameters:
            state (LockLifecycleState): New lifecycle state to set.
        """
        self._state = state

    @property
    def state(self) -> LockLifecycleState:
        """Return the current internal lifecycle state of the lock."""
        return self._state

    def _attempt_lock_acquisition(self) -> LockWriteResult:
        """
        Execute coordination repository lock acquisition within transaction scope.

        Returns:
            LockWriteResult: Result details containing success indicator and fencing token.
        """
        with session_scope(self.coordination_session_factory) as session:
            repo = CoordinationLockRepository(session)
            return repo.acquire_lock(
                lock_name=self.lock_name,
                holder_id=self.holder_id,
                ttl_seconds=self.ttl_seconds,
            )

    def _handle_acquire_exception(
        self,
        exc: Exception,
        start_time: float,
        retries: int,
        max_retries: int,
        timeout_seconds: float = 30.0,
    ) -> None:
        """
        Handle and classify exceptions raised during lock acquisition attempts.

        Parameters:
            exc (Exception): Caught exception.
            start_time (float): Start timestamp of the overall acquisition process.
            retries (int): Number of retries attempted so far.
            max_retries (int): Allowed maximum number of retries.
            timeout_seconds (float): Timeout ceiling in seconds.

        Raises:
            LockAcquisitionTimeout: If database error occurs and retry limit or timeout limit is reached.
            Exception: Re-raises the caught exception if not a DB connectivity error.
        """
        self._emit(
            LockEvent(
                LockEventType.UNEXPECTED_ERROR,
                self.lock_name,
                self.holder_id,
                metadata={"error": type(exc).__name__},
            )
        )
        self._metric("lock_errors_total")
        if not isinstance(exc, (SQLAlchemyError, OSError)):
            self._set_state(LockLifecycleState.LOST)
            raise exc
        if retries >= max_retries or (time() - start_time) >= timeout_seconds:
            self._set_state(LockLifecycleState.LOST)
            msg = (
                f"Failed to acquire lock '{self.lock_name}' "
                f"due to database errors (elapsed: {time() - start_time:.2f}s)"
            )
            raise LockAcquisitionTimeout(msg) from exc

    def _handle_acquire_contention(
        self,
        start_time: float,
        retries: int,
        max_retries: int,
        timeout_seconds: float = 30.0,
    ) -> float:
        """
        Handle contested lock state checks, asserting wait ceilings and retries.

        Parameters:
            start_time (float): Start timestamp of the overall acquisition process.
            retries (int): Number of retries attempted so far.
            max_retries (int): Allowed maximum number of retries.
            timeout_seconds (float): Timeout ceiling in seconds.

        Returns:
            float: Elapsed time in seconds since the start of acquisition.

        Raises:
            LockAcquisitionTimeout: If the retry budget or timeout ceiling is exceeded.
        """
        elapsed = time() - start_time
        if retries >= max_retries or elapsed >= timeout_seconds:
            self._set_state(LockLifecycleState.CONTENTED)
            self._emit(
                LockEvent(
                    LockEventType.CONTENTED,
                    self.lock_name,
                    self.holder_id,
                )
            )
            self._metric("lock_timeout_total")
            msg = (
                f"Failed to acquire lock '{self.lock_name}' within {timeout_seconds:g}s ceiling "
                f"(elapsed: {elapsed:.2f}s, max_retries: {max_retries})"
            )
            raise LockAcquisitionTimeout(msg)
        return elapsed

    def acquire(
        self, *, retry_interval_seconds: float = 1.0, max_retries: int = 0, timeout_seconds: float = 30.0
    ) -> LockLease:
        """
        Attempt to acquire the distributed lock, using deterministic back-off.

        Parameters:
            retry_interval_seconds (float): Initial seconds to wait between retry attempts.
            max_retries (int): Maximum number of retry attempts before giving up.
                The operation is capped by the timeout_seconds ceiling (default 30s per GEMINI.md).
            timeout_seconds (float): Timeout ceiling in seconds.

        Returns:
            LockLease: Active lease with lifecycle state and fencing token when acquisition succeeds.

        Raises:
            LockAcquisitionTimeout: If the lock is not acquired within the configured retries or the timeout ceiling.
            Exception: Re-raises unexpected exceptions encountered during acquisition.
        """
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        # Enforce the repo-wide 30-second maximum wait ceiling per GEMINI.md
        timeout_seconds = min(timeout_seconds, 30.0)

        self._emit(
            LockEvent(
                LockEventType.ACQUIRE_ATTEMPT,
                self.lock_name,
                self.holder_id,
            )
        )
        self._metric("lock_acquire_total")

        start_time = time()
        current_interval = retry_interval_seconds
        retries = 0

        while True:
            if (time() - start_time) >= timeout_seconds:
                self._handle_acquire_contention(start_time, retries, max_retries, timeout_seconds)
            try:
                res = self._attempt_lock_acquisition()
                if res.success:
                    self._fencing_token = res.fencing_token
                    self._set_state(LockLifecycleState.ACQUIRED)
                    self._emit(
                        LockEvent(
                            LockEventType.ACQUIRED,
                            self.lock_name,
                            self.holder_id,
                            metadata={"fencing_token": self._fencing_token},
                        )
                    )
                    self._metric("lock_acquired_total")
                    return LockLease(state=LockLifecycleState.ACQUIRED, fencing_token=self._fencing_token)
            except Exception as exc:
                self._handle_acquire_exception(exc, start_time, retries, max_retries, timeout_seconds)

            elapsed = self._handle_acquire_contention(start_time, retries, max_retries, timeout_seconds)

            # Deterministic exponential back-off bounded by the timeout ceiling
            sleep_duration = min(current_interval, timeout_seconds - elapsed)
            if sleep_duration > 0:
                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="lock_acquisition_retry",
                        message=f"Retrying lock acquisition for '{self.lock_name}' (elapsed: {elapsed:.2f}s)...",
                        metadata={"lock_name": self.lock_name, "elapsed": elapsed, "sleep": sleep_duration},
                    ),
                )
                sleep(sleep_duration)

            current_interval *= 2
            retries += 1

    def _handle_refresh_transient_error(
        self,
        attempt: int,
        max_retries: int,
        retry_delay_seconds: float,
        exc: Exception,
        start_time: float,
    ) -> bool:
        """
        Decide whether to retry a lock refresh after a transient error and emit observability signals.

        Emits a TRANSIENT_ERROR event on each invocation. If the retry budget is exhausted,
        marks the lock as lost, emits a FAILED event, and records failure and latency metrics.

        Parameters:
            attempt (int): Zero-based current retry attempt.
            max_retries (int): Maximum allowed retry attempts (zero or greater).
            retry_delay_seconds (float): Base delay in seconds used for exponential backoff.
            exc (Exception): The transient exception that triggered this handler.
            start_time (float): Timestamp (as returned by time()) when the refresh operation began;
                used to compute latency.

        Returns:
            bool: `True` if the caller should retry the refresh, `False` if no retries remain
                and the lock has been marked lost.
        """
        self._emit(
            LockEvent(
                LockEventType.TRANSIENT_ERROR,
                self.lock_name,
                self.holder_id,
                metadata={"error": type(exc).__name__},
            )
        )
        if attempt < max_retries:
            delay = retry_delay_seconds * (2**attempt)
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="lock_refresh_retry",
                    message=(
                        f"Lock refresh attempt {attempt + 1}/{max_retries + 1} "
                        f"failed ({type(exc).__name__}), retrying in {delay}s..."
                    ),
                    metadata={
                        "lock_name": self.lock_name,
                        "attempt": attempt + 1,
                        "max_attempts": max_retries + 1,
                        "error": type(exc).__name__,
                        "delay": delay,
                    },
                ),
            )
            sleep(delay)
            return True

        self._set_state(LockLifecycleState.LOST)
        self._emit(
            LockEvent(
                LockEventType.FAILED,
                self.lock_name,
                self.holder_id,
                metadata={"error": type(exc).__name__, "attempts": attempt + 1},
            )
        )
        self._metric("lock_refresh_failures")
        self._metric("lock_refresh_latency_seconds", {"status": "failed"}, value=time() - start_time)
        return False

    def _handle_refresh_unexpected_error(self, exc: Exception, start_time: float) -> bool:
        """Handle an unexpected exception raised during a refresh attempt.

        Handle an unexpected exception raised during a refresh attempt by marking the lock as lost,
        emitting observability events and metrics, and indicating the refresh should stop.

        Parameters:
            exc (Exception): The unexpected exception that occurred.
            start_time (float): Timestamp when the refresh attempt started, used to record latency.

        Returns:
            bool: `False` to indicate the refresh should not be retried.
        """
        self._emit(
            LockEvent(
                LockEventType.UNEXPECTED_ERROR,
                self.lock_name,
                self.holder_id,
                metadata={"error": type(exc).__name__},
            )
        )
        self._set_state(LockLifecycleState.LOST)
        self._metric("lock_errors_total")
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="lock_refresh_unexpected_error",
                message=(f"Unexpected error refreshing distributed lock '{self.lock_name}': {type(exc).__name__}"),
                metadata={"lock_name": self.lock_name, "error": type(exc).__name__},
            ),
        )
        self._metric("lock_refresh_latency_seconds", {"status": "error"}, value=time() - start_time)
        return False

    def refresh(self, *, max_retries: int = 2, retry_delay_seconds: float = 0.5) -> LockLease | bool:
        """
        Extend the current lock's TTL by attempting to refresh the lease.

        Parameters:
            max_retries (int): Number of additional attempts to retry on transient errors (must be >= 0).
            retry_delay_seconds (float): Base delay in seconds used for retry backoff between attempts (must be >= 0).

        Returns:
            LockLease: The renewed lease when the refresh succeeds.
            bool: `False` if the lock is contested or the refresh did not succeed.
        """
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be >= 0")

        start = time()
        for attempt in range(max_retries + 1):
            try:
                with session_scope(self.coordination_session_factory) as session:
                    repo = CoordinationLockRepository(session)
                    res = repo.refresh_lock(
                        lock_name=self.lock_name,
                        holder_id=self.holder_id,
                        ttl_seconds=self.ttl_seconds,
                    )
                    if res.success:
                        self._fencing_token = res.fencing_token
                        self._set_state(LockLifecycleState.REFRESHED)
                        self._emit(
                            LockEvent(
                                LockEventType.REFRESHED,
                                self.lock_name,
                                self.holder_id,
                                metadata={"attempt": attempt, "fencing_token": self._fencing_token},
                            )
                        )
                        self._metric("lock_refresh_total")
                        self._metric("lock_refresh_latency_seconds", {"status": "success"}, value=time() - start)
                        return LockLease(state=LockLifecycleState.REFRESHED, fencing_token=self._fencing_token)

                    self._set_state(LockLifecycleState.CONTENTED)
                    self._emit(
                        LockEvent(
                            LockEventType.CONTENTED,
                            self.lock_name,
                            self.holder_id,
                        )
                    )
                    self._metric("lock_contention_total")
                    self._metric("lock_refresh_latency_seconds", {"status": "contested"}, value=time() - start)
                    return False
            except (SQLAlchemyError, OSError) as exc:
                if self._handle_refresh_transient_error(attempt, max_retries, retry_delay_seconds, exc, start):
                    continue
                return False
            except Exception as exc:
                return self._handle_refresh_unexpected_error(exc, start)
        return False

    def release(self) -> None:
        """
        Release the lock and update its lifecycle state.

        Marks the lock as released on success and records the corresponding release event and metric.
        If release fails, records an unexpected error event and error metric, logs the failure,
        and suppresses the exception.
        """
        try:
            with session_scope(self.coordination_session_factory) as session:
                repo = CoordinationLockRepository(session)
                repo.release_lock(
                    lock_name=self.lock_name,
                    holder_id=self.holder_id,
                )
                self._set_state(LockLifecycleState.RELEASED)
                self._emit(
                    LockEvent(
                        LockEventType.RELEASED,
                        self.lock_name,
                        self.holder_id,
                    )
                )
                self._metric("lock_release_total")
                log_event(
                    logger,
                    logging.DEBUG,
                    ObservabilityEvent(
                        event="lock_released",
                        message=f"Released distributed lock '{self.lock_name}' for holder '{self.holder_id}'",
                        metadata={"lock_name": self.lock_name, "holder_id": self.holder_id},
                    ),
                )
        except Exception as exc:
            self._emit(
                LockEvent(
                    LockEventType.UNEXPECTED_ERROR,
                    self.lock_name,
                    self.holder_id,
                    metadata={"error": type(exc).__name__},
                )
            )
            self._metric("lock_errors_total")
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="lock_release_failed",
                    message=f"Failed to release distributed lock '{self.lock_name}': {type(exc).__name__}",
                    metadata={"lock_name": self.lock_name, "error": type(exc).__name__},
                ),
            )

    def _classify_lock_state(self, snapshot: LockStateSnapshot) -> LockState:
        """
        Determine the high-level lock state represented by a database snapshot.

        Parameters:
            snapshot (LockStateSnapshot): Snapshot indicating whether the lock row exists,
                whether it is currently valid, and its expiration timestamp.

        Returns:
            LockState: `LockState.VALID` if the snapshot exists and is valid; `LockState.EXPIRED`
                if the snapshot exists, is not valid, and `expires_at` is less than or equal
                to the current UTC time; `LockState.UNKNOWN` otherwise.
        """
        if not snapshot.exists:
            return LockState.UNKNOWN

        if not snapshot.valid:
            now = datetime.now(UTC)
            if snapshot.expires_at and snapshot.expires_at <= now:
                return LockState.EXPIRED
            return LockState.UNKNOWN

        return LockState.VALID

    def _handle_check_state_error(self, exc: Exception) -> LockState:
        """Handle exceptions raised during a lock state check.

        Classify and handle exceptions raised during a lock state check, update the internal
        lifecycle state, and emit observability events.

        Parameters:
                exc (Exception): The exception raised while checking the lock state.

        Returns:
                LockState: `LockState.LOST` when the exception indicates transient DB/connectivity
                issues (`SQLAlchemyError` or `OSError`). For other exceptions this method does
                not return; it sets the lifecycle state to `LOST`, emits an `UNEXPECTED_ERROR`
                event, and re-raises the original exception.
        """
        if isinstance(exc, (SQLAlchemyError, OSError)):
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="lock_state_check_db_connectivity_lost",
                    message=f"Lost database connectivity while checking lock '{self.lock_name}': {type(exc).__name__}",
                    metadata={"lock_name": self.lock_name, "error": type(exc).__name__},
                ),
            )
            self._set_state(LockLifecycleState.LOST)
            self._emit(
                LockEvent(
                    LockEventType.TRANSIENT_ERROR,
                    self.lock_name,
                    self.holder_id,
                    metadata={"error": type(exc).__name__},
                )
            )
            return LockState.LOST

        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="lock_state_check_unexpected_error",
                message=f"Unexpected error checking lock '{self.lock_name}' state ({type(exc).__name__}) - re-raising",
                metadata={"lock_name": self.lock_name, "error": type(exc).__name__},
            ),
        )
        self._set_state(LockLifecycleState.LOST)
        self._emit(
            LockEvent(
                LockEventType.UNEXPECTED_ERROR,
                self.lock_name,
                self.holder_id,
                metadata={"error": type(exc).__name__},
            )
        )
        raise exc

    def check_state(self) -> LockState:
        """
        Check the current state of this distributed lock.

        State Classification:
        - VALID: Lock exists, not expired, held by this holder_id
        - EXPIRED: Lock exists but TTL has passed
        - UNKNOWN: Lock doesn't exist OR held by different holder_id
        - LOST: Database connectivity failure during state check

        Returns:
            LockState: The current state (VALID, EXPIRED, UNKNOWN, LOST).
        """
        try:
            with session_scope(self.coordination_session_factory) as session:
                repo = CoordinationLockRepository(session)
                snapshot = repo.get_lock_state(
                    lock_name=self.lock_name,
                    holder_id=self.holder_id,
                )

                state = self._classify_lock_state(snapshot)

                self._emit(
                    LockEvent(
                        LockEventType.STATE_CHECK,
                        self.lock_name,
                        self.holder_id,
                        metadata={"state": state},
                    )
                )

                if state == LockState.VALID:
                    self._set_state(LockLifecycleState.ACQUIRED)
                else:
                    self._set_state(LockLifecycleState.LOST)

                return state
        except Exception as exc:
            return self._handle_check_state_error(exc)

    def __enter__(self) -> DistributedLock:
        """
        Enter the context by acquiring the distributed lock.

        Raises:
            RuntimeError: if the lock could not be acquired for this lock's name.

        Returns:
            DistributedLock: the acquired lock instance (`self`).
        """
        if not self.acquire():
            raise RuntimeError(f"Could not acquire distributed lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit point."""
        self.release()

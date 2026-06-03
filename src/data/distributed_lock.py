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

from src.data.repository import CoordinationLockRepository, session_scope
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

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
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class LockMetrics:
    """Abstract metrics interface (Prometheus, OpenTelemetry, etc.)."""

    def inc(self, metric: str, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        raise NotImplementedError

    def observe(self, metric: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a histogram/summary metric."""
        raise NotImplementedError


class LockLifecycleState(str, Enum):
    """Explicit lifecycle states of the coordination primitive state machine."""

    INITIAL = "initial"
    ACQUIRED = "acquired"
    REFRESHED = "refreshed"
    CONTENTED = "contented"
    LOST = "lost"
    RELEASED = "released"


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
        """
        Initialize the distributed lock coordination primitive.

        Args:
            session_factory: Factory for creating database sessions (backward-compatible).
            lock_name: Unique identifier for the lock.
            coordination_session_factory: Factory for creating primary-only coordination sessions.
            metrics: Pluggable metrics interface (e.g. Prometheus, OTEL).
            event_sink: Callable event sink for immutable structured logs/audit trail.
            holder_id: Unique identifier for the current process/instance.
            ttl_seconds: Time-to-live for the lock in seconds.
        """
        resolved_factory = coordination_session_factory or session_factory
        if resolved_factory is None:
            raise TypeError(
                "__init__() missing 1 required positional/keyword argument: "
                "'coordination_session_factory' or 'session_factory'"
            )
        if lock_name is None:
            raise TypeError("__init__() missing 1 required positional argument: 'lock_name'")

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
        """Emit a structured coordination lifecycle event."""
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
        """Record a counter increment or observation metric if metrics interface is provided."""
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
        """Transition the internal lifecycle state machine state."""
        self._state = state

    @property
    def state(self) -> LockLifecycleState:
        """Return the current internal lifecycle state of the lock."""
        return self._state

    def acquire(self, *, retry_interval_seconds: float = 1.0, max_retries: int = 0) -> LockLease | bool:
        """Acquire the distributed lock with optional retries."""
        self._emit(
            LockEvent(
                LockEventType.ACQUIRE_ATTEMPT,
                self.lock_name,
                self.holder_id,
            )
        )
        self._metric("lock_acquire_total")
        retries = 0
        while True:
            try:
                with session_scope(self.coordination_session_factory) as session:
                    repo = CoordinationLockRepository(session)
                    res = repo.acquire_lock(
                        lock_name=self.lock_name,
                        holder_id=self.holder_id,
                        ttl_seconds=self.ttl_seconds,
                    )
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
                self._emit(
                    LockEvent(
                        LockEventType.UNEXPECTED_ERROR,
                        self.lock_name,
                        self.holder_id,
                        metadata={"error": type(exc).__name__},
                    )
                )
                self._metric("lock_errors_total")
                if retries >= max_retries:
                    self._set_state(LockLifecycleState.LOST)
                    raise

            if retries >= max_retries:
                self._set_state(LockLifecycleState.CONTENTED)
                self._emit(
                    LockEvent(
                        LockEventType.CONTENTED,
                        self.lock_name,
                        self.holder_id,
                    )
                )
                self._metric("lock_contention_total")
                return False

            retries += 1
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="lock_acquisition_retry",
                    message=f"Retrying lock acquisition for '{self.lock_name}' ({retries}/{max_retries})...",
                    metadata={"lock_name": self.lock_name, "retry": retries, "max_retries": max_retries},
                ),
            )
            sleep(retry_interval_seconds)

    def refresh(self, *, max_retries: int = 2, retry_delay_seconds: float = 0.5) -> LockLease | bool:
        """
        Refresh the distributed lock to extend its TTL.

        Retries on transient DB errors to handle brief network blips.
        Uses exponential backoff delays on retries.

        Args:
            max_retries: Number of retry attempts on transient errors (default 2).
            retry_delay_seconds: Base delay between retries (default 0.5s).

        Returns:
            LockLease on success, False if held by another holder.
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
                    continue
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
                self._metric("lock_refresh_latency_seconds", {"status": "failed"}, value=time() - start)
                return False
            except Exception as exc:
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
                        message=(
                            f"Unexpected error refreshing distributed lock '{self.lock_name}': "
                            f"{type(exc).__name__}"
                        ),
                        metadata={"lock_name": self.lock_name, "error": type(exc).__name__},
                    ),
                )
                self._metric("lock_refresh_latency_seconds", {"status": "error"}, value=time() - start)
                return False
        return False

    def release(self) -> None:
        """Release the distributed lock."""
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

    def check_state(self) -> LockState:
        """
        Check the current state of this distributed lock.

        State Classification:
        - VALID: Lock exists, not expired, held by this holder_id
        - EXPIRED: Lock exists but TTL has passed
        - UNKNOWN: Lock doesn't exist OR held by different holder_id
        - LOST: Database connectivity failure during state check

        LOST vs UNKNOWN Distinction:
        - UNKNOWN = deterministic state (no lock record or wrong owner)
          May allow reacquisition if lock truly doesn't exist
        - LOST = transient failure (cannot determine state due to DB error)
          Must not proceed - cannot safely determine ownership

        Recovery Implications:
        - UNKNOWN: RecoveryGate may allow reacquisition or RESET recovery
        - LOST: RecoveryGate blocks execution (UNSAFE action)
        - EXPIRED: Allows reacquisition by any holder
        - VALID: Normal operation continues

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

                if not snapshot.exists:
                    state = LockState.UNKNOWN
                elif not snapshot.valid:
                    now = datetime.now(timezone.utc)
                    if snapshot.expires_at and snapshot.expires_at <= now:
                        state = LockState.EXPIRED
                    else:
                        state = LockState.UNKNOWN
                else:
                    state = LockState.VALID

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
        except (SQLAlchemyError, OSError) as exc:
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
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="lock_state_check_unexpected_error",
                    message=(
                        f"Unexpected error checking lock '{self.lock_name}' state "
                        f"({type(exc).__name__}) - re-raising"
                    ),
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
            raise

    def __enter__(self) -> DistributedLock:
        """Context manager entry point."""
        if not self.acquire():
            raise RuntimeError(f"Could not acquire distributed lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit point."""
        self.release()

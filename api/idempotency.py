"""Thread-safe, TTL-bounded HTTP Idempotency-Key store for mutating API endpoints."""

from __future__ import annotations

import hashlib
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

UTC = timezone.utc

MAX_IDEMPOTENCY_KEY_LENGTH = 128
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:@/-]{1,128}$")


class InvalidIdempotencyKeyError(ValueError):
    """Raised when an Idempotency-Key header is malformed or exceeds length bounds."""


class IdempotencyConflictError(RuntimeError):
    """Raised when an Idempotency-Key is reused with different parameters or while in progress."""


@dataclass(frozen=True)
class _IdempotencyEntry:
    fingerprint: str
    in_progress: bool
    expires_at: datetime
    response: Any = None


def normalize_idempotency_key(raw_key: str | None) -> str | None:
    """Validate and normalize an optional Idempotency-Key header value."""
    if raw_key is None:
        return None
    cleaned = raw_key.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_IDEMPOTENCY_KEY_LENGTH or not _IDEMPOTENCY_KEY_PATTERN.fullmatch(cleaned):
        raise InvalidIdempotencyKeyError("Idempotency-Key must be 1-128 characters using only [A-Za-z0-9._:@/-].")
    return cleaned


def fingerprint_request(*parts: str) -> str:
    """Build a deterministic SHA-256 fingerprint for idempotency conflict detection."""
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("utf-8"))
        hasher.update(b"\x1f")
    return hasher.hexdigest()


class IdempotencyStore:
    """Thread-safe TTL-bounded in-memory idempotency store with automatic expiry pruning."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 3600.0,
        max_entries: int = 1024,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize the idempotency store with bounded TTL and capacity."""
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_entries = max_entries
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = threading.RLock()
        self._entries: dict[tuple[str, str, str], _IdempotencyEntry] = {}

    def _prune_locked(self, now: datetime) -> None:
        expired = [k for k, entry in self._entries.items() if entry.expires_at <= now]
        for k in expired:
            del self._entries[k]
        while len(self._entries) >= self._max_entries:
            oldest_key = next(iter(self._entries))
            del self._entries[oldest_key]

    def begin(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        fingerprint: str,
    ) -> tuple[bool, Any]:
        """Begin or replay an idempotent operation.

        Returns ``(is_replay, cached_response)``. Raises ``IdempotencyConflictError`` if the
        key is currently in progress or was previously used with a different fingerprint.
        """
        now = self._clock()
        composite = (scope, actor, key)
        from .metrics import record_rebuild_idempotency

        with self._lock:
            self._prune_locked(now)
            existing = self._entries.get(composite)
            if existing is not None:
                if existing.fingerprint != fingerprint:
                    record_rebuild_idempotency("conflict")
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used with different request parameters."
                    )
                if existing.in_progress:
                    record_rebuild_idempotency("conflict")
                    raise IdempotencyConflictError("A request with this Idempotency-Key is already in progress.")
                record_rebuild_idempotency("hit")
                return True, existing.response

            self._entries[composite] = _IdempotencyEntry(
                fingerprint=fingerprint,
                in_progress=True,
                expires_at=now + self._ttl,
                response=None,
            )
            record_rebuild_idempotency("miss")
            return False, None

    def complete(
        self,
        *,
        scope: str,
        actor: str,
        key: str,
        fingerprint: str,
        response: Any,
    ) -> None:
        """Record a completed response for replay within the TTL window."""
        now = self._clock()
        composite = (scope, actor, key)
        with self._lock:
            self._prune_locked(now)
            self._entries[composite] = _IdempotencyEntry(
                fingerprint=fingerprint,
                in_progress=False,
                expires_at=now + self._ttl,
                response=response,
            )

    def abort(self, *, scope: str, actor: str, key: str) -> None:
        """Release an in-progress reservation when the underlying operation fails."""
        composite = (scope, actor, key)
        with self._lock:
            existing = self._entries.get(composite)
            if existing is not None and existing.in_progress:
                del self._entries[composite]

    def clear(self) -> None:
        """Clear all stored entries (primarily for tests)."""
        with self._lock:
            self._entries.clear()


rebuild_idempotency_store = IdempotencyStore()

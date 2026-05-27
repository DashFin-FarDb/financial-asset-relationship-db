"""Database-backed distributed lock for rebuild coordination."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from enum import Enum
from time import sleep

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.repository import AssetGraphRepository, session_scope

logger = logging.getLogger(__name__)


class LockState(str, Enum):
    """Explicit states of a distributed lock."""

    VALID = "valid"
    EXPIRED = "expired"
    UNKNOWN = "unknown"
    LOST = "lost"


class DistributedLock:
    """A distributed lock backed by a database table."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        lock_name: str,
        *,
        holder_id: str | None = None,
        ttl_seconds: int = 300,
    ) -> None:
        """
        Initialize the distributed lock.

        Args:
            session_factory: Factory for creating database sessions.
            lock_name: Unique identifier for the lock.
            holder_id: Unique identifier for the current process/instance.
            ttl_seconds: Time-to-live for the lock in seconds.
        """
        self.session_factory = session_factory
        self.lock_name = lock_name
        self.holder_id = holder_id or str(uuid.uuid4())
        self.ttl_seconds = ttl_seconds

    def acquire(self, *, retry_interval_seconds: float = 1.0, max_retries: int = 0) -> bool:
        """
        Acquire the distributed lock with optional retries.
        """
        retries = 0
        while True:
            try:
                with session_scope(self.session_factory) as session:
                    repo = AssetGraphRepository(session)
                    if repo.try_acquire_distributed_lock(
                        lock_name=self.lock_name,
                        holder_id=self.holder_id,
                        ttl_seconds=self.ttl_seconds,
                    ):
                        logger.debug(
                            "Acquired distributed lock '%s' for holder '%s'",
                            self.lock_name,
                            self.holder_id,
                        )
                        return True
            except Exception:
                logger.exception(
                    "Failed to acquire distributed lock '%s'",
                    self.lock_name,
                )
                # If we've hit the retry limit, propagate the exception
                if retries >= max_retries:
                    raise

            # Check if we should stop retrying if the lock was simply unavailable
            if retries >= max_retries:
                break

            retries += 1
            logger.info(
                "Retrying lock acquisition for '%s' (%d/%d)...",
                self.lock_name,
                retries,
                max_retries,
            )
            sleep(retry_interval_seconds)

        return False

    def refresh(
        self,
        *,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.5,
    ) -> bool:
        """
        Refresh the distributed lock to extend its TTL.
    
        Retries on transient DB errors to handle brief network blips.
    
        Args:
            max_retries:
                Number of retry attempts on transient errors (default 2).
            retry_delay_seconds:
                Delay between retries (default 0.5s).
    
        Returns:
            True if lock was refreshed, False if held by another holder.
        """
    
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
    
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be >= 0")
    
        for attempt in range(max_retries + 1):
            try:
                with session_scope(self.session_factory) as session:
                    repo = AssetGraphRepository(session)
    
                    if repo.try_acquire_distributed_lock(
                        lock_name=self.lock_name,
                        holder_id=self.holder_id,
                        ttl_seconds=self.ttl_seconds,
                    ):
                        logger.debug(
                            "Refreshed distributed lock '%s' for holder '%s'",
                            self.lock_name,
                            self.holder_id,
                        )
                        return True
    
                    # Lock held by another holder - don't retry
                    logger.warning(
                        "Failed to refresh distributed lock '%s' "
                        "(taken by another holder)",
                        self.lock_name,
                    )
                    return False
    
            except (SQLAlchemyError, OSError) as exc:
                # Transient DB/network error - retry if attempts remain
                if attempt < max_retries:
                    logger.warning(
                        "Lock refresh attempt %d/%d failed for lock '%s' "
                        "holder '%s': %s. Retrying in %ss...",
                        attempt + 1,
                        max_retries + 1,
                        self.lock_name,
                        self.holder_id,
                        type(exc).__name__,
                        retry_delay_seconds,
                    )
    
                    sleep(retry_delay_seconds)
                    continue
    
                # Max retries exhausted
                logger.warning(
                    "Lock refresh failed after %d attempts for lock '%s' "
                    "holder '%s': %s",
                    max_retries + 1,
                    self.lock_name,
                    self.holder_id,
                    type(exc).__name__,
                )
                return False
    
            except Exception:
                logger.exception(
                    "Unexpected error refreshing distributed lock '%s'",
                    self.lock_name,
                )
                raise

    def release(self) -> None:
        """Release the distributed lock."""
        try:
            with session_scope(self.session_factory) as session:
                repo = AssetGraphRepository(session)
                repo.release_distributed_lock(
                    lock_name=self.lock_name,
                    holder_id=self.holder_id,
                )
                logger.debug(
                    "Released distributed lock '%s' for holder '%s'",
                    self.lock_name,
                    self.holder_id,
                )
        except Exception:
            logger.exception(
                "Failed to release distributed lock '%s'",
                self.lock_name,
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
            with session_scope(self.session_factory) as session:
                repo = AssetGraphRepository(session)
                return repo.check_distributed_lock_state(
                    lock_name=self.lock_name,
                    holder_id=self.holder_id,
                )
        except (SQLAlchemyError, OSError) as exc:
            # DB connectivity failure during lock state check (SQLAlchemy/DBAPI and OS-layer I/O)
            # Use bounded logging to prevent DSN/credential leakage in tracebacks
            logger.warning(
                "Lost database connectivity while checking lock '%s': %s",
                self.lock_name,
                type(exc).__name__,
            )
            return LockState.LOST
        except Exception as exc:
            # Unexpected error - this indicates a programming bug, not connectivity loss
            # Re-raise to surface the issue rather than masking it as LOST state
            logger.error(
                "Unexpected error checking lock '%s' state (%s) - re-raising",
                self.lock_name,
                type(exc).__name__,
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

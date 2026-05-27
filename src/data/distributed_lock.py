"""Database-backed distributed lock for rebuild coordination."""

from __future__ import annotations

import logging
import uuid
import random
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


class LockRefreshResult(str, Enum):
    """
    Explicit outcomes of a refresh operation.

    This avoids overloading boolean return values with multiple meanings.
    """

    REFRESHED = "refreshed"
    CONTENTED = "contented"  # lock held by another holder
    FAILED = "failed"        # retry exhaustion or transient failure


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
        self.session_factory = session_factory
        self.lock_name = lock_name
        self.holder_id = holder_id or str(uuid.uuid4())
        self.ttl_seconds = ttl_seconds

    # -------------------------
    # Acquire
    # -------------------------

    def acquire(self, *, retry_interval_seconds: float = 1.0, max_retries: int = 0) -> bool:
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
                if retries >= max_retries:
                    raise

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

    # -------------------------
    # Refresh
    # -------------------------

    def refresh(
        self,
        *,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.5,
    ) -> LockRefreshResult:
        """
        Refresh the distributed lock to extend its TTL.

        Returns:
            LockRefreshResult.REFRESHED:
                lock successfully refreshed

            LockRefreshResult.CONTENTED:
                lock is held by another holder (expected contention)

            LockRefreshResult.FAILED:
                retry exhaustion or transient failure
        """

        if not isinstance(max_retries, int):
            raise TypeError("max_retries must be an int")

        if not isinstance(retry_delay_seconds, (int, float)):
            raise TypeError("retry_delay_seconds must be a number")

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
                        return LockRefreshResult.REFRESHED

                    logger.debug(
                        "Lock refresh not applied (contention) lock='%s'",
                        self.lock_name,
                    )
                    return LockRefreshResult.CONTENTED

            except (SQLAlchemyError, OSError) as exc:
                if attempt < max_retries:
                    delay = retry_delay_seconds * (2 ** attempt)
                    jitter = random.uniform(0, delay * 0.1)

                    logger.warning(
                        "Lock refresh attempt %d/%d failed lock='%s' holder='%s' error=%s retrying_in=%.2fs",
                        attempt + 1,
                        max_retries + 1,
                        self.lock_name,
                        self.holder_id,
                        type(exc).__name__,
                        delay + jitter,
                    )

                    sleep(delay + jitter)
                    continue

                logger.warning(
                    "Lock refresh failed after %d attempts lock='%s' holder='%s' error=%s",
                    max_retries + 1,
                    self.lock_name,
                    self.holder_id,
                    type(exc).__name__,
                )
                return LockRefreshResult.FAILED

            except Exception:
                logger.exception(
                    "Unexpected error refreshing distributed lock '%s'",
                    self.lock_name,
                )
                return LockRefreshResult.FAILED

    # -------------------------
    # Release
    # -------------------------

    def release(self) -> None:
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

    # -------------------------
    # State
    # -------------------------

    def check_state(self) -> LockState:
        try:
            with session_scope(self.session_factory) as session:
                repo = AssetGraphRepository(session)
                return repo.check_distributed_lock_state(
                    lock_name=self.lock_name,
                    holder_id=self.holder_id,
                )

        except (SQLAlchemyError, OSError) as exc:
            logger.warning(
                "Database connectivity failure checking lock '%s': %s",
                self.lock_name,
                type(exc).__name__,
            )
            return LockState.LOST

        except Exception:
            logger.exception(
                "Unexpected error checking lock state '%s'",
                self.lock_name,
            )
            raise

    # -------------------------
    # Context manager
    # -------------------------

    def __enter__(self) -> DistributedLock:
        if not self.acquire():
            raise RuntimeError(f"Could not acquire distributed lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

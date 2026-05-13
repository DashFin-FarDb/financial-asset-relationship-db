"""Database-backed distributed lock for rebuild coordination."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from time import sleep

from sqlalchemy.orm import Session

from src.data.repository import AssetGraphRepository, session_scope

logger = logging.getLogger(__name__)


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
            except Exception as exc:
                logger.error(
                    "Failed to acquire distributed lock '%s': %s",
                    self.lock_name,
                    type(exc).__name__,
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
        except Exception as exc:
            logger.error(
                "Failed to release distributed lock '%s': %s",
                self.lock_name,
                type(exc).__name__,
            )

    def __enter__(self) -> DistributedLock:
        """Context manager entry point."""
        if not self.acquire():
            raise RuntimeError(f"Could not acquire distributed lock: {self.lock_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit point."""
        self.release()

"""Unit tests for strictly monotonic fencing tokens under clock skew and atomic CAS lock renewal."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import sessionmaker

from src.data.database import create_engine_from_url
from src.data.db_models import DistributedLockORM
from src.data.repository import CoordinationLockRepository

UTC = timezone.utc


def _make_session_factory():
    engine = create_engine_from_url("sqlite:///:memory:")
    DistributedLockORM.__table__.create(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_monotonic_fencing_token_advances_under_backward_clock_skew() -> None:
    """Even if a contender's wall clock lags behind the previous lock holder, fencing_token strictly increases."""
    session_factory = _make_session_factory()
    with session_factory() as session:
        repo = CoordinationLockRepository(session)
        first = repo.acquire_lock(lock_name="rebuild", holder_id="host-a", ttl_seconds=60)
        session.commit()
        assert first.success

        # Simulate host-a having a clock 60s in the future and lock already expired
        future_updated = datetime.now(UTC) + timedelta(seconds=60)
        past_expiry = datetime.now(UTC) - timedelta(seconds=5)
        session.execute(
            update(DistributedLockORM)
            .where(DistributedLockORM.lock_name == "rebuild")
            .values(updated_at=future_updated, expires_at=past_expiry)
        )
        session.commit()

        prev_token = repo._fencing_token_from_timestamp(future_updated)
        takeover = repo.acquire_lock(lock_name="rebuild", holder_id="host-b", ttl_seconds=60)
        session.commit()
        assert takeover.success
        assert takeover.fencing_token > prev_token


def test_renew_owned_lock_uses_atomic_cas_on_fencing_token() -> None:
    """renew_owned_lock succeeds with the exact fencing_token, advances it, and rejects stale tokens atomically."""
    session_factory = _make_session_factory()
    with session_factory() as session:
        repo = CoordinationLockRepository(session)
        acq = repo.acquire_lock(lock_name="rebuild", holder_id="host-a", ttl_seconds=60)
        session.commit()
        assert acq.success

        # Stale fencing token must fail atomically
        assert not repo.renew_owned_lock(
            lock_name="rebuild",
            holder_id="host-a",
            ttl_seconds=60,
            expected_fencing_token=acq.fencing_token - 1,
        )

        # Exact fencing token succeeds and advances the stored fencing token
        assert repo.renew_owned_lock(
            lock_name="rebuild",
            holder_id="host-a",
            ttl_seconds=60,
            expected_fencing_token=acq.fencing_token,
        )
        session.commit()

        after = repo.get_lock_state(lock_name="rebuild", holder_id="host-a")
        assert after.valid
        assert after.fencing_token is not None
        assert after.fencing_token > acq.fencing_token

        # Replaying the old fencing token after renewal must fail
        assert not repo.renew_owned_lock(
            lock_name="rebuild",
            holder_id="host-a",
            ttl_seconds=60,
            expected_fencing_token=acq.fencing_token,
        )

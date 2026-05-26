"""Unit tests for AssetGraphRepository distributed lock and latest job methods."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from src.data.database import create_session_factory, init_db
from src.data.db_models import DistributedLockORM
from src.data.distributed_lock import DistributedLock, LockState
from src.data.repository import AssetGraphRepository


@pytest.fixture
def repository_factory(tmp_path):
    """Factory for AssetGraphRepository with fresh SQLite DB."""
    db_path = tmp_path / "test_distributed_lock.db"
    engine = create_engine(f"sqlite:///{db_path}")
    init_db(engine)
    factory = create_session_factory(engine)
    sessions = []

    def make_repository():
        session = factory()
        sessions.append(session)
        return AssetGraphRepository(session)

    yield make_repository

    for session in sessions:
        session.close()
    engine.dispose()


@pytest.mark.unit
class TestDistributedLockRepository:
    """Test cases for distributed lock repository methods."""

    def test_try_acquire_distributed_lock_new(self, repository_factory):
        """Test acquiring a new lock."""
        repo = repository_factory()
        acquired = repo.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder1",
            ttl_seconds=60,
        )
        assert acquired is True
        repo.session.commit()

        # Verify persisted state
        reader = repository_factory()
        from src.data.db_models import DistributedLockORM

        lock = reader.session.get(DistributedLockORM, "test_lock")
        assert lock is not None
        assert lock.holder_id == "holder1"

        lock_expires_at = lock.expires_at
        if lock_expires_at.tzinfo is None:
            lock_expires_at = lock_expires_at.replace(tzinfo=timezone.utc)
        assert lock_expires_at > datetime.now(timezone.utc)

    def test_try_acquire_distributed_lock_held_by_other(self, repository_factory):
        """Test failing to acquire a lock held by another holder."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder1",
            ttl_seconds=60,
        )
        repo.session.commit()

        # Try to acquire with other holder
        repo2 = repository_factory()
        acquired = repo2.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder2",
            ttl_seconds=60,
        )
        assert acquired is False

    def test_try_acquire_distributed_lock_refresh(self, repository_factory):
        """Test refreshing a lock held by the same holder."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder1",
            ttl_seconds=60,
        )
        repo.session.commit()

        # Refresh
        acquired = repo.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder1",
            ttl_seconds=120,
        )
        assert acquired is True
        repo.session.commit()

        reader = repository_factory()
        from src.data.db_models import DistributedLockORM

        lock = reader.session.get(DistributedLockORM, "test_lock")

        lock_expires_at = lock.expires_at
        if lock_expires_at.tzinfo is None:
            lock_expires_at = lock_expires_at.replace(tzinfo=timezone.utc)
        assert lock_expires_at > datetime.now(timezone.utc) + timedelta(seconds=60)

    def test_try_acquire_distributed_lock_takeover_expired(self, repository_factory):
        """Test taking over an expired lock."""
        repo = repository_factory()
        # Create expired lock manually or by setting very short TTL and waiting?
        # Better to set expires_at in the past via DB.
        from src.data.db_models import DistributedLockORM

        now = datetime.now(timezone.utc)
        expired_lock = DistributedLockORM(
            lock_name="test_lock",
            holder_id="holder1",
            expires_at=now - timedelta(seconds=1),
            created_at=now - timedelta(seconds=60),
            updated_at=now - timedelta(seconds=60),
        )
        repo.session.add(expired_lock)
        repo.session.commit()

        # Take over
        repo2 = repository_factory()
        acquired = repo2.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder2",
            ttl_seconds=60,
        )
        assert acquired is True
        repo2.session.commit()

        reader = repository_factory()
        lock = reader.session.get(DistributedLockORM, "test_lock")
        assert lock.holder_id == "holder2"

        lock_expires_at = lock.expires_at
        if lock_expires_at.tzinfo is None:
            lock_expires_at = lock_expires_at.replace(tzinfo=timezone.utc)
        assert lock_expires_at > now

    def test_release_distributed_lock(self, repository_factory):
        """Test releasing a lock."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder1",
            ttl_seconds=60,
        )
        repo.session.commit()

        repo.release_distributed_lock(lock_name="test_lock", holder_id="holder1")
        repo.session.commit()

        reader = repository_factory()
        from src.data.db_models import DistributedLockORM

        lock = reader.session.get(DistributedLockORM, "test_lock")
        assert lock is None

    def test_release_distributed_lock_not_owner(self, repository_factory):
        """Test that releasing a lock held by another holder does nothing."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock",
            holder_id="holder1",
            ttl_seconds=60,
        )
        repo.session.commit()

        # Try to release with other holder id
        repo.release_distributed_lock(lock_name="test_lock", holder_id="holder2")
        repo.session.commit()

        reader = repository_factory()
        from src.data.db_models import DistributedLockORM

        lock = reader.session.get(DistributedLockORM, "test_lock")
        assert lock is not None
        assert lock.holder_id == "holder1"

    def test_check_distributed_lock_state_returns_unknown_when_missing(self, repository_factory):
        """Missing lock rows should be reported as UNKNOWN."""
        repo = repository_factory()
        assert repo.check_distributed_lock_state(lock_name="missing", holder_id="holder1") == LockState.UNKNOWN

    def test_check_distributed_lock_state_returns_expired_for_stale_lock(self, repository_factory):
        """Expired lock rows should be classified as EXPIRED."""
        repo = repository_factory()

        now = datetime.now(timezone.utc)
        repo.session.add(
            DistributedLockORM(
                lock_name="test_lock",
                holder_id="holder1",
                expires_at=now - timedelta(seconds=1),
                created_at=now - timedelta(seconds=60),
                updated_at=now - timedelta(seconds=60),
            )
        )
        repo.session.commit()

        reader = repository_factory()
        assert reader.check_distributed_lock_state(lock_name="test_lock", holder_id="holder1") == LockState.EXPIRED

    def test_check_distributed_lock_state_returns_valid_for_current_holder(self, repository_factory):
        """Current holder with unexpired lock should be VALID."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=60)
        repo.session.commit()

        reader = repository_factory()
        assert reader.check_distributed_lock_state(lock_name="test_lock", holder_id="holder1") == LockState.VALID

    def test_check_distributed_lock_state_returns_unknown_for_other_holder(self, repository_factory):
        """Different holder with unexpired lock should be UNKNOWN."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=60)
        repo.session.commit()

        reader = repository_factory()
        assert reader.check_distributed_lock_state(lock_name="test_lock", holder_id="holder2") == LockState.UNKNOWN


@pytest.mark.unit
class TestLatestRebuildJobRepository:
    """Test cases for get_latest_successful_rebuild_job."""

    def test_get_latest_successful_rebuild_job_empty(self, repository_factory):
        """Test retrieving latest job when none exist."""
        repo = repository_factory()
        job = repo.get_latest_successful_rebuild_job()
        assert job is None

    def test_get_latest_successful_rebuild_job(self, repository_factory):
        """Test retrieving the most recent successful job."""
        repo = repository_factory()
        from src.data.db_models import RebuildJobORM

        # 1. Old successful job
        id1 = repo.create_rebuild_job(requested_by="user1")
        repo.mark_rebuild_job_running(id1)
        repo.mark_rebuild_job_succeeded(id1, node_count=1, edge_count=1, duration_ms=1)

        # Manually adjust completed_at for id1 to be older
        job1 = repo.session.get(RebuildJobORM, id1)
        job1.completed_at = datetime.now(timezone.utc) - timedelta(hours=1)
        repo.session.commit()

        # 2. Newer failed job
        id2 = repo.create_rebuild_job(requested_by="user2")
        repo.mark_rebuild_job_running(id2)
        repo.mark_rebuild_job_failed(id2, failure_category="err", failure_message="err", duration_ms=1)
        repo.session.commit()

        # 3. Newest successful job
        id3 = repo.create_rebuild_job(requested_by="user3")
        repo.mark_rebuild_job_running(id3)
        repo.mark_rebuild_job_succeeded(id3, node_count=3, edge_count=3, duration_ms=3)
        repo.session.commit()

        reader = repository_factory()
        latest = reader.get_latest_successful_rebuild_job()
        assert latest is not None
        assert latest.job_id == id3
        assert latest.requested_by == "user3"


@pytest.mark.unit
class TestDistributedLockRetryLogic:
    """Test cases for distributed lock refresh retry logic."""

    def test_refresh_retries_on_transient_db_error(self, monkeypatch, repository_factory):
        """Lock refresh should retry on transient SQLAlchemyError."""
        call_count = 0

        def flaky_try_acquire(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise SQLAlchemyError("connection timeout")
            return True

        # Create a lock with a real session factory
        repo = repository_factory()
        session_factory = lambda: repo.session
        lock = DistributedLock(session_factory, "test_lock", ttl_seconds=60)

        # Patch the repository method
        monkeypatch.setattr(
            AssetGraphRepository,
            "try_acquire_distributed_lock",
            flaky_try_acquire,
        )

        assert lock.refresh(max_retries=2, retry_delay_seconds=0.01) is True
        assert call_count == 3  # Initial + 2 retries

    def test_refresh_does_not_retry_on_lock_conflict(self, monkeypatch, repository_factory):
        """Lock refresh should not retry when lock is held by another holder."""
        call_count = 0

        def try_acquire_returns_false(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return False

        repo = repository_factory()
        session_factory = lambda: repo.session
        lock = DistributedLock(session_factory, "test_lock", ttl_seconds=60)

        monkeypatch.setattr(
            AssetGraphRepository,
            "try_acquire_distributed_lock",
            try_acquire_returns_false,
        )

        assert lock.refresh(max_retries=2) is False
        assert call_count == 1  # No retries on lock conflict

    def test_refresh_exhausts_retries_on_persistent_error(self, monkeypatch, repository_factory):
        """Lock refresh should return False after exhausting retries."""

        def always_fails(*args, **kwargs):
            raise SQLAlchemyError("persistent connection error")

        repo = repository_factory()
        session_factory = lambda: repo.session
        lock = DistributedLock(session_factory, "test_lock", ttl_seconds=60)

        monkeypatch.setattr(
            AssetGraphRepository,
            "try_acquire_distributed_lock",
            always_fails,
        )

        assert lock.refresh(max_retries=2, retry_delay_seconds=0.01) is False

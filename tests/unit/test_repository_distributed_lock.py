"""Unit tests for AssetGraphRepository distributed lock and latest job methods."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from src.data.database import create_session_factory, init_db
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

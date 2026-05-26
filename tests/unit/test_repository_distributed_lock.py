"""Unit tests for AssetGraphRepository distributed lock and latest job methods."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from src.data.database import create_session_factory, init_db
from src.data.db_models import DistributedLockORM, RebuildJobORM
from src.data.distributed_lock import DistributedLock, LockState
from src.data.repository import AssetGraphRepository


def _ensure_utc(dt: datetime) -> datetime:
    """Helper to ensure datetime is UTC aware, preventing duplicate timezone logic."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


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
            lock_name="test_lock", holder_id="holder1", ttl_seconds=60
        )
        assert acquired is True
        repo.session.commit()

        # Verify persisted state
        reader = repository_factory()
        lock = reader.session.get(DistributedLockORM, "test_lock")
        
        assert lock is not None
        assert lock.holder_id == "holder1"
        assert _ensure_utc(lock.expires_at) > datetime.now(timezone.utc)

    def test_try_acquire_distributed_lock_held_by_other(self, repository_factory):
        """Test failing to acquire a lock held by another holder."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock", holder_id="holder1", ttl_seconds=60
        )
        repo.session.commit()

        # Try to acquire with other holder
        repo2 = repository_factory()
        acquired = repo2.try_acquire_distributed_lock(
            lock_name="test_lock", holder_id="holder2", ttl_seconds=60
        )
        assert acquired is False

    def test_try_acquire_distributed_lock_refresh(self, repository_factory):
        """Test refreshing a lock held by the same holder."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock", holder_id="holder1", ttl_seconds=60
        )
        repo.session.commit()

        # Refresh
        acquired = repo.try_acquire_distributed_lock(
            lock_name="test_lock", holder_id="holder1", ttl_seconds=120
        )
        assert acquired is True
        repo.session.commit()

        reader = repository_factory()
        lock = reader.session.get(DistributedLockORM, "test_lock")
        
        expected_min_expiry = datetime.now(timezone.utc) + timedelta(seconds=60)
        assert _ensure_utc(lock.expires_at) > expected_min_expiry

    def test_try_acquire_distributed_lock_takeover_expired(self, repository_factory):
        """Test taking over an expired lock."""
        repo = repository_factory()
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
            lock_name="test_lock", holder_id="holder2", ttl_seconds=60
        )
        assert acquired is True
        repo2.session.commit()

        reader = repository_factory()
        lock = reader.session.get(DistributedLockORM, "test_lock")
        
        assert lock.holder_id == "holder2"
        assert _ensure_utc(lock.expires_at) > now

    def test_release_distributed_lock(self, repository_factory):
        """Test releasing a lock."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock", holder_id="holder1", ttl_seconds=60
        )
        repo.session.commit()

        repo.release_distributed_lock(lock_name="test_lock", holder_id="holder1")
        repo.session.commit()

        reader = repository_factory()
        lock = reader.session.get(DistributedLockORM, "test_lock")
        assert lock is None

    def test_release_distributed_lock_not_owner(self, repository_factory):
        """Test that releasing a lock held by another holder does nothing."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(
            lock_name="test_lock", holder_id="holder1", ttl_seconds=60
        )
        repo.session.commit()

        # Try to release with other holder id
        repo.release_distributed_lock(lock_name="test_lock", holder_id="holder2")
        repo.session.commit()

        reader = repository_factory()
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
        assert repo.get_latest_successful_rebuild_job() is None

    def test_get_latest_successful_rebuild_job(self, repository_factory):
        """Test retrieving the most recent successful job."""
        repo = repository_factory()

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

    @pytest.fixture
    def lock_setup(self, repository_factory):
        """Provides a factory-conformant session supplier and lock instance, fixing previous lambda bypass."""
        repo = repository_factory()
        
        def bound_session_factory():
            """Conforms directly to the repository state-isolation lifecycle contract."""
            return repo.session
            
        return DistributedLock(bound_session_factory, "test_lock", ttl_seconds=60)

    def test_refresh_retries_on_transient_db_error(self, monkeypatch, lock_setup):
        """Lock refresh should retry on transient SQLAlchemyError."""
        mock_try_acquire = MagicMock(side_effect=[
            SQLAlchemyError("connection timeout"),
            SQLAlchemyError("connection timeout"),
            True
        ])
        monkeypatch.setattr(AssetGraphRepository, "try_acquire_distributed_lock", mock_try_acquire)

        assert lock_setup.refresh(max_retries=2, retry_delay_seconds=0.01) is True
        assert mock_try_acquire.call_count == 3

    def test_refresh_does_not_retry_on_lock_conflict(self, monkeypatch, lock_setup):
        """Lock refresh should not retry when lock is held by another holder."""
        mock_try_acquire = MagicMock(return_value=False)
        monkeypatch.setattr(AssetGraphRepository, "try_acquire_distributed_lock", mock_try_acquire)

        assert lock_setup.refresh(max_retries=2) is False
        assert mock_try_acquire.call_count == 1  # No retries on lock conflict

    def test_refresh_exhausts_retries_on_persistent_error(self, monkeypatch, lock_setup):
        """Lock refresh should return False after exhausting retries."""
        mock_try_acquire = MagicMock(side_effect=SQLAlchemyError("persistent connection error"))
        monkeypatch.setattr(AssetGraphRepository, "try_acquire_distributed_lock", mock_try_acquire)

        assert lock_setup.refresh(max_retries=2, retry_delay_seconds=0.01) is False
        assert mock_try_acquire.call_count == 3  # Initial try + 2 retries

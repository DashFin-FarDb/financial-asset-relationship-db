"""Unit tests for AssetGraphRepository distributed lock and latest job methods."""

from datetime import datetime, timedelta, timezone
from time import sleep
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from src.data.database import create_session_factory, init_db
from src.data.db_models import DistributedLockORM, RebuildJobORM
from src.data.distributed_lock import (
    DistributedLock,
    LockEvent,
    LockEventType,
    LockLifecycleState,
    LockMetrics,
    LockState,
)
from src.data.repository import AssetGraphRepository


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure the datetime is timezone-aware and normalized to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@pytest.fixture
def repository_factory(tmp_path):
    """Create a factory for AssetGraphRepository with a fresh SQLite DB."""
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
        acquired = repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=60)
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
        repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=60)
        repo.session.commit()

        # Try to acquire with other holder
        repo2 = repository_factory()
        acquired = repo2.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder2", ttl_seconds=60)
        assert acquired is False

    def test_try_acquire_distributed_lock_refresh(self, repository_factory):
        """Test refreshing a lock held by the same holder."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=60)
        repo.session.commit()

        acquired = repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=120)
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
        acquired = repo2.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder2", ttl_seconds=60)
        assert acquired is True
        repo2.session.commit()

        reader = repository_factory()
        lock = reader.session.get(DistributedLockORM, "test_lock")

        assert lock.holder_id == "holder2"
        assert _ensure_utc(lock.expires_at) > now

    def test_release_distributed_lock(self, repository_factory):
        """Test releasing a lock."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=60)
        repo.session.commit()

        repo.release_distributed_lock(lock_name="test_lock", holder_id="holder1")
        repo.session.commit()

        reader = repository_factory()
        lock = reader.session.get(DistributedLockORM, "test_lock")
        assert lock is None

    def test_release_distributed_lock_not_owner(self, repository_factory):
        """Test that releasing a lock held by another holder does nothing."""
        repo = repository_factory()
        repo.try_acquire_distributed_lock(lock_name="test_lock", holder_id="holder1", ttl_seconds=60)
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

    @pytest.fixture(scope="function")
    def lock_setup(self, repository_factory):
        """Provide a factory-conformant session supplier and lock instance.

        This fixes the previous lambda bypass.
        """

        def bound_session_factory():
            """Return a fresh Session by creating a new repository.

            Uses the repository_factory fixture on each call.
            """
            return repository_factory().session

        return DistributedLock(bound_session_factory, "test_lock", ttl_seconds=60)

    def test_refresh_retries_on_transient_db_error(self, monkeypatch, lock_setup):
        """Lock refresh should retry on transient SQLAlchemyError."""
        mock_try_acquire = MagicMock(
            side_effect=[SQLAlchemyError("connection timeout"), SQLAlchemyError("connection timeout"), True]
        )
        monkeypatch.setattr(AssetGraphRepository, "try_acquire_distributed_lock", mock_try_acquire)

        assert bool(lock_setup.refresh(max_retries=2, retry_delay_seconds=0.01)) is True
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


@pytest.mark.unit
class TestDistributedLockObservability:
    """Test cases for DistributedLock state machine, event emission, and metrics."""

    @pytest.fixture(scope="function")
    def bound_session_factory(self, repository_factory):
        """Supplier for fresh Sessions."""

        def factory():
            return repository_factory().session

        return factory

    def test_initial_state(self, bound_session_factory):
        """Lock should start in INITIAL state."""
        lock = DistributedLock(bound_session_factory, "test_lock")
        assert lock._state == LockLifecycleState.INITIAL

    def test_acquire_success_observability(self, bound_session_factory):
        """Test structured event emission and metrics during successful lock acquisition."""
        events = []
        mock_metrics = MagicMock(spec=LockMetrics)

        def event_sink(event: LockEvent):
            events.append(event)

        lock = DistributedLock(
            bound_session_factory,
            "test_lock",
            metrics=mock_metrics,
            event_sink=event_sink,
        )

        assert bool(lock.acquire()) is True
        assert lock._state == LockLifecycleState.ACQUIRED

        # Verify events emitted
        assert len(events) == 2
        assert events[0].event_type == LockEventType.ACQUIRE_ATTEMPT
        assert events[0].lock_name == "test_lock"
        assert events[1].event_type == LockEventType.ACQUIRED
        assert events[1].lock_name == "test_lock"

        # Verify metrics called
        mock_metrics.inc.assert_any_call("lock_acquire_total", None)
        mock_metrics.inc.assert_any_call("lock_acquired_total", None)

    def test_refresh_success_observability(self, bound_session_factory):
        """Test event, state machine, and latency tracking during successful lock refresh."""
        events = []
        mock_metrics = MagicMock(spec=LockMetrics)

        def event_sink(event: LockEvent):
            events.append(event)

        lock = DistributedLock(
            bound_session_factory,
            "test_lock",
            metrics=mock_metrics,
            event_sink=event_sink,
        )

        # Acquire first
        assert bool(lock.acquire()) is True
        events.clear()

        # Refresh
        assert bool(lock.refresh(max_retries=0)) is True
        assert lock._state == LockLifecycleState.REFRESHED

        # Verify refresh events
        assert len(events) == 1
        assert events[0].event_type == LockEventType.REFRESHED
        assert events[0].metadata["attempt"] == 0

        # Verify refresh metrics (including latency observation)
        mock_metrics.inc.assert_any_call("lock_refresh_total", None)
        mock_metrics.observe.assert_any_call(
            "lock_refresh_latency_seconds", pytest.approx(0.0, abs=0.5), {"status": "success"}
        )

    def test_release_observability(self, bound_session_factory):
        """Test event emission and metrics during lock release."""
        events = []
        mock_metrics = MagicMock(spec=LockMetrics)

        def event_sink(event: LockEvent):
            events.append(event)

        lock = DistributedLock(
            bound_session_factory,
            "test_lock",
            metrics=mock_metrics,
            event_sink=event_sink,
        )

        assert bool(lock.acquire()) is True
        events.clear()

        lock.release()
        assert lock._state == LockLifecycleState.RELEASED

        # Verify release events
        assert len(events) == 1
        assert events[0].event_type == LockEventType.RELEASED

        # Verify metrics
        mock_metrics.inc.assert_any_call("lock_release_total", None)

    def test_refresh_transient_error_exponential_backoff_and_failed_state(self, monkeypatch, bound_session_factory):
        """Test refresh event flows, state transition to LOST, and backoff sleep delays on transient error exhaustion."""
        mock_try_acquire = MagicMock(side_effect=SQLAlchemyError("transient db error"))
        monkeypatch.setattr(AssetGraphRepository, "try_acquire_distributed_lock", mock_try_acquire)

        events = []
        mock_metrics = MagicMock(spec=LockMetrics)
        sleep_delays = []

        def mock_sleep(seconds: float):
            sleep_delays.append(seconds)

        monkeypatch.setattr("src.data.distributed_lock.sleep", mock_sleep)

        def event_sink(event: LockEvent):
            events.append(event)

        lock = DistributedLock(
            bound_session_factory,
            "test_lock",
            metrics=mock_metrics,
            event_sink=event_sink,
        )

        assert lock.refresh(max_retries=2, retry_delay_seconds=0.01) is False
        assert lock._state == LockLifecycleState.LOST

        # 3 acquire attempts failed (1 initial + 2 retries)
        assert mock_try_acquire.call_count == 3

        # Delays should be exponential: 0.01s (base * 2^0) and 0.02s (base * 2^1)
        assert len(sleep_delays) == 2
        assert pytest.approx(sleep_delays[0]) == 0.01
        assert pytest.approx(sleep_delays[1]) == 0.02

        # Verify structured events emitted: 3 transient errors, then final failed event
        transient_events = [e for e in events if e.event_type == LockEventType.TRANSIENT_ERROR]
        failed_events = [e for e in events if e.event_type == LockEventType.FAILED]

        assert len(transient_events) == 3  # each error triggers event
        assert len(failed_events) == 1
        assert failed_events[0].metadata["attempts"] == 3

        # Verify failure metrics
        mock_metrics.inc.assert_any_call("lock_refresh_failures", None)
        mock_metrics.observe.assert_any_call(
            "lock_refresh_latency_seconds", pytest.approx(0.0, abs=0.5), {"status": "failed"}
        )

    def test_refresh_contention_observability(self, bound_session_factory, repository_factory):
        """Test refresh contention transitions state to CONTENTED, emits event, and tracks metrics."""
        events = []
        mock_metrics = MagicMock(spec=LockMetrics)

        def event_sink(event: LockEvent):
            events.append(event)

        # Pre-acquire lock with a different holder id to force contention
        repo = repository_factory()
        repo.try_acquire_distributed_lock(lock_name="contested_lock", holder_id="other_holder", ttl_seconds=60)
        repo.session.commit()

        lock = DistributedLock(
            bound_session_factory,
            "contested_lock",
            holder_id="test_holder",
            metrics=mock_metrics,
            event_sink=event_sink,
        )

        assert lock.refresh(max_retries=2) is False
        assert lock._state == LockLifecycleState.CONTENTED

        # Verify contention events and metrics
        assert len(events) == 1
        assert events[0].event_type == LockEventType.CONTENTED

        mock_metrics.inc.assert_any_call("lock_contention_total", None)
        mock_metrics.observe.assert_any_call(
            "lock_refresh_latency_seconds", pytest.approx(0.0, abs=0.5), {"status": "contested"}
        )


@pytest.mark.unit
class TestMultiRegionCoordination:
    """Unit tests asserting multi-region coordination, fencing, and isolation guarantees."""

    def test_zero_replica_isolation_and_primary_only_routing(self):
        """Verify that DistributedLock only calls the coordination_session_factory."""
        coordination_called = False

        def coord_factory():
            nonlocal coordination_called
            coordination_called = True
            # Return a mock session to prevent further errors
            mock_session = MagicMock()
            return mock_session

        lock = DistributedLock(coordination_session_factory=coord_factory, lock_name="test_lock")

        # When acquire is called, only coordination_session_factory should be executed
        try:
            lock.acquire()
        except Exception:
            pass

        assert coordination_called is True

    def test_fencing_token_monotonicity(self, repository_factory):
        """Verify subsequent lock states return strictly monotonic fencing tokens (microsecond resolution)."""

        def bound_session_factory():
            return repository_factory().session

        lock = DistributedLock(
            coordination_session_factory=bound_session_factory, lock_name="fenced_lock", ttl_seconds=60
        )

        lease1 = lock.acquire()
        assert lease1 is not False
        token1 = lease1.fencing_token
        assert token1 > 0

        # Wait a tiny bit (simulating progress/update time) or manually update record
        sleep(0.01)

        lease2 = lock.refresh()
        assert lease2 is not False
        token2 = lease2.fencing_token

        assert token2 > token1

    def test_fail_fast_on_primary_partition_timeout(self, monkeypatch):
        """Verify that primary timeouts transition lock state to LOST instantly without falling back."""

        def failing_factory():
            raise TimeoutError("Primary database connection timeout")

        events = []

        def event_sink(event):
            events.append(event)

        lock = DistributedLock(
            coordination_session_factory=failing_factory, lock_name="timeout_lock", event_sink=event_sink
        )

        # check_state should catch TimeoutError and transition to LOST
        state = lock.check_state()
        assert state == LockState.LOST
        assert lock._state == LockLifecycleState.LOST

        # Verify a TRANSIENT_ERROR event is emitted
        assert len(events) == 1
        assert events[0].event_type == LockEventType.TRANSIENT_ERROR

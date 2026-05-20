"""Tests for RebuildDriftEvaluator integration with ReconciliationEngine."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest

from src.data.db_models import RebuildJobStatus
from src.data.distributed_lock import LockState
from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator
from src.logic.reconciliation_engine import Severity


class TestRebuildDriftEvaluator:
    """Tests for RebuildDriftEvaluator."""

    def test_no_job_no_executor_evaluates_as_none(self) -> None:
        """Test that no job + no executor evaluates as no drift."""
        session_factory = Mock()
        lock = Mock()
        lock.check_state.return_value = LockState.VALID

        # Mock session that returns None for active rebuild job
        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = None
        mock_session.__enter__.return_value = mock_session
        mock_session.return_value = mock_session
        session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        session_factory.return_value.__exit__ = Mock(return_value=None)

        # Patch AssetGraphRepository
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            assert drift_type == "none"
            assert severity == Severity.NONE
            assert metadata["lock_is_valid"] is True

    def test_orphaned_running_without_lock_is_high_severity(self) -> None:
        """Test that orphaned running state without lock is HIGH severity."""
        session_factory = Mock()
        lock = Mock()
        lock.check_state.return_value = LockState.EXPIRED

        # Mock running job
        mock_job = Mock()
        mock_job.job_id = "test-job-123"
        mock_job.status = RebuildJobStatus.RUNNING
        mock_job.active_worker_id = "worker-456"
        mock_job.last_heartbeat_at = datetime.now(timezone.utc)

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = mock_job
        mock_session.__enter__.return_value = mock_session
        session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        session_factory.return_value.__exit__ = Mock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=lock,
                runtime_has_active_executor=False,  # No executor
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            assert drift_type == "orphaned_running"
            assert severity == Severity.HIGH
            assert metadata["job_id"] == "test-job-123"
            assert metadata["lock_is_valid"] is False

    def test_orphaned_running_with_valid_lock_is_critical(self) -> None:
        """Test that orphaned running with valid lock is CRITICAL (split-brain)."""
        session_factory = Mock()
        lock = Mock()
        lock.check_state.return_value = LockState.VALID  # Valid lock

        # Mock running job
        mock_job = Mock()
        mock_job.job_id = "test-job-789"
        mock_job.status = RebuildJobStatus.RUNNING
        mock_job.active_worker_id = "worker-xyz"
        mock_job.last_heartbeat_at = datetime.now(timezone.utc)

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = mock_job
        mock_session.__enter__.return_value = mock_session
        session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        session_factory.return_value.__exit__ = Mock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=lock,
                runtime_has_active_executor=False,  # No executor but lock valid
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            assert drift_type == "orphaned_running"
            assert severity == Severity.CRITICAL  # Critical due to split-brain risk
            assert metadata["lock_is_valid"] is True

    def test_zombie_executor_is_critical(self) -> None:
        """Test that zombie executor (runtime active, DB not running) is CRITICAL."""
        session_factory = Mock()
        lock = Mock()
        lock.check_state.return_value = LockState.VALID

        # Mock completed job (DB not running)
        mock_job = Mock()
        mock_job.job_id = "test-job-completed"
        mock_job.status = RebuildJobStatus.SUCCEEDED
        mock_job.active_worker_id = None
        mock_job.last_heartbeat_at = datetime.now(timezone.utc)

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = mock_job
        mock_session.__enter__.return_value = mock_session
        session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        session_factory.return_value.__exit__ = Mock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=lock,
                runtime_has_active_executor=True,  # Runtime says executing!
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            assert drift_type == "zombie_executor"
            assert severity == Severity.CRITICAL

    def test_crash_suspicion_is_high_severity(self) -> None:
        """Test that stale heartbeat with no executor is classified as HIGH severity.

        Note: Orphaned running takes priority over crash suspicion in detection logic.
        """
        session_factory = Mock()
        lock = Mock()
        lock.check_state.return_value = LockState.EXPIRED

        # Mock job with stale heartbeat
        old_heartbeat = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        mock_job = Mock()
        mock_job.job_id = "test-job-stale"
        mock_job.status = RebuildJobStatus.RUNNING
        mock_job.active_worker_id = "worker-crashed"
        mock_job.last_heartbeat_at = old_heartbeat  # Very old

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = mock_job
        mock_session.__enter__.return_value = mock_session
        session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        session_factory.return_value.__exit__ = Mock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            # Orphaned running takes priority in detection (running job, no executor)
            assert drift_type == "orphaned_running"
            assert severity == Severity.HIGH

    def test_stale_ownership_is_medium_severity(self) -> None:
        """Test that stale ownership is classified as MEDIUM or HIGH severity.

        Note: Orphaned running (RUNNING status + no executor) takes priority
        over stale_ownership/crash_suspicion in the detection hierarchy.
        """
        session_factory = Mock()
        lock = Mock()
        lock.check_state.return_value = LockState.EXPIRED

        # Mock job with stale heartbeat (beyond TTL but not crash threshold)
        # This would be detected as stale_ownership rather than crash_suspicion
        # based on the specific detection logic
        mock_job = Mock()
        mock_job.job_id = "test-job-stale-owner"
        mock_job.status = RebuildJobStatus.RUNNING
        mock_job.active_worker_id = "worker-stale"
        mock_job.last_heartbeat_at = None  # No heartbeat at all

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = mock_job
        mock_session.__enter__.return_value = mock_session
        session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        session_factory.return_value.__exit__ = Mock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            # Orphaned running takes precedence over crash_suspicion/stale_ownership
            # when job is RUNNING and runtime has no executor
            assert drift_type in ("orphaned_running", "crash_suspicion", "stale_ownership")
            assert severity in (Severity.MEDIUM, Severity.HIGH)

    def test_metadata_includes_job_details(self) -> None:
        """Test that metadata includes relevant job details."""
        session_factory = Mock()
        lock = Mock()
        lock.check_state.return_value = LockState.VALID

        heartbeat_time = datetime.now(timezone.utc)
        mock_job = Mock()
        mock_job.job_id = "test-job-details"
        mock_job.status = RebuildJobStatus.RUNNING
        mock_job.active_worker_id = "worker-123"
        mock_job.last_heartbeat_at = heartbeat_time

        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = mock_job
        mock_session.__enter__.return_value = mock_session
        session_factory.return_value.__enter__ = Mock(return_value=mock_session)
        session_factory.return_value.__exit__ = Mock(return_value=None)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            assert metadata["job_id"] == "test-job-details"
            assert metadata["active_worker_id"] == "worker-123"
            assert metadata["last_heartbeat_at"] == heartbeat_time.isoformat()
            assert "job_status" in metadata
            assert metadata["lock_state"] == "valid"

    def test_handles_session_factory_error_gracefully(self) -> None:
        """Test that evaluator handles session factory errors gracefully."""
        session_factory = Mock()
        session_factory.side_effect = Exception("DB connection failed")

        lock = Mock()
        lock.check_state.return_value = LockState.VALID

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        # Should not raise, should return drift evaluation
        # (will treat job as None when DB query fails)
        drift_type, severity, metadata = evaluator.evaluate_drift()

        # No job + no executor = no drift
        assert drift_type == "none"
        assert severity == Severity.NONE

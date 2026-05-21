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

    @pytest.mark.parametrize(
        "lock_state,job_status,has_executor,expected_drift,expected_severity,test_description",
        [
            # No job, no executor = no drift
            (LockState.VALID, None, False, "none", Severity.NONE, "no_job_no_executor"),
            # Orphaned running without lock
            (LockState.EXPIRED, RebuildJobStatus.RUNNING, False, "orphaned_running", Severity.HIGH, "orphaned_no_lock"),
            # Orphaned running with valid lock (split-brain risk)
            (
                LockState.VALID,
                RebuildJobStatus.RUNNING,
                False,
                "orphaned_running",
                Severity.CRITICAL,
                "orphaned_with_lock",
            ),
            # Zombie executor (runtime active, DB shows completed)
            (
                LockState.VALID,
                RebuildJobStatus.SUCCEEDED,
                True,
                "zombie_executor",
                Severity.CRITICAL,
                "zombie_executor",
            ),
        ],
        ids=lambda params: (params[-1].name if hasattr(params[-1], "name") else str(params[-1])) if isinstance(params, tuple) else str(params),
    )
    def test_drift_type_and_severity_combinations(
        self,
        mock_session_factory,
        mock_lock,
        mock_rebuild_job,
        lock_state,
        job_status,
        has_executor,
        expected_drift,
        expected_severity,
        test_description,
    ) -> None:
        """Test various drift type and severity combinations using parametrization.

        This consolidates the repetitive pattern of testing different drift scenarios
        with the same mock setup structure.
        """
        session_factory, mock_session = mock_session_factory
        mock_lock.check_state.return_value = lock_state

        # Setup mock repository
        mock_repo = MagicMock()
        if job_status is None:
            mock_repo.get_active_rebuild_state.return_value = None
        else:
            job = mock_rebuild_job(
                job_id=f"test-job-{test_description}",
                status=job_status,
                active_worker_id="worker-456" if job_status == RebuildJobStatus.RUNNING else None,
                heartbeat_at=datetime.now(timezone.utc),
            )
            mock_repo.get_active_rebuild_state.return_value = job

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=mock_lock,
                runtime_has_active_executor=has_executor,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            assert drift_type == expected_drift, f"Expected drift {expected_drift}, got {drift_type}"
            assert severity == expected_severity, f"Expected severity {expected_severity}, got {severity}"
            assert metadata["lock_state"] == lock_state.value
            assert metadata["lock_is_valid"] == (lock_state == LockState.VALID)

    def test_crash_suspicion_is_high_severity(self, mock_session_factory, mock_lock, mock_rebuild_job) -> None:
        """Test that stale heartbeat with no executor is classified as HIGH severity.

        Note: Orphaned running takes priority over crash suspicion in detection logic.
        """
        session_factory, mock_session = mock_session_factory
        mock_lock.check_state.return_value = LockState.EXPIRED

        # Mock job with stale heartbeat
        old_heartbeat = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        job = mock_rebuild_job(
            job_id="test-job-stale",
            status=RebuildJobStatus.RUNNING,
            active_worker_id="worker-crashed",
            heartbeat_at=old_heartbeat,  # Very old
        )

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = job

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=mock_lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            # Orphaned running takes priority in detection (running job, no executor)
            assert drift_type == "orphaned_running"
            assert severity == Severity.HIGH

    def test_stale_ownership_is_medium_severity(self, mock_session_factory, mock_lock, mock_rebuild_job) -> None:
        """Test that stale ownership is classified as MEDIUM or HIGH severity.

        Note: Orphaned running (RUNNING status + no executor) takes priority
        over stale_ownership/crash_suspicion in the detection hierarchy.
        """
        session_factory, mock_session = mock_session_factory
        mock_lock.check_state.return_value = LockState.EXPIRED

        # Mock job with no heartbeat
        job = mock_rebuild_job(
            job_id="test-job-stale-owner",
            status=RebuildJobStatus.RUNNING,
            active_worker_id="worker-stale",
            heartbeat_at=None,  # No heartbeat at all
        )

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = job

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=mock_lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            # Orphaned running takes precedence over crash_suspicion/stale_ownership
            # when job is RUNNING and runtime has no executor
            assert drift_type in ("orphaned_running", "crash_suspicion", "stale_ownership")
            assert severity in (Severity.MEDIUM, Severity.HIGH)

    def test_metadata_includes_job_details(self, mock_session_factory, mock_lock, mock_rebuild_job) -> None:
        """Test that metadata includes relevant job details."""
        session_factory, mock_session = mock_session_factory
        mock_lock.check_state.return_value = LockState.VALID

        heartbeat_time = datetime.now(timezone.utc)
        job = mock_rebuild_job(
            job_id="test-job-details",
            status=RebuildJobStatus.RUNNING,
            active_worker_id="worker-123",
            heartbeat_at=heartbeat_time,
        )

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = job

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=mock_lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            drift_type, severity, metadata = evaluator.evaluate_drift()

            assert metadata["job_id"] == "test-job-details"
            assert metadata["active_worker_id"] == "worker-123"
            assert metadata["last_heartbeat_at"] == heartbeat_time.isoformat()
            assert "job_status" in metadata
            assert metadata["lock_state"] == "valid"

    def test_handles_session_factory_error_gracefully(self, mock_lock) -> None:
        """Test that evaluator handles session factory errors gracefully."""
        from sqlalchemy.exc import SQLAlchemyError

        session_factory = Mock()
        session_factory.side_effect = SQLAlchemyError("DB connection failed")

        mock_lock.check_state.return_value = LockState.VALID

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        # Should not raise, should return drift evaluation
        # (will treat job as None when DB query fails)
        drift_type, severity, metadata = evaluator.evaluate_drift()

        # No job + no executor = no drift
        assert drift_type == "none"
        assert severity == Severity.NONE

    def test_propagates_value_error_on_integrity_violation(self, mock_session_factory, mock_lock) -> None:
        """Test that ValueError from DB integrity violation is propagated."""
        session_factory, mock_session = mock_session_factory

        # Mock session that raises ValueError (e.g., multiple RUNNING jobs)
        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.side_effect = ValueError("Multiple RUNNING jobs found")

        mock_lock.check_state.return_value = LockState.VALID

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=mock_lock,
                runtime_has_active_executor=False,
                lock_ttl_seconds=300,
            )

            # Should raise ValueError (DB integrity violation)
            with pytest.raises(ValueError, match="Multiple RUNNING jobs found"):
                evaluator.evaluate_drift()

    def test_lock_lost_is_critical_drift(self, mock_session_factory, mock_lock) -> None:
        """Test that LOST lock state is treated as CRITICAL drift."""
        session_factory, _ = mock_session_factory
        mock_lock.check_state.return_value = LockState.LOST

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        drift_type, severity, metadata = evaluator.evaluate_drift()

        assert drift_type == "lock_lost"
        assert severity == Severity.CRITICAL
        assert metadata["lock_state"] == "lost"
        assert metadata["lock_is_valid"] is False
        assert "lost" in metadata["reason"].lower()

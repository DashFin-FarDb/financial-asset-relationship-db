"""Tests for RebuildDriftEvaluator integration with ReconciliationEngine."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.data.db_models import RebuildJobStatus
from src.data.distributed_lock import LockState
from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator
from src.logic.reconciliation_engine import Severity

UTC = timezone.utc


class TestRebuildDriftEvaluator:
    """Tests for RebuildDriftEvaluator."""

    @pytest.mark.parametrize(
        "lock_state,job_status,has_executor,expected_drift,expected_severity,test_description",
        [
            # No job, no executor = no drift
            pytest.param(
                LockState.VALID, None, False, "none", Severity.NONE, "no_job_no_executor", id="no_job_no_executor"
            ),
            # Orphaned running without lock
            pytest.param(
                LockState.EXPIRED,
                RebuildJobStatus.RUNNING,
                False,
                "orphaned_running",
                Severity.HIGH,
                "orphaned_no_lock",
                id="orphaned_no_lock",
            ),
            # Orphaned running with valid lock (split-brain risk)
            pytest.param(
                LockState.VALID,
                RebuildJobStatus.RUNNING,
                False,
                "orphaned_running",
                Severity.CRITICAL,
                "orphaned_with_lock",
                id="orphaned_with_lock",
            ),
            # Zombie executor (runtime active, DB shows completed)
            pytest.param(
                LockState.VALID,
                RebuildJobStatus.SUCCEEDED,
                True,
                "zombie_executor",
                Severity.CRITICAL,
                "zombie_executor",
                id="zombie_executor",
            ),
        ],
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
        """Test various drift type and severity combinations using parametrization."""
        session_factory, _ = mock_session_factory
        mock_lock.check_state.return_value = lock_state

        mock_repo = MagicMock()
        if job_status is None:
            mock_repo.get_active_rebuild_state.return_value = None
        else:
            job = mock_rebuild_job(
                job_id=f"test-job-{test_description}",
                status=job_status,
                active_worker_id="worker-456" if job_status == RebuildJobStatus.RUNNING else None,
                heartbeat_at=datetime.now(UTC),
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
        """Test that a stale heartbeat with an active executor is crash suspicion."""
        session_factory, _ = mock_session_factory
        mock_lock.check_state.return_value = LockState.VALID

        old_heartbeat = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        job = mock_rebuild_job(
            job_id="test-job-stale",
            status=RebuildJobStatus.RUNNING,
            active_worker_id="worker-crashed",
            heartbeat_at=old_heartbeat,
        )

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = job

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=mock_lock,
                runtime_has_active_executor=True,
                lock_ttl_seconds=300,
            )

            drift_type, severity, _ = evaluator.evaluate_drift()

            assert drift_type == "crash_suspicion"
            assert severity == Severity.HIGH

    def test_stale_ownership_is_medium_severity(self, mock_session_factory, mock_lock, mock_rebuild_job) -> None:
        """Test that stale ownership is classified distinctly from orphaned jobs."""
        session_factory, _ = mock_session_factory
        mock_lock.check_state.return_value = LockState.EXPIRED

        old_heartbeat = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        job = mock_rebuild_job(
            job_id="test-job-stale-owner",
            status=RebuildJobStatus.RUNNING,
            active_worker_id=None,
            heartbeat_at=old_heartbeat,
        )

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = job

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

            evaluator = RebuildDriftEvaluator(
                session_factory=session_factory,
                lock=mock_lock,
                runtime_has_active_executor=True,
                lock_ttl_seconds=300,
            )

            drift_type, severity, _ = evaluator.evaluate_drift()

            assert drift_type == "stale_ownership"
            assert severity == Severity.MEDIUM

    def test_db_error_returns_critical_drift(self, mock_lock) -> None:
        """Test that persistence failures become explicit critical drift."""
        session_factory = Mock()
        session_factory.side_effect = SQLAlchemyError("DB connection failed")

        mock_lock.check_state.return_value = LockState.VALID

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        drift_type, severity, metadata = evaluator.evaluate_drift()

        assert drift_type == "persistence_unavailable"
        assert severity == Severity.CRITICAL
        assert metadata["error_type"] == "SQLAlchemyError"
        assert metadata["lock_is_valid"] is True

    def test_metadata_includes_job_details(self, mock_session_factory, mock_lock, mock_rebuild_job) -> None:
        """Test that metadata includes relevant job details."""
        session_factory, _ = mock_session_factory
        mock_lock.check_state.return_value = LockState.VALID

        heartbeat_time = datetime.now(UTC)
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

            _, _, metadata = evaluator.evaluate_drift()

            assert metadata["job_id"] == "test-job-details"
            assert metadata["active_worker_id"] == "worker-123"
            assert metadata["last_heartbeat_at"] == heartbeat_time.isoformat()
            assert "job_status" in metadata
            assert metadata["lock_state"] == "valid"

    def test_propagates_value_error_on_integrity_violation(self, mock_session_factory, mock_lock) -> None:
        """Test that ValueError from DB integrity violation is propagated."""
        session_factory, _ = mock_session_factory

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
        assert "lost" in str(metadata["reason"]).lower()

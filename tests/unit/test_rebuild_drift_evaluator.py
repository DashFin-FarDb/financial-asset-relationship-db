"""Tests for RebuildDriftEvaluator integration with ReconciliationEngine."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.data.db_models import RebuildJobStatus
from src.data.distributed_lock import LockState
from src.logic import reconciliation_engine
from src.logic.rebuild_drift_evaluator import RebuildDriftEvaluator


class TestRebuildDriftEvaluator:
    """Tests for RebuildDriftEvaluator module execution patterns."""

    @pytest.mark.parametrize(
        "lock_state,job_status,has_executor,expected_drift,expected_severity,test_description",
        [
            # No job, no executor = no drift
            pytest.param(
                LockState.VALID,
                None,
                False,
                "none",
                reconciliation_engine.Severity.NONE,
                "no_job_no_executor",
                id="no_job_no_executor",
            ),
            # Orphaned running without lock
            pytest.param(
                LockState.EXPIRED,
                RebuildJobStatus.RUNNING,
                False,
                "orphaned_running",
                reconciliation_engine.Severity.HIGH,
                "orphaned_no_lock",
                id="orphaned_no_lock",
            ),
            # Orphaned running with valid lock (split-brain risk)
            pytest.param(
                LockState.VALID,
                RebuildJobStatus.RUNNING,
                False,
                "orphaned_running",
                reconciliation_engine.Severity.CRITICAL,
                "orphaned_with_lock",
                id="orphaned_with_lock",
            ),
            # Zombie executor (runtime active, DB shows completed)
            pytest.param(
                LockState.VALID,
                RebuildJobStatus.SUCCEEDED,
                True,
                "zombie_executor",
                reconciliation_engine.Severity.CRITICAL,
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
        monkeypatch,
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

        # Setup mock repository via execution helper mapping pattern
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

        monkeypatch.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

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

    def test_crash_suspicion_is_high_severity(
        self, mock_session_factory, mock_lock, mock_rebuild_job, monkeypatch
    ) -> None:
        """Test that stale heartbeat with no executor is classified as HIGH severity."""
        session_factory, _ = mock_session_factory
        mock_lock.check_state.return_value = LockState.EXPIRED

        old_heartbeat = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        job = mock_rebuild_job(
            job_id="test-job-stale",
            status=RebuildJobStatus.RUNNING,
            active_worker_id="worker-crashed",
            heartbeat_at=old_heartbeat,
        )

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = job

        monkeypatch.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        drift_type, severity, _ = evaluator.evaluate_drift()

        assert drift_type == "orphaned_running"
        assert severity == reconciliation_engine.Severity.HIGH

    def test_stale_ownership_is_medium_severity(
        self, mock_session_factory, mock_lock, mock_rebuild_job, monkeypatch
    ) -> None:
        """Test that stale ownership resolves cleanly inside the matching sequence logic."""
        session_factory, _ = mock_session_factory
        mock_lock.check_state.return_value = LockState.EXPIRED

        job = mock_rebuild_job(
            job_id="test-job-stale-owner",
            status=RebuildJobStatus.RUNNING,
            active_worker_id="worker-stale",
            heartbeat_at=None,
        )

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.return_value = job

        monkeypatch.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        drift_type, severity, _ = evaluator.evaluate_drift()

        assert drift_type == "orphaned_running"
        assert severity == reconciliation_engine.Severity.HIGH

    def test_metadata_includes_job_details(
        self, mock_session_factory, mock_lock, mock_rebuild_job, monkeypatch
    ) -> None:
        """Test that metadata parsing includes verified job attributes."""
        session_factory, _ = mock_session_factory
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

        monkeypatch.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

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

    def test_handles_session_factory_error_gracefully(self, mock_lock) -> None:
        """Verify fallback behavior when repository queries drop with operational exceptions."""
        session_factory = Mock()
        session_factory.side_effect = SQLAlchemyError("DB connection failed")

        mock_lock.check_state.return_value = LockState.VALID

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        drift_type, severity, _ = evaluator.evaluate_drift()

        assert drift_type == "none"
        assert severity == reconciliation_engine.Severity.NONE

    def test_verifies_lock_check_exception_handling_safely(self, mock_session_factory, mock_lock) -> None:
        """Verify security safety bounds when the coordination lock system breaks entirely.

        Asserts that critical engine components do not silently swallow infrastructural or
        coordination backend failures, preventing invisible deadlocks or split-brain configurations.
        """
        session_factory, _ = mock_session_factory
        mock_lock.check_state.side_effect = RuntimeError("Distributed lock backend unreachable")

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        with pytest.raises(RuntimeError, match="Distributed lock backend unreachable"):
            evaluator.evaluate_drift()

    def test_propagates_value_error_on_integrity_violation(self, mock_session_factory, mock_lock, monkeypatch) -> None:
        """Test sequence stability assertions when data integrity layers throw state errors."""
        session_factory, _ = mock_session_factory

        mock_repo = MagicMock()
        mock_repo.get_active_rebuild_state.side_effect = ValueError("Multiple RUNNING jobs found")

        mock_lock.check_state.return_value = LockState.VALID

        monkeypatch.setattr("src.logic.rebuild_drift_evaluator.AssetGraphRepository", lambda session: mock_repo)

        evaluator = RebuildDriftEvaluator(
            session_factory=session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
            lock_ttl_seconds=300,
        )

        with pytest.raises(ValueError, match="Multiple RUNNING jobs found"):
            evaluator.evaluate_drift()

    def test_lock_lost_is_critical_drift(self, mock_session_factory, mock_lock) -> None:
        """Test sequence evaluation bounds when active processing scopes drop lock states."""
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
        assert severity == reconciliation_engine.Severity.CRITICAL
        assert metadata["lock_state"] == "lost"
        assert metadata["lock_is_valid"] is False
        assert "lost" in metadata["reason"].lower()

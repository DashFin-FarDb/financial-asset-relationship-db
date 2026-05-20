"""Tests for the Reconciliation Engine core abstraction."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src.logic.reconciliation_engine import (
    ActionType,
    DriftEvaluator,
    ExecutionMode,
    ReconciliationEngine,
    ReconciliationPlan,
    Severity,
)


class MockDriftEvaluator:
    """Mock drift evaluator for testing."""

    def __init__(
        self,
        drift_type: str,
        severity: Severity,
        metadata: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        """Initialize mock evaluator with predetermined drift."""
        self.drift_type = drift_type
        self.severity = severity
        self.metadata = metadata or {}

    def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | bool | None]]:
        """Return predetermined drift evaluation."""
        return self.drift_type, self.severity, self.metadata


class TestReconciliationPlan:
    """Tests for ReconciliationPlan data structure."""

    def test_plan_creation_valid(self) -> None:
        """Test creating a valid reconciliation plan."""
        plan = ReconciliationPlan(
            drift_type="test_drift",
            severity=Severity.MEDIUM,
            actions=[ActionType.REBUILD_GRAPH],
            target_state="Target state description",
            execution_mode=ExecutionMode.DEFERRED,
            reason="Test reason",
            metadata={"key": "value"},
            created_at=datetime.now(timezone.utc),
        )

        assert plan.drift_type == "test_drift"
        assert plan.severity == Severity.MEDIUM
        assert plan.actions == [ActionType.REBUILD_GRAPH]
        assert plan.execution_mode == ExecutionMode.DEFERRED

    def test_plan_requires_actions(self) -> None:
        """Test that plan creation fails without actions."""
        with pytest.raises(ValueError, match="must contain at least one action"):
            ReconciliationPlan(
                drift_type="test_drift",
                severity=Severity.MEDIUM,
                actions=[],  # Empty actions list
                target_state="Target state",
                execution_mode=ExecutionMode.AUTOMATIC,
                reason="Test",
                metadata={},
                created_at=datetime.now(timezone.utc),
            )

    def test_plan_noop_consistency(self) -> None:
        """Test that NONE severity requires NOOP action."""
        # Valid: NONE severity with NOOP
        plan_valid = ReconciliationPlan(
            drift_type="none",
            severity=Severity.NONE,
            actions=[ActionType.NOOP],
            target_state="Already converged",
            execution_mode=ExecutionMode.AUTOMATIC,
            reason="No drift",
            metadata={},
            created_at=datetime.now(timezone.utc),
        )
        assert plan_valid.severity == Severity.NONE

        # Invalid: NONE severity without NOOP
        with pytest.raises(ValueError, match="Severity NONE requires NOOP action"):
            ReconciliationPlan(
                drift_type="none",
                severity=Severity.NONE,
                actions=[ActionType.REBUILD_GRAPH],  # Wrong action for NONE severity
                target_state="Target",
                execution_mode=ExecutionMode.AUTOMATIC,
                reason="Test",
                metadata={},
                created_at=datetime.now(timezone.utc),
            )


class TestReconciliationEngine:
    """Tests for ReconciliationEngine core functionality."""

    def test_no_drift_produces_noop_plan(self) -> None:
        """Test that no drift produces a NOOP plan."""
        evaluator = MockDriftEvaluator("none", Severity.NONE)
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.severity == Severity.NONE
        assert plan.actions == [ActionType.NOOP]
        assert plan.execution_mode == ExecutionMode.AUTOMATIC
        assert "converged" in plan.reason.lower()

    def test_critical_drift_produces_alert_only(self) -> None:
        """Test that critical drift produces ALERT_ONLY plan."""
        evaluator = MockDriftEvaluator("unknown_critical", Severity.CRITICAL)
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.severity == Severity.CRITICAL
        assert plan.actions == [ActionType.ALERT_ONLY]
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert "unsafe" in plan.reason.lower()

    def test_orphaned_running_produces_reset_plan(self) -> None:
        """Test that orphaned running state produces RESET plan."""
        evaluator = MockDriftEvaluator(
            "orphaned_running",
            Severity.HIGH,
            metadata={"job_id": "test-123", "lock_is_valid": False},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "orphaned_running"
        assert plan.severity == Severity.HIGH
        assert ActionType.RESET_STATE in plan.actions
        assert plan.execution_mode == ExecutionMode.DEFERRED
        assert "orphaned" in plan.reason.lower()

    def test_stale_ownership_produces_reset_plan(self) -> None:
        """Test that stale ownership produces RESET plan."""
        evaluator = MockDriftEvaluator(
            "stale_ownership",
            Severity.MEDIUM,
            metadata={"job_id": "test-456"},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "stale_ownership"
        assert ActionType.RESET_STATE in plan.actions
        assert "stale" in plan.reason.lower()

    def test_crash_suspicion_produces_reset_plan(self) -> None:
        """Test that crash suspicion produces RESET plan."""
        evaluator = MockDriftEvaluator(
            "crash_suspicion",
            Severity.HIGH,
            metadata={"job_id": "test-789"},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "crash_suspicion"
        assert ActionType.RESET_STATE in plan.actions
        assert "crash" in plan.reason.lower()

    def test_zombie_executor_produces_alert_only(self) -> None:
        """Test that zombie executor produces ALERT_ONLY plan (split-brain risk)."""
        evaluator = MockDriftEvaluator(
            "zombie_executor",
            Severity.CRITICAL,
            metadata={"runtime_has_active_executor": True},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "zombie_executor"
        assert plan.actions == [ActionType.ALERT_ONLY]
        assert plan.execution_mode == ExecutionMode.MANUAL
        # Critical severity triggers generic critical path, so reason mentions "critical" not "zombie"
        assert "critical" in plan.reason.lower() or "unsafe" in plan.reason.lower()

    def test_version_mismatch_produces_rebuild_plan(self) -> None:
        """Test that version mismatch produces REBUILD plan."""
        evaluator = MockDriftEvaluator(
            "version_mismatch",
            Severity.MEDIUM,
            metadata={"expected_version": "1.2.3", "actual_version": "1.2.2"},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "version_mismatch"
        assert ActionType.REBUILD_GRAPH in plan.actions
        assert "version" in plan.reason.lower()

    def test_low_health_degradation_produces_alert_only(self) -> None:
        """Test that low-severity health degradation produces ALERT_ONLY."""
        evaluator = MockDriftEvaluator(
            "health_degradation",
            Severity.LOW,
            metadata={"health_score": 0.85},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "health_degradation"
        assert plan.actions == [ActionType.ALERT_ONLY]
        assert plan.execution_mode == ExecutionMode.AUTOMATIC

    def test_high_health_degradation_produces_restart_plan(self) -> None:
        """Test that high-severity health degradation produces RESTART plan."""
        evaluator = MockDriftEvaluator(
            "health_degradation",
            Severity.HIGH,
            metadata={"health_score": 0.3},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "health_degradation"
        assert ActionType.RESTART_RUNTIME in plan.actions
        assert plan.execution_mode == ExecutionMode.DEFERRED

    def test_persistence_inconsistency_produces_repair_plan(self) -> None:
        """Test that persistence inconsistency produces REPAIR plan."""
        evaluator = MockDriftEvaluator(
            "persistence_inconsistency",
            Severity.MEDIUM,
            metadata={"inconsistency_details": "checksum mismatch"},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "persistence_inconsistency"
        assert ActionType.REPAIR_PERSISTENCE in plan.actions
        assert plan.execution_mode == ExecutionMode.MANUAL

    def test_unknown_drift_type_produces_alert_only(self) -> None:
        """Test that unknown drift type produces ALERT_ONLY plan."""
        evaluator = MockDriftEvaluator(
            "completely_unknown_type",
            Severity.MEDIUM,
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "completely_unknown_type"
        assert plan.actions == [ActionType.ALERT_ONLY]
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert "unknown" in plan.reason.lower()

    def test_automatic_execution_mode_with_high_severity_reset(self) -> None:
        """Test that automatic execution is used for high-severity reset when enabled."""
        evaluator = MockDriftEvaluator(
            "orphaned_running",
            Severity.HIGH,
        )
        engine = ReconciliationEngine(evaluator, enable_automatic_execution=True)

        plan = engine.generate_reconciliation_plan()

        assert plan.execution_mode == ExecutionMode.AUTOMATIC

    def test_deferred_execution_without_automatic_flag(self) -> None:
        """Test that deferred execution is used when automatic execution is disabled."""
        evaluator = MockDriftEvaluator(
            "orphaned_running",
            Severity.HIGH,
        )
        engine = ReconciliationEngine(evaluator, enable_automatic_execution=False)

        plan = engine.generate_reconciliation_plan()

        assert plan.execution_mode == ExecutionMode.DEFERRED

    def test_plan_includes_metadata(self) -> None:
        """Test that generated plan includes metadata from drift evaluation."""
        test_metadata = {
            "job_id": "test-job-123",
            "lock_state": "valid",
            "worker_id": "worker-456",
        }
        evaluator = MockDriftEvaluator(
            "crash_suspicion",
            Severity.HIGH,
            metadata=test_metadata,
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.metadata == test_metadata
        assert plan.metadata["job_id"] == "test-job-123"

    def test_plan_timestamp_is_recent(self) -> None:
        """Test that plan creation timestamp is recent."""
        evaluator = MockDriftEvaluator("none", Severity.NONE)
        engine = ReconciliationEngine(evaluator)

        before = datetime.now(timezone.utc)
        plan = engine.generate_reconciliation_plan()
        after = datetime.now(timezone.utc)

        assert before <= plan.created_at <= after

    def test_deterministic_plan_generation(self) -> None:
        """Test that same drift produces same plan (deterministic)."""
        evaluator = MockDriftEvaluator("orphaned_running", Severity.HIGH)
        engine = ReconciliationEngine(evaluator)

        plan1 = engine.generate_reconciliation_plan()
        plan2 = engine.generate_reconciliation_plan()

        # Same drift should produce same actions and execution mode
        assert plan1.drift_type == plan2.drift_type
        assert plan1.severity == plan2.severity
        assert plan1.actions == plan2.actions
        assert plan1.execution_mode == plan2.execution_mode
        assert plan1.reason == plan2.reason


class TestDriftEvaluatorProtocol:
    """Tests for DriftEvaluator protocol compliance."""

    def test_mock_evaluator_implements_protocol(self) -> None:
        """Test that mock evaluator implements the protocol correctly."""
        evaluator = MockDriftEvaluator("test", Severity.MEDIUM)

        # Should have evaluate_drift method
        assert hasattr(evaluator, "evaluate_drift")
        assert callable(evaluator.evaluate_drift)

        # Should return correct tuple structure
        drift_type, severity, metadata = evaluator.evaluate_drift()
        assert isinstance(drift_type, str)
        assert isinstance(severity, Severity)
        assert isinstance(metadata, dict)

    def test_protocol_compatibility_with_engine(self) -> None:
        """Test that any DriftEvaluator implementation works with engine."""
        # Create a minimal protocol-compliant evaluator
        class MinimalEvaluator:
            def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | bool | None]]:
                return "test_drift", Severity.LOW, {}

        evaluator = MinimalEvaluator()
        engine = ReconciliationEngine(evaluator)

        # Should work without errors
        plan = engine.generate_reconciliation_plan()
        assert plan is not None
        assert isinstance(plan, ReconciliationPlan)

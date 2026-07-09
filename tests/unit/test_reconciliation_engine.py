"""Tests for the Reconciliation Engine core abstraction."""

from datetime import datetime, timezone
from typing import Any

import pytest

from src.logic.reconciliation_engine import (
    ActionType,
    ExecutionMode,
    ExecutionSafety,
    ReconciliationEngine,
    ReconciliationPlan,
    Severity,
)
from src.models.financial_models import Asset, AssetClass

UTC = timezone.utc


class MockDriftEvaluator:
    """Mock drift evaluator for testing."""

    def __init__(
        self,
        drift_type: str,
        severity: Severity,
        metadata: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        """Initialize mock evaluator with predetermined drift."""
        self.drift_type = drift_type
        self.severity = severity
        self.metadata = metadata or {}

    def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
        """Return predetermined drift evaluation."""
        return self.drift_type, self.severity, self.metadata


class MinimalDriftEvaluator:
    """Minimal protocol-compliant evaluator for engine compatibility tests."""

    def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
        """Return a no-drift result."""
        return "minimal", Severity.NONE, {}


class TestReconciliationPlan:
    """Tests for ReconciliationPlan data structure."""

    def test_plan_creation_valid(self) -> None:
        """Test creating a valid reconciliation plan."""
        plan = ReconciliationPlan(
            drift_type="test_drift",
            severity=Severity.MEDIUM,
            actions=(ActionType.RESET_STATE,),
            target_state="Target state description",
            execution_mode=ExecutionMode.DEFERRED,
            safety_state=ExecutionSafety.RESET_REQUIRED,
            reason="Test reason",
            metadata={"key": "value"},
            created_at=datetime.now(UTC),
        )

        assert plan.drift_type == "test_drift"
        assert plan.severity == Severity.MEDIUM
        assert plan.actions == (ActionType.RESET_STATE,)
        assert plan.execution_mode == ExecutionMode.DEFERRED

    def test_plan_requires_actions(self) -> None:
        """Test that plan creation fails without actions."""
        with pytest.raises(ValueError, match="must contain at least one action"):
            ReconciliationPlan(
                drift_type="test_drift",
                severity=Severity.MEDIUM,
                actions=(),  # Empty actions list
                target_state="Target state",
                execution_mode=ExecutionMode.AUTOMATIC,
                safety_state=ExecutionSafety.MANUAL_INVESTIGATION,
                reason="Test",
                metadata={},
                created_at=datetime.now(UTC),
            )

    def test_plan_noop_consistency(self) -> None:
        """Test that NONE severity requires NOOP action."""
        # Valid: NONE severity with NOOP
        plan_valid = ReconciliationPlan(
            drift_type="none",
            severity=Severity.NONE,
            actions=(ActionType.NOOP,),
            target_state="Already converged",
            execution_mode=ExecutionMode.AUTOMATIC,
            safety_state=ExecutionSafety.CONVERGED,
            reason="No drift",
            metadata={},
            created_at=datetime.now(UTC),
        )
        assert plan_valid.severity == Severity.NONE

        # Invalid: NONE severity without NOOP
        with pytest.raises(ValueError, match="Severity NONE requires NOOP action"):
            ReconciliationPlan(
                drift_type="none",
                severity=Severity.NONE,
                actions=(ActionType.ALERT_ONLY,),  # Wrong action for NONE severity
                target_state="Target",
                execution_mode=ExecutionMode.AUTOMATIC,
                safety_state=ExecutionSafety.MANUAL_INVESTIGATION,
                reason="Test",
                metadata={},
                created_at=datetime.now(UTC),
            )

    def test_plan_rejects_invalid_action_types(self) -> None:
        """Test that plan creation fails with invalid action types."""
        # Test with string that's not an ActionType enum value
        with pytest.raises(ValueError, match="Invalid action type.*Must be an ActionType enum value"):
            ReconciliationPlan(
                drift_type="test_drift",
                severity=Severity.MEDIUM,
                actions=("invalid_action",),  # type: ignore[arg-type]  # Intentional for test
                target_state="Target state",
                execution_mode=ExecutionMode.DEFERRED,
                safety_state=ExecutionSafety.RESET_REQUIRED,
                reason="Test",
                metadata={},
                created_at=datetime.now(UTC),
            )

        # Test with mixed valid and invalid action types
        with pytest.raises(ValueError, match="Invalid action type.*Must be an ActionType enum value"):
            ReconciliationPlan(
                drift_type="test_drift",
                severity=Severity.HIGH,
                actions=(ActionType.RESET_STATE, "invalid_action"),  # type: ignore[arg-type]  # Intentional for test
                target_state="Target state",
                execution_mode=ExecutionMode.DEFERRED,
                safety_state=ExecutionSafety.RESET_REQUIRED,
                reason="Test",
                metadata={},
                created_at=datetime.now(UTC),
            )


class TestReconciliationEngine:
    """Tests for ReconciliationEngine core functionality."""

    def test_evaluator_runtime_error_returns_failure_plan(self) -> None:
        """Unexpected evaluator exceptions become explicit CRITICAL plans."""

        class FailingEvaluator:
            def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
                raise RuntimeError("lock subsystem unavailable")

        engine = ReconciliationEngine(FailingEvaluator())
        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "drift_evaluation_failed"
        assert plan.severity == Severity.CRITICAL
        assert plan.actions == (ActionType.ALERT_ONLY,)
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert plan.safety_state == ExecutionSafety.EVALUATION_FAILED
        assert plan.metadata["error_type"] == "RuntimeError"

    def test_evaluator_value_error_propagates(self) -> None:
        """Invariant/integrity failures intentionally propagate."""

        class IntegrityFailEvaluator:
            def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
                raise ValueError("multiple RUNNING jobs found")

        engine = ReconciliationEngine(IntegrityFailEvaluator())

        with pytest.raises(ValueError, match="multiple RUNNING jobs found"):
            engine.generate_reconciliation_plan()

    def test_no_drift_produces_noop_plan(self) -> None:
        """Test that no drift produces a NOOP plan."""
        evaluator = MockDriftEvaluator("none", Severity.NONE, metadata={"lock_is_valid": True})
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.severity == Severity.NONE
        assert plan.actions == (ActionType.NOOP,)
        assert plan.execution_mode == ExecutionMode.AUTOMATIC
        assert plan.safety_state == ExecutionSafety.CONVERGED
        assert "converged" in plan.reason.lower()

    @pytest.mark.parametrize("true_value", ["true", "True", "TRUE", "1", "yes", "y", "t"], ids=repr)
    def test_lock_is_valid_string_truthy_variants(self, true_value: Any) -> None:
        """Test that lock_is_valid parsing handles common truthy string representations."""
        evaluator = MockDriftEvaluator("none", Severity.NONE, metadata={"lock_is_valid": true_value})
        engine = ReconciliationEngine(evaluator)
        plan = engine.generate_reconciliation_plan()
        assert plan.safety_state == ExecutionSafety.CONVERGED
        assert plan.execution_mode == ExecutionMode.AUTOMATIC

    @pytest.mark.parametrize("false_value", ["false", "False", "FALSE", "0", "no", "n", "f", ""], ids=repr)
    def test_lock_is_valid_string_falsy_variants(self, false_value: Any) -> None:
        """Test that lock_is_valid parsing handles common falsy string representations."""
        evaluator = MockDriftEvaluator("none", Severity.NONE, metadata={"lock_is_valid": false_value})
        engine = ReconciliationEngine(evaluator)
        plan = engine.generate_reconciliation_plan()

        assert plan.safety_state == ExecutionSafety.WAIT_REQUIRED
        assert plan.execution_mode == ExecutionMode.DEFERRED

    @pytest.mark.parametrize(
        "true_value",
        [
            pytest.param(1, id="int_1"),
            pytest.param(1.0, id="float_1.0"),
            pytest.param(42, id="int_42"),
            pytest.param(-1, id="int_-1"),
        ],
    )
    def test_lock_is_valid_number_truthy_variants(self, true_value: Any) -> None:
        """Test that lock_is_valid parsing handles numeric truthy representations."""
        evaluator = MockDriftEvaluator("none", Severity.NONE, metadata={"lock_is_valid": true_value})
        engine = ReconciliationEngine(evaluator)
        plan = engine.generate_reconciliation_plan()
        assert plan.safety_state == ExecutionSafety.CONVERGED
        assert plan.execution_mode == ExecutionMode.AUTOMATIC

    @pytest.mark.parametrize(
        "false_value",
        [
            pytest.param(0, id="int_0"),
            pytest.param(0.0, id="float_0.0"),
        ],
    )
    def test_lock_is_valid_number_falsy_variants(self, false_value: Any) -> None:
        """Test that lock_is_valid parsing handles numeric falsy representations."""
        evaluator = MockDriftEvaluator("none", Severity.NONE, metadata={"lock_is_valid": false_value})
        engine = ReconciliationEngine(evaluator)
        plan = engine.generate_reconciliation_plan()
        assert plan.safety_state == ExecutionSafety.WAIT_REQUIRED
        assert plan.execution_mode == ExecutionMode.DEFERRED

    def test_lock_is_valid_none_defaults_to_false(self) -> None:
        """Test that None defaults to False for lock_is_valid."""
        evaluator = MockDriftEvaluator("none", Severity.NONE, metadata={"lock_is_valid": None})
        engine = ReconciliationEngine(evaluator)
        plan = engine.generate_reconciliation_plan()
        assert plan.safety_state == ExecutionSafety.WAIT_REQUIRED
        assert plan.execution_mode == ExecutionMode.DEFERRED

    def test_no_drift_invalid_lock_waits(self) -> None:
        """Test that no drift with invalid lock returns WAIT plan."""
        evaluator = MockDriftEvaluator("none", Severity.NONE, metadata={"lock_is_valid": False})
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.severity == Severity.NONE
        assert plan.actions == (ActionType.NOOP,)
        assert plan.execution_mode == ExecutionMode.DEFERRED
        assert plan.safety_state == ExecutionSafety.WAIT_REQUIRED
        assert "gated on lock" in plan.reason.lower()

    def test_critical_drift_produces_alert_only(self) -> None:
        """Test that critical drift produces ALERT_ONLY plan."""
        evaluator = MockDriftEvaluator("unknown_critical", Severity.CRITICAL)
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.severity == Severity.CRITICAL
        assert plan.actions == (ActionType.ALERT_ONLY,)
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert plan.safety_state == ExecutionSafety.MANUAL_INVESTIGATION
        assert "unsafe" in plan.reason.lower()

    def test_critical_lock_lost_is_integrity_compromised(self) -> None:
        """Test critical lock lost is flagged as integrity compromised."""
        evaluator = MockDriftEvaluator("lock_lost", Severity.CRITICAL, metadata={"lock_is_valid": False})
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.actions == (ActionType.ALERT_ONLY,)
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert plan.safety_state == ExecutionSafety.INTEGRITY_COMPROMISED

    def test_critical_persistence_unavailable_is_observability_failure(self) -> None:
        """Test critical persistence unavailable is flagged as observability failure."""
        evaluator = MockDriftEvaluator("persistence_unavailable", Severity.CRITICAL)
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.actions == (ActionType.ALERT_ONLY,)
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert plan.safety_state == ExecutionSafety.OBSERVABILITY_FAILURE

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
        assert plan.safety_state == ExecutionSafety.RESET_REQUIRED
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
        assert plan.safety_state == ExecutionSafety.RESET_REQUIRED
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
        assert plan.safety_state == ExecutionSafety.RESET_REQUIRED
        assert "crash" in plan.reason.lower()

    def test_crash_suspicion_with_valid_lock_produces_wait_plan(self) -> None:
        """Test that crash suspicion waits while the lock remains valid."""
        evaluator = MockDriftEvaluator(
            "crash_suspicion",
            Severity.HIGH,
            metadata={"job_id": "test-789", "lock_is_valid": True},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.actions == (ActionType.WAIT_FOR_CONVERGENCE,)
        assert plan.execution_mode == ExecutionMode.DEFERRED
        assert plan.safety_state == ExecutionSafety.WAIT_REQUIRED
        assert "wait" in plan.target_state.lower()

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
        assert plan.actions == (ActionType.ALERT_ONLY,)
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert plan.safety_state == ExecutionSafety.UNSAFE_SPLIT_BRAIN
        # Critical severity triggers generic critical path, so reason mentions "critical" not "zombie"
        assert "critical" in plan.reason.lower() or "unsafe" in plan.reason.lower()

    def test_stale_ownership_with_valid_lock_produces_wait_plan(self) -> None:
        """Test that stale ownership waits while the lock remains valid."""
        evaluator = MockDriftEvaluator(
            "stale_ownership",
            Severity.MEDIUM,
            metadata={"job_id": "test-456", "lock_is_valid": True},
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.actions == (ActionType.WAIT_FOR_CONVERGENCE,)
        assert plan.execution_mode == ExecutionMode.DEFERRED
        assert plan.safety_state == ExecutionSafety.WAIT_REQUIRED
        assert "wait" in plan.target_state.lower()

    def test_unknown_drift_type_produces_alert_only(self) -> None:
        """Test that unknown drift type produces ALERT_ONLY plan."""
        evaluator = MockDriftEvaluator(
            "completely_unknown_type",
            Severity.MEDIUM,
        )
        engine = ReconciliationEngine(evaluator)

        plan = engine.generate_reconciliation_plan()

        assert plan.drift_type == "completely_unknown_type"
        assert plan.actions == (ActionType.ALERT_ONLY,)
        assert plan.execution_mode == ExecutionMode.MANUAL
        assert plan.safety_state == ExecutionSafety.MANUAL_INVESTIGATION
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
        assert plan.safety_state == ExecutionSafety.RESET_REQUIRED

    def test_deferred_execution_without_automatic_flag(self) -> None:
        """Test that deferred execution is used when automatic execution is disabled."""
        evaluator = MockDriftEvaluator(
            "orphaned_running",
            Severity.HIGH,
        )
        engine = ReconciliationEngine(evaluator, enable_automatic_execution=False)

        plan = engine.generate_reconciliation_plan()

        assert plan.execution_mode == ExecutionMode.DEFERRED
        assert plan.safety_state == ExecutionSafety.RESET_REQUIRED

    def test_plan_includes_metadata(self) -> None:
        """Test that generated plan includes metadata from drift evaluation."""
        test_metadata: dict[str, Any] = {
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

        # Metadata will include lock_is_valid (normalized from missing value)
        assert plan.metadata["job_id"] == "test-job-123"
        assert plan.metadata["lock_state"] == "valid"
        assert plan.metadata["worker_id"] == "worker-456"
        assert "lock_is_valid" in plan.metadata  # Added by normalization

    def test_plan_timestamp_is_recent(self) -> None:
        """Test that plan creation timestamp is recent."""
        evaluator = MockDriftEvaluator("none", Severity.NONE)
        engine = ReconciliationEngine(evaluator)

        before = datetime.now(UTC)
        plan = engine.generate_reconciliation_plan()
        after = datetime.now(UTC)

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
        assert plan1.safety_state == plan2.safety_state
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
        evaluator = MinimalDriftEvaluator()
        engine = ReconciliationEngine(evaluator)

        # Should work without errors
        plan = engine.generate_reconciliation_plan()
        assert plan is not None
        assert isinstance(plan, ReconciliationPlan)

    def test_run_rebuild_with_checkpoints(self) -> None:
        """Test that run_rebuild correctly invokes checkpoints and respects initial state."""
        # Create 120 assets to trigger multiple checkpoints (every 50)
        assets = [
            Asset(id=f"A{i}", symbol=f"S{i}", name=f"N{i}", asset_class=AssetClass.EQUITY, sector="Tech", price=100.0)
            for i in range(120)
        ]

        checkpoints = []

        def on_checkpoint(data: dict[str, Any]) -> None:
            checkpoints.append(data)

        from src.logic.rebuild_executor import RebuildExecutor

        executor = RebuildExecutor()

        # 1. Full rebuild without initial checkpoint
        graph = executor.run_rebuild(assets=assets, regulatory_events=[], on_checkpoint=on_checkpoint)

        assert len(graph.assets) == 120
        # Checkpoints at 50, 100, and final (total 3)
        assert len(checkpoints) == 3
        assert checkpoints[0]["processed_count"] == 50
        assert checkpoints[1]["processed_count"] == 100
        assert checkpoints[2]["processed_count"] == 120
        assert checkpoints[2].get("last_asset_id") is None  # final checkpoint doesn't set last_asset_id in my impl

        # 2. Resumed rebuild with initial checkpoint
        checkpoints.clear()
        initial_checkpoint = {"processed_ids": [a.id for a in assets[:100]]}

        graph_resumed = executor.run_rebuild(
            assets=assets,
            regulatory_events=[],
            on_checkpoint=on_checkpoint,
            initial_checkpoint=initial_checkpoint,
        )

        assert len(graph_resumed.assets) == 120
        # Only 20 new assets processed -> no 50-asset intervals -> only final checkpoint
        assert len(checkpoints) == 1
        assert checkpoints[0]["processed_count"] == 120

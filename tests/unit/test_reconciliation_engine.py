"""Unit tests for deterministic reconciliation plan generation."""

from src.logic.reconciliation_engine import (
    ActionType,
    DesiredState,
    DeterministicReconciliationEngine,
    DriftType,
    ObservedState,
    Severity,
)


def test_reconcile_returns_noop_when_states_are_aligned() -> None:
    """Aligned desired/observed state should map to a NOOP plan."""
    engine = DeterministicReconciliationEngine()
    desired = DesiredState(graph_version="v1")
    observed = ObservedState(graph_version="v1")

    plan = engine.reconcile(desired, observed)

    assert plan.drift_type == DriftType.NONE
    assert plan.severity == Severity.NONE
    assert plan.actions == (ActionType.NOOP,)


def test_reconcile_returns_rebuild_for_version_mismatch() -> None:
    """Version mismatch drift should map deterministically to REBUILD_GRAPH."""
    engine = DeterministicReconciliationEngine()
    desired = DesiredState(graph_version="v2")
    observed = ObservedState(graph_version="v1")

    plan = engine.reconcile(desired, observed)

    assert plan.drift_type == DriftType.VERSION_MISMATCH
    assert plan.severity == Severity.HIGH
    assert plan.actions == (ActionType.REBUILD_GRAPH,)


def test_reconcile_returns_alert_only_for_non_critical_health_degradation() -> None:
    """Non-critical health degradation should map to ALERT_ONLY."""
    engine = DeterministicReconciliationEngine()
    desired = DesiredState(graph_version="v1")
    observed = ObservedState(graph_version="v1", health_degraded=True)

    plan = engine.reconcile(desired, observed)

    assert plan.drift_type == DriftType.HEALTH_DEGRADED
    assert plan.severity == Severity.MEDIUM
    assert plan.actions == (ActionType.ALERT_ONLY,)


def test_reconcile_is_deterministic_for_identical_inputs() -> None:
    """Same inputs should always produce identical reconciliation plans."""
    engine = DeterministicReconciliationEngine()
    desired = DesiredState(graph_version="v2")
    observed = ObservedState(graph_version="v1")

    plan_one = engine.reconcile(desired, observed)
    plan_two = engine.reconcile(desired, observed)

    assert plan_one == plan_two

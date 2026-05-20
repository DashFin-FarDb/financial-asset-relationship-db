"""Deterministic reconciliation planning for desired vs observed state drift."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ActionType(StrEnum):
    """Plan actions emitted by reconciliation logic."""

    NOOP = "noop"
    REBUILD_GRAPH = "rebuild_graph"
    ROLLBACK_VERSION = "rollback_version"
    REPAIR_PERSISTENCE = "repair_persistence"
    RESTART_RUNTIME = "restart_runtime"
    ALERT_ONLY = "alert_only"


class DriftType(StrEnum):
    """Normalized drift classes produced by drift evaluation."""

    NONE = "none"
    VERSION_MISMATCH = "version_mismatch"
    PERSISTENCE_UNHEALTHY = "persistence_unhealthy"
    RUNTIME_UNHEALTHY = "runtime_unhealthy"
    HEALTH_DEGRADED = "health_degraded"


class Severity(StrEnum):
    """Reconciliation severity levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutionMode(StrEnum):
    """Execution mode for reconciliation plan consumers."""

    DELEGATE_TO_JOB_SYSTEM = "delegate_to_job_system"


@dataclass(frozen=True)
class DesiredState:
    """Desired control-plane state for reconciliation planning."""

    graph_version: str | None = None
    require_runtime_healthy: bool = True
    require_persistence_healthy: bool = True


@dataclass(frozen=True)
class ObservedState:
    """Observed runtime state used for drift evaluation."""

    graph_version: str | None = None
    runtime_healthy: bool = True
    persistence_healthy: bool = True
    health_degraded: bool = False


@dataclass(frozen=True)
class DriftEvaluation:
    """Standardized drift output from evaluator."""

    drift_type: DriftType
    severity: Severity
    reason: str


@dataclass(frozen=True)
class ReconciliationPlan:
    """Plan-only reconciliation output; execution is delegated."""

    drift_type: DriftType
    severity: Severity
    actions: tuple[ActionType, ...]
    target_state: DesiredState
    execution_mode: ExecutionMode
    reason: str


class DriftEvaluator(Protocol):
    """Contract for converting state into normalized drift."""

    def evaluate(self, desired_state: DesiredState, observed_state: ObservedState) -> DriftEvaluation:
        """Evaluate drift between desired and observed state."""


class ReconciliationEngine(Protocol):
    """Contract for deterministic plan generation."""

    def reconcile(self, desired_state: DesiredState, observed_state: ObservedState) -> ReconciliationPlan:
        """Generate a plan without executing side effects."""


class DefaultDriftEvaluator:
    """Default deterministic drift evaluator for desired-state vs observed-state inputs."""

    def evaluate(self, desired_state: DesiredState, observed_state: ObservedState) -> DriftEvaluation:
        """Evaluate drift according to deterministic priority rules.

        Priority order:
        1) version mismatch
        2) persistence health drift
        3) runtime health drift
        4) non-critical degradation
        5) aligned (none)
        """
        observed_version = observed_state.graph_version
        if desired_state.graph_version and (
            observed_version is None or observed_version != desired_state.graph_version
        ):
            return DriftEvaluation(
                drift_type=DriftType.VERSION_MISMATCH,
                severity=Severity.HIGH,
                reason=(
                    f"Observed graph version {observed_version!r} does not match desired "
                    f"version {desired_state.graph_version!r}"
                ),
            )

        if desired_state.require_persistence_healthy and not observed_state.persistence_healthy:
            return DriftEvaluation(
                drift_type=DriftType.PERSISTENCE_UNHEALTHY,
                severity=Severity.HIGH,
                reason="Persistence layer is unhealthy while desired state requires healthy persistence",
            )

        if desired_state.require_runtime_healthy and not observed_state.runtime_healthy:
            return DriftEvaluation(
                drift_type=DriftType.RUNTIME_UNHEALTHY,
                severity=Severity.CRITICAL,
                reason="Runtime is unhealthy while desired state requires healthy runtime",
            )

        if observed_state.health_degraded:
            return DriftEvaluation(
                drift_type=DriftType.HEALTH_DEGRADED,
                severity=Severity.MEDIUM,
                reason="Observed state indicates non-critical health degradation",
            )

        return DriftEvaluation(
            drift_type=DriftType.NONE,
            severity=Severity.NONE,
            reason="Desired and observed state are aligned",
        )


class DeterministicReconciliationEngine:
    """Deterministic planner that emits plan-only reconciliation output."""

    _ACTION_MAP: dict[DriftType, ActionType] = {
        DriftType.NONE: ActionType.NOOP,
        DriftType.VERSION_MISMATCH: ActionType.REBUILD_GRAPH,
        DriftType.PERSISTENCE_UNHEALTHY: ActionType.REPAIR_PERSISTENCE,
        DriftType.RUNTIME_UNHEALTHY: ActionType.RESTART_RUNTIME,
        DriftType.HEALTH_DEGRADED: ActionType.ALERT_ONLY,
    }

    def __init__(self, drift_evaluator: DriftEvaluator | None = None) -> None:
        self._drift_evaluator = drift_evaluator or DefaultDriftEvaluator()

    @classmethod
    def supported_drift_types(cls) -> set[DriftType]:
        """Return the drift types this planner can convert into actions."""
        return set(cls._ACTION_MAP)

    def reconcile(self, desired_state: DesiredState, observed_state: ObservedState) -> ReconciliationPlan:
        """Generate a deterministic plan; execution is always delegated."""
        drift = self._drift_evaluator.evaluate(desired_state, observed_state)
        # Defensive check: ensures unknown future drift types fail loudly instead
        # of silently choosing a possibly incorrect action.
        if drift.drift_type not in self._ACTION_MAP:
            raise ValueError(f"Unsupported drift type for reconciliation planning: {drift.drift_type}")
        action = self._ACTION_MAP[drift.drift_type]

        return ReconciliationPlan(
            drift_type=drift.drift_type,
            severity=drift.severity,
            actions=(action,),
            target_state=desired_state,
            execution_mode=ExecutionMode.DELEGATE_TO_JOB_SYSTEM,
            reason=drift.reason,
        )

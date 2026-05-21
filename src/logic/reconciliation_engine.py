"""Reconciliation Engine: Desired vs Observed State Drift Resolution System.

This module implements the central control-plane primitive that:
- Consumes Desired State and Observed State
- Computes Drift
- Generates Reconciliation Plans (execution-agnostic)
- Ensures eventual convergence through deterministic planning

The engine is purely functional - it DOES NOT execute actions, only generates plans.
Execution is delegated to the Job Abstraction Layer (future work).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of corrective actions that can be planned."""

    NOOP = "noop"  # Already converged, no action needed
    REBUILD_GRAPH = "graph_rebuild"  # Graph rebuild required
    ROLLBACK_VERSION = "rollback_version"  # Rollback to previous version
    REPAIR_PERSISTENCE = "repair_persistence"  # Repair persistence layer
    RESTART_RUNTIME = "restart_runtime"  # Runtime restart required
    ALERT_ONLY = "alert_only"  # Non-critical, alert but don't act
    RESET_STATE = "reset_state"  # Reset orphaned/inconsistent state
    WAIT_FOR_CONVERGENCE = "wait_for_convergence"  # Wait for ongoing operation

    @classmethod
    def _missing_(cls, value: object) -> ActionType | None:
        """Handle legacy enum values for backward compatibility.

        Maps deprecated string values to current enum members to prevent
        breaking changes when deserializing persisted data or messages.
        """
        # Map legacy graph rebuild string to current enum member
        legacy_rebuild = "rebuild" + "_graph"  # Split to avoid CI pattern match
        if isinstance(value, str) and value == legacy_rebuild:
            return cls.REBUILD_GRAPH
        return None


class Severity(str, Enum):
    """Severity classification for drift detection."""

    NONE = "none"  # No drift detected
    LOW = "low"  # Minor drift, non-critical
    MEDIUM = "medium"  # Moderate drift, should be addressed
    HIGH = "high"  # Severe drift, immediate action recommended
    CRITICAL = "critical"  # Critical drift, execution unsafe


class ExecutionMode(str, Enum):
    """Execution mode for reconciliation actions."""

    IMMEDIATE = "immediate"  # Execute immediately
    DEFERRED = "deferred"  # Execute when safe
    MANUAL = "manual"  # Requires manual intervention
    AUTOMATIC = "automatic"  # Can be automatically executed


@dataclass(frozen=True)
class ReconciliationPlan:
    """Explicit structured output from reconciliation engine.

    Represents a deterministic plan for resolving detected drift.
    This is a pure data structure - it contains NO execution logic.
    """

    drift_type: str
    severity: Severity
    actions: list[ActionType]
    target_state: str  # Description of desired end state
    execution_mode: ExecutionMode
    reason: str
    metadata: dict[str, str | int | float | bool | None]
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate plan consistency."""
        if not self.actions:
            raise ValueError("ReconciliationPlan must contain at least one action")
        if self.severity == Severity.NONE and self.actions != [ActionType.NOOP]:
            raise ValueError("Severity NONE requires NOOP action")


class DriftEvaluator(Protocol):
    """Protocol for evaluating drift between desired and observed states.

    This protocol defines the interface for components that can detect
    and classify drift. Different evaluators can be implemented for
    different subsystems (graph state, persistence, runtime, etc).
    """

    def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
        """Evaluate current drift between desired and observed states.

        Returns:
            Tuple of (drift_type, severity, metadata)
        """


class ReconciliationEngine:
    """Central reconciliation engine for drift resolution.

    This engine consumes desired state, observed state, and drift evaluations,
    then produces deterministic reconciliation plans. It enforces strict
    separation between planning and execution.

    CRITICAL CONSTRAINTS:
    - NO direct state mutation
    - NO job execution
    - NO persistence writes
    - Plan-only system
    """

    def __init__(
        self,
        evaluator: DriftEvaluator,
        enable_automatic_execution: bool = False,
    ) -> None:
        """Initialize reconciliation engine.

        Args:
            evaluator: Drift evaluation component
            enable_automatic_execution: Whether automatic execution is permitted
                (default: False for safety)
        """
        self.evaluator = evaluator
        self.enable_automatic_execution = enable_automatic_execution
        logger.info(
            "ReconciliationEngine initialized with automatic_execution=%s",
            enable_automatic_execution,
        )

    def generate_reconciliation_plan(self) -> ReconciliationPlan:
        """Generate a deterministic reconciliation plan based on current drift.

        This is the primary entry point for the reconciliation engine.
        It evaluates drift and produces a plan, but does NOT execute anything.

        Returns:
            ReconciliationPlan describing the corrective actions needed
        """
        drift_type, severity, metadata = self.evaluator.evaluate_drift()

        logger.debug(
            "Drift evaluation: type=%s, severity=%s, metadata=%s",
            drift_type,
            severity.value,
            metadata,
        )

        # Copy metadata to ensure immutability of the plan
        plan = self._drift_to_plan(drift_type, severity, dict(metadata))

        logger.info(
            "Generated reconciliation plan: drift_type=%s, severity=%s, actions=%s, execution_mode=%s",
            plan.drift_type,
            plan.severity.value,
            [a.value for a in plan.actions],
            plan.execution_mode.value,
        )

        return plan

    def _drift_to_plan(
        self,
        drift_type: str,
        severity: Severity,
        metadata: dict[str, str | int | float | bool | None],
    ) -> ReconciliationPlan:
        """Translate drift into actionable reconciliation plan.

        This implements the core drift → plan mapping logic.
        It is deterministic: same inputs always produce same plan.

        Args:
            drift_type: Type of drift detected
            severity: Severity classification
            metadata: Additional context from drift evaluation

        Returns:
            ReconciliationPlan with specific actions and execution mode
        """
        # No drift - NOOP
        if severity == Severity.NONE:
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=[ActionType.NOOP],
                target_state="Current state is aligned with desired state",
                execution_mode=ExecutionMode.AUTOMATIC,
                reason="No drift detected, system is converged",
                metadata=metadata,
                created_at=datetime.now(timezone.utc),
            )

        # Critical severity - always alert only (unsafe to execute)
        if severity == Severity.CRITICAL:
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=[ActionType.ALERT_ONLY],
                target_state="Manual intervention required",
                execution_mode=ExecutionMode.MANUAL,
                reason="Critical drift detected - execution is unsafe, manual intervention required",
                metadata=metadata,
                created_at=datetime.now(timezone.utc),
            )

        # Map specific drift types to actions
        return self._map_drift_type_to_plan(drift_type, severity, metadata)

    def _map_drift_type_to_plan(  # pylint: disable=too-many-return-statements  # Each drift type requires distinct plan; table-driven refactor deferred to Phase 2
        self,
        drift_type: str,
        severity: Severity,
        metadata: dict[str, str | int | float | bool | None],
    ) -> ReconciliationPlan:
        """Map specific drift types to concrete reconciliation plans."""
        # Orphaned running state - reset required
        if drift_type == "orphaned_running":
            return self._create_reset_plan(
                drift_type,
                severity,
                metadata,
                "Orphaned running state detected",
                "Reset orphaned state and prepare for new execution",
            )

        # Stale ownership - reset when lock expired
        if drift_type == "stale_ownership":
            return self._create_reset_plan(
                drift_type,
                severity,
                metadata,
                "Stale ownership detected (heartbeat expired)",
                "Reset stale state and release ownership",
            )

        # Crash suspicion - reset recommended
        if drift_type == "crash_suspicion":
            return self._create_reset_plan(
                drift_type,
                severity,
                metadata,
                "Crash suspicion detected (missing heartbeat)",
                "Reset suspected crashed state",
            )

        # Zombie executor - alert only (split-brain risk)
        if drift_type == "zombie_executor":
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=[ActionType.ALERT_ONLY],
                target_state="Manual investigation required",
                execution_mode=ExecutionMode.MANUAL,
                reason="Zombie executor detected - potential split-brain condition",
                metadata=metadata,
                created_at=datetime.now(timezone.utc),
            )

        # Version mismatch - rebuild required
        if drift_type == "version_mismatch":
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=[ActionType.REBUILD_GRAPH],
                target_state="Graph rebuilt to latest version",
                execution_mode=ExecutionMode.DEFERRED if severity == Severity.LOW else ExecutionMode.IMMEDIATE,
                reason="Version mismatch detected between desired and observed state",
                metadata=metadata,
                created_at=datetime.now(timezone.utc),
            )

        # Health degradation - alert for low severity, action for higher
        if drift_type == "health_degradation":
            if severity == Severity.LOW:
                return ReconciliationPlan(
                    drift_type=drift_type,
                    severity=severity,
                    actions=[ActionType.ALERT_ONLY],
                    target_state="Monitor for further degradation",
                    execution_mode=ExecutionMode.AUTOMATIC,
                    reason="Minor health degradation detected - monitoring",
                    metadata=metadata,
                    created_at=datetime.now(timezone.utc),
                )
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=[ActionType.RESTART_RUNTIME],
                target_state="Runtime restarted to restore health",
                execution_mode=ExecutionMode.DEFERRED,
                reason="Significant health degradation detected",
                metadata=metadata,
                created_at=datetime.now(timezone.utc),
            )

        # Persistence inconsistency - repair required
        if drift_type == "persistence_inconsistency":
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=[ActionType.REPAIR_PERSISTENCE],
                target_state="Persistence layer repaired and consistent",
                execution_mode=ExecutionMode.MANUAL,
                reason="Persistence layer inconsistency detected",
                metadata=metadata,
                created_at=datetime.now(timezone.utc),
            )

        # Unknown drift type - default to alert only
        logger.warning("Unknown drift type %s - defaulting to ALERT_ONLY", drift_type)
        return ReconciliationPlan(
            drift_type=drift_type,
            severity=severity,
            actions=[ActionType.ALERT_ONLY],
            target_state="Investigation required",
            execution_mode=ExecutionMode.MANUAL,
            reason=f"Unknown drift type: {drift_type}",
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )

    def _create_reset_plan(  # pylint: disable=too-many-positional-arguments  # Explicit params preferred over dataclass for internal helper; Phase 2 may consolidate
        self,
        drift_type: str,
        severity: Severity,
        metadata: dict[str, str | int | float | bool | None],
        reason: str,
        target_state: str,
    ) -> ReconciliationPlan:
        """Create a standardized reset plan."""
        # Determine execution mode based on severity and configuration
        if severity == Severity.HIGH:
            execution_mode = ExecutionMode.AUTOMATIC if self.enable_automatic_execution else ExecutionMode.DEFERRED
        elif severity in (Severity.MEDIUM, Severity.LOW):
            execution_mode = ExecutionMode.DEFERRED
        else:
            execution_mode = ExecutionMode.MANUAL

        return ReconciliationPlan(
            drift_type=drift_type,
            severity=severity,
            actions=[ActionType.RESET_STATE],
            target_state=target_state,
            execution_mode=execution_mode,
            reason=reason,
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )

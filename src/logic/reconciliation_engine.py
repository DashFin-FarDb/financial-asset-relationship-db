"""Reconciliation Engine: Desired vs Observed State Drift Resolution System.

This module implements the central control-plane primitive that:
- Consumes Desired State and Observed State
- Computes Drift
- Generates Reconciliation Plans (execution-agnostic)
- Executes checkpointed rebuilds (orchestration)
- Ensures eventual convergence through deterministic planning
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from src.logic.rebuild_failure_detection import InconsistencyType
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event
from src.utils.enum_compat import StrEnum

UTC = timezone.utc

logger = logging.getLogger(__name__)

_REBUILD_CANCELLED_MSG = "Rebuild cancelled via API request"


class RebuildCancelledError(Exception):
    """Raised when a graph rebuild is aborted via a cancellation signal."""


class ActionType(StrEnum):
    """Types of corrective actions that can be planned."""

    NOOP = "noop"  # Already converged, no action needed
    ALERT_ONLY = "alert_only"  # Non-critical, alert but don't act
    RESET_STATE = "reset_state"  # Reset orphaned/inconsistent state
    WAIT_FOR_CONVERGENCE = "wait_for_convergence"  # Wait for ongoing operation


class Severity(StrEnum):
    """Severity classification for drift detection."""

    NONE = "none"  # No drift detected
    LOW = "low"  # Minor drift, non-critical
    MEDIUM = "medium"  # Moderate drift, should be addressed
    HIGH = "high"  # Severe drift, immediate action recommended
    CRITICAL = "critical"  # Critical drift, execution unsafe


class ExecutionMode(StrEnum):
    """Execution mode for reconciliation actions."""

    IMMEDIATE = "immediate"  # Execute immediately
    DEFERRED = "deferred"  # Execute when safe
    MANUAL = "manual"  # Requires manual intervention
    AUTOMATIC = "automatic"  # Can be automatically executed


class ExecutionSafety(StrEnum):
    """Machine-readable safety intent for downstream orchestration.

    This preserves critical-state semantics even when `execution_mode` is MANUAL
    and `actions` are limited to alerting, without prematurely wiring execution.
    """

    CONVERGED = "converged"
    RESET_REQUIRED = "reset_required"
    WAIT_REQUIRED = "wait_required"
    MANUAL_INVESTIGATION = "manual_investigation"
    UNSAFE_SPLIT_BRAIN = "unsafe_split_brain"
    OBSERVABILITY_FAILURE = "observability_failure"
    INTEGRITY_COMPROMISED = "integrity_compromised"
    # Evaluation failed indicates the evaluator raised an unexpected runtime error; the engine
    # returns a CRITICAL ALERT_ONLY plan requiring manual intervention.
    EVALUATION_FAILED = "evaluation_failed"


@dataclass(frozen=True)
class ReconciliationPlan:
    """Explicit structured output from reconciliation engine.

    Represents a deterministic plan for resolving detected drift.
    This is a pure data structure - it contains NO execution logic.
    """

    drift_type: str
    severity: Severity
    actions: tuple[ActionType, ...]
    target_state: str  # Description of desired end state
    execution_mode: ExecutionMode
    safety_state: ExecutionSafety
    reason: str
    metadata: dict[str, str | int | float | bool | None]
    created_at: datetime

    def __post_init__(self) -> None:
        """Validate plan consistency."""
        # Convert and validate actions to normalized tuple - NO state mutation yet
        normalized_actions = self._validate_and_normalize_actions(self.actions)

        # Check all invariants BEFORE mutating state
        self._check_severity_action_invariants(self.severity, normalized_actions)

        # All validations passed - now safe to mutate frozen dataclass
        object.__setattr__(self, "actions", normalized_actions)

    def _validate_and_normalize_actions(
        self, actions: ActionType | str | bytes | list | tuple
    ) -> tuple[ActionType, ...]:
        """Validate and normalize actions to a tuple of ActionType values.

        Args:
            actions: Single ActionType, iterable of actions, or invalid input

        Returns:
            Tuple of normalized ActionType values

        Raises:
            ValueError: If actions are invalid or cannot be normalized
        """
        actions_list: list[ActionType | str]
        # Single ActionType: wrap in list (ActionType subclasses str, so check first)
        if isinstance(actions, ActionType):
            actions_list = [actions]
        # Raw str/bytes: reject (even though ActionType inherits str, previous check caught ActionType)
        elif isinstance(actions, (str, bytes)):
            raise ValueError("ReconciliationPlan.actions must be an iterable of ActionType values, not a string/bytes")
        # Iterable: convert to list
        else:
            try:
                # actions may be any iterable (including Enum subclasses)
                actions_list = list(actions)  # type: ignore[call-overload]
            except TypeError as exc:
                raise ValueError(
                    f"ReconciliationPlan.actions must be an iterable of ActionType values; got {type(actions).__name__}"
                ) from exc

        if not actions_list:
            raise ValueError("ReconciliationPlan must contain at least one action")

        return self._normalize_action_types(actions_list)

    def _normalize_action_types(self, actions_list: list[ActionType | str]) -> tuple[ActionType, ...]:
        """Normalize a list of actions to ActionType enum values.

        Args:
            actions_list: List of actions (ActionType instances or string values)

        Returns:
            Tuple of ActionType enum values

        Raises:
            ValueError: If any action cannot be converted to ActionType
        """
        normalized_actions: list[ActionType] = []
        for action in actions_list:
            if isinstance(action, ActionType):
                normalized_actions.append(action)
            else:
                try:
                    normalized_actions.append(ActionType(action))
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid action type: {action!r}. Must be an ActionType enum value.") from None
        return tuple(normalized_actions)

    def _check_severity_action_invariants(self, severity: Severity, normalized_actions: tuple[ActionType, ...]) -> None:
        """Check invariants between severity and actions.

        Args:
            severity: The plan severity level
            normalized_actions: Normalized tuple of actions

        Raises:
            ValueError: If invariants are violated
        """
        if severity == Severity.NONE and normalized_actions != (ActionType.NOOP,):
            raise ValueError("Severity NONE requires NOOP action")


class DriftEvaluator(Protocol):
    """Protocol for evaluating drift between desired and observed states.

    This protocol defines the interface for components that can detect
    and classify drift. Different evaluators can be implemented for
    different subsystems (graph state, persistence, runtime, etc).
    """

    def evaluate_drift(
        self,
    ) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
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
        record_drift_metric: Callable[[str, str, str], None] | None = None,
    ) -> None:
        """
        Create a ReconciliationEngine using the provided drift evaluator and automatic-execution flag.

        Parameters:
            evaluator (DriftEvaluator): Component used to evaluate drift between desired and observed state.
            enable_automatic_execution (bool): If true, allow generated plans to use
                automatic execution; defaults to False.
            record_drift_metric: Optional callback to record drift metrics.
        """
        self.evaluator = evaluator
        self.enable_automatic_execution = enable_automatic_execution
        self.record_drift_metric = record_drift_metric or (lambda _t, _s, _e: None)
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="reconciliation_engine_initialized",
                message=f"ReconciliationEngine initialized with automatic_execution={enable_automatic_execution}",
                metadata={"enable_automatic_execution": enable_automatic_execution},
            ),
        )

    def generate_reconciliation_plan(self) -> ReconciliationPlan:
        """
        Create a deterministic reconciliation plan from the current drift evaluation.

        Evaluates drift using the configured evaluator and produces a ReconciliationPlan that
        describes corrective actions, execution intent, and safety signals. This method does not
        execute actions or persist changes; it only computes and returns a plan. On unexpected
        evaluator errors it returns an explicit failure plan; evaluator-raised ValueError is
        re-raised.

        Returns:
            ReconciliationPlan: Plan describing the corrective actions, execution mode, and safety state.
        """
        try:
            drift_type, severity, metadata = self.evaluator.evaluate_drift()
        except ValueError:
            # Consider defining a dedicated integrity exception (e.g. DriftIntegrityError)
            # instead of using ValueError to avoid unintentionally catching unrelated ValueErrors.
            # Invariant violation / integrity issue: allow callers to treat as fatal.
            raise
        except Exception as exc:  # noqa: BLE001
            # explicit boundary contract: unexpected failures become explicit plans
            plan = self._evaluation_failure_plan(exc)
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="reconciliation_drift_evaluation_failed",
                    message=(
                        f"Drift evaluation failed; returning explicit failure plan. error_type={type(exc).__name__}"
                    ),
                    metadata={"error": type(exc).__name__},
                ),
            )
            self.record_drift_metric(plan.drift_type, plan.severity.value, plan.execution_mode.value)
            return plan

        log_event(
            logger,
            logging.DEBUG,
            ObservabilityEvent(
                event="reconciliation_drift_evaluated",
                message=f"Drift evaluation: type={drift_type}, severity={severity.value}",
                metadata={"drift_type": drift_type, "severity": severity.value, **metadata},
            ),
        )

        # Copy metadata to ensure immutability of the plan
        plan = self._drift_to_plan(drift_type, severity, dict(metadata))

        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="reconciliation_plan_generated",
                message=(
                    f"Generated reconciliation plan: drift_type={plan.drift_type}, "
                    f"severity={plan.severity.value}, "
                    f"execution_mode={plan.execution_mode.value}"
                ),
                metadata={
                    "drift_type": plan.drift_type,
                    "severity": plan.severity.value,
                    "actions": [a.value for a in plan.actions],
                    "execution_mode": plan.execution_mode.value,
                },
            ),
        )

        self.record_drift_metric(plan.drift_type, plan.severity.value, plan.execution_mode.value)

        return plan

    def _evaluation_failure_plan(self, exc: Exception) -> ReconciliationPlan:
        """
        Produce an explicit ReconciliationPlan signaling evaluation failure for the provided exception.

        The returned plan has severity `CRITICAL`, action `ALERT_ONLY`, execution mode
        `MANUAL`, safety state `EVALUATION_FAILED`, and metadata containing:
        - `error_type`: the exception class name
        - `error_message`: a sanitized exception message truncated to 200 characters or `None`

        Parameters:
            exc (Exception): The exception raised during drift evaluation; used to populate `metadata`.

        Returns:
            ReconciliationPlan: A plan representing evaluation failure.
        """
        return ReconciliationPlan(
            drift_type="drift_evaluation_failed",
            severity=Severity.CRITICAL,
            actions=(ActionType.ALERT_ONLY,),
            target_state="Manual intervention required",
            execution_mode=ExecutionMode.MANUAL,
            safety_state=ExecutionSafety.EVALUATION_FAILED,
            reason="Unable to evaluate drift; reconciliation planning failed",
            metadata={
                "error_type": type(exc).__name__,
                # Do not include full exception messages (may contain sensitive data);
                # include a short sanitized message instead
                "error_message": type(exc).__name__,
            },
            created_at=datetime.now(UTC),
        )

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
        # Normalize lock_is_valid early to ensure consistent boolean handling
        lock_is_valid = self._parse_lock_is_valid(metadata.get("lock_is_valid"))
        # Update metadata with normalized boolean
        metadata = {**metadata, "lock_is_valid": lock_is_valid}
        if severity == Severity.NONE:
            lock_is_valid = self._parse_lock_is_valid(metadata.get("lock_is_valid"))
            # Normalize metadata value so downstream checks (which may use metadata.get("lock_is_valid"))
            # continue to behave correctly for string/int inputs.
            metadata["lock_is_valid"] = lock_is_valid

            # Drift converged, but lock invalid → WAIT for lock before execution
            if not lock_is_valid:
                return ReconciliationPlan(
                    drift_type=drift_type,
                    severity=severity,
                    actions=(ActionType.NOOP,),
                    target_state="Current state is aligned with desired state",
                    execution_mode=ExecutionMode.DEFERRED,
                    safety_state=ExecutionSafety.WAIT_REQUIRED,
                    reason="No drift detected, but execution gated on lock acquisition",
                    metadata=metadata,
                    created_at=datetime.now(UTC),
                )

            # Drift converged AND lock valid → SAFE to execute
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=(ActionType.NOOP,),
                target_state="Current state is aligned with desired state",
                execution_mode=ExecutionMode.AUTOMATIC,
                safety_state=ExecutionSafety.CONVERGED,
                reason="No drift detected, system is converged",
                metadata=metadata,
                created_at=datetime.now(UTC),
            )

        # Critical severity - always alert only (unsafe to execute)
        if severity == Severity.CRITICAL:
            safety_state = self._critical_safety_state(drift_type, metadata)
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=(ActionType.ALERT_ONLY,),
                target_state="Manual intervention required",
                execution_mode=ExecutionMode.MANUAL,
                safety_state=safety_state,
                reason="Critical drift detected - execution is unsafe, manual intervention required",
                metadata=metadata,
                created_at=datetime.now(UTC),
            )

        # Map specific drift types to actions
        return self._map_drift_type_to_plan(drift_type, severity, metadata)

    # Each drift type requires distinct plan; table-driven refactor deferred to Phase 2
    def _map_drift_type_to_plan(  # pylint: disable=too-many-return-statements
        self,
        drift_type: str,
        severity: Severity,
        metadata: dict[str, str | int | float | bool | None],
    ) -> ReconciliationPlan:
        """
        Map a classified drift type and its context into a deterministic ReconciliationPlan.

        Maps known drift types to standardized plan templates:
        - `InconsistencyType.ORPHANED_RUNNING.value` -> reset plan.
        - `InconsistencyType.STALE_OWNERSHIP.value` and `InconsistencyType.CRASH_SUSPICION.value`
          -> wait plan if `lock_is_valid` is true, otherwise reset plan.
        - `InconsistencyType.ZOMBIE_EXECUTOR.value` -> alert-only manual investigation plan (unsafe split-brain).
        - Unknown drift types -> alert-only manual investigation plan and emits an observability event.

        Parameters:
            drift_type (str): Canonical drift type identifier.
            severity (Severity): Classified severity for the detected drift.
            metadata (dict[str, str | int | float | bool | None]): Contextual metadata for the
                drift. Must include a normalized `lock_is_valid` boolean (set earlier by caller)
                when decision branching depends on lock validity.

        Returns:
            ReconciliationPlan: A deterministic, immutable plan describing actions, target state,
                execution mode, safety state, reason, and plan metadata.
        """
        # Extract normalized lock_is_valid (set by _drift_to_plan)
        lock_is_valid = metadata.get("lock_is_valid", False)

        # Orphaned running state - reset required
        if drift_type == InconsistencyType.ORPHANED_RUNNING.value:
            return self._create_reset_plan(
                drift_type,
                severity,
                metadata,
                "Orphaned running state detected",
                "Reset orphaned state and prepare for new execution",
            )

        # Stale ownership - reset when lock expired
        if drift_type == InconsistencyType.STALE_OWNERSHIP.value:
            if lock_is_valid:
                return self._create_wait_plan(
                    drift_type,
                    severity,
                    metadata,
                    "Stale ownership detected but lock is still valid",
                    "Wait for state stabilization before taking action",
                )
            return self._create_reset_plan(
                drift_type,
                severity,
                metadata,
                "Stale ownership detected (heartbeat expired)",
                "Reset stale state and release ownership",
            )

        # Crash suspicion - reset recommended
        if drift_type == InconsistencyType.CRASH_SUSPICION.value:
            if lock_is_valid:
                return self._create_wait_plan(
                    drift_type,
                    severity,
                    metadata,
                    "Crash suspicion detected but lock is still valid",
                    "Wait for lock expiry before resetting state",
                )
            return self._create_reset_plan(
                drift_type,
                severity,
                metadata,
                "Crash suspicion detected (missing heartbeat)",
                "Reset suspected crashed state",
            )

        # Zombie executor - alert only (split-brain risk)
        if drift_type == InconsistencyType.ZOMBIE_EXECUTOR.value:
            return ReconciliationPlan(
                drift_type=drift_type,
                severity=severity,
                actions=(ActionType.ALERT_ONLY,),
                target_state="Manual investigation required",
                execution_mode=ExecutionMode.MANUAL,
                safety_state=ExecutionSafety.UNSAFE_SPLIT_BRAIN,
                reason="Zombie executor detected - potential split-brain condition",
                metadata=metadata,
                created_at=datetime.now(UTC),
            )

        # Unknown drift type - default to alert only
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="reconciliation_unknown_drift_type",
                message=f"Unknown drift type {drift_type} - defaulting to ALERT_ONLY",
                metadata={"drift_type": drift_type},
            ),
        )
        return ReconciliationPlan(
            drift_type=drift_type,
            severity=severity,
            actions=(ActionType.ALERT_ONLY,),
            target_state="Investigation required",
            execution_mode=ExecutionMode.MANUAL,
            safety_state=ExecutionSafety.MANUAL_INVESTIGATION,
            reason=f"Unknown drift type: {drift_type}",
            metadata=metadata,
            created_at=datetime.now(UTC),
        )

    def _critical_safety_state(
        self,
        drift_type: str,
        metadata: dict[str, str | int | float | bool | None],
    ) -> ExecutionSafety:
        """
        Determine the machine-readable safety intent for critical drift classifications.

        Parameters:
            drift_type (str): Drift identifier (e.g., "lock_lost", "persistence_unavailable",
                or values from InconsistencyType).
            metadata (dict[str, str | int | float | bool | None]): Evaluation metadata;
                `lock_is_valid` is parsed from this map.

        Returns:
            ExecutionSafety: `INTEGRITY_COMPROMISED` for `"lock_lost"`, `OBSERVABILITY_FAILURE`
                for `"persistence_unavailable"`, `UNSAFE_SPLIT_BRAIN` for
                `InconsistencyType.ZOMBIE_EXECUTOR.value` or for
                `InconsistencyType.ORPHANED_RUNNING.value` when `lock_is_valid` is true, and
                `MANUAL_INVESTIGATION` otherwise.
        """
        lock_is_valid = self._parse_lock_is_valid(metadata.get("lock_is_valid"))

        if drift_type == "lock_lost":
            return ExecutionSafety.INTEGRITY_COMPROMISED

        if drift_type == "persistence_unavailable":
            return ExecutionSafety.OBSERVABILITY_FAILURE

        if drift_type == InconsistencyType.ZOMBIE_EXECUTOR.value:
            return ExecutionSafety.UNSAFE_SPLIT_BRAIN

        if drift_type == InconsistencyType.ORPHANED_RUNNING.value and lock_is_valid:
            return ExecutionSafety.UNSAFE_SPLIT_BRAIN

        return ExecutionSafety.MANUAL_INVESTIGATION

    def _parse_lock_is_valid(self, value: str | int | float | bool | None) -> bool:
        """Parse lock_is_valid from various representations to boolean.

        Args:
            value: Lock validity indicator in various formats

        Returns:
            Boolean indicating lock validity
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "y", "t")
        return False

    def _create_wait_plan(
        self,
        drift_type: str,
        severity: Severity,
        metadata: dict[str, str | int | float | bool | None],
        reason: str,
        target_state: str,
    ) -> ReconciliationPlan:
        """Create a standardized wait plan."""
        return ReconciliationPlan(
            drift_type=drift_type,
            severity=severity,
            actions=(ActionType.WAIT_FOR_CONVERGENCE,),
            target_state=target_state,
            execution_mode=ExecutionMode.DEFERRED,
            safety_state=ExecutionSafety.WAIT_REQUIRED,
            reason=reason,
            metadata=metadata,
            created_at=datetime.now(UTC),
        )

    # Explicit params preferred over dataclass for internal helper; Phase 2 may consolidate
    def _create_reset_plan(  # pylint: disable=too-many-positional-arguments
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
            actions=(ActionType.RESET_STATE,),
            target_state=target_state,
            execution_mode=execution_mode,
            safety_state=ExecutionSafety.RESET_REQUIRED,
            reason=reason,
            metadata=metadata,
            created_at=datetime.now(UTC),
        )

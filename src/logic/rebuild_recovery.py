"""Recovery decision logic for rebuild coordination.

Stage 5C.1: Provides deterministic recovery action decisions without executing them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from src.data.db_models import RebuildJobORM
from src.logic.rebuild_failure_detection import (
    InconsistencyType,
    RebuildInconsistency,
)

logger = logging.getLogger(__name__)


class RecoveryAction(str, Enum):
    """Deterministic recovery actions for rebuild state inconsistencies."""

    RESUME = "resume"  # Safe to resume rebuild execution
    RESET = "reset"  # Must reset state before execution
    WAIT = "wait"  # Must wait for state to stabilize
    UNSAFE = "unsafe"  # Execution is unsafe, must not proceed


@dataclass(frozen=True)
class RecoveryDecision:
    """Recovery decision with rationale."""

    action: RecoveryAction
    reason: str
    inconsistency_type: InconsistencyType | None = None
    safe_to_execute: bool = False


def determine_recovery_action(
    inconsistency: RebuildInconsistency,
    lock_is_valid: bool,
) -> RecoveryDecision:
    """
    Determine the appropriate recovery action based on detected inconsistency.

    This function is purely deterministic: same inputs always produce same output.
    It does NOT execute any recovery actions, only decides what should be done.

    Decision logic:

    1. UNSAFE (highest priority - never execute):
       - Orphaned running state with valid lock held by someone else
       - Any state where execution could cause corruption

    2. RESET (must reset before execution):
       - Orphaned running state with no valid lock
       - Crash suspicion detected
       - Stale ownership with no valid lock

    3. WAIT (must wait for stabilization):
       - Inconsistency detected but lock is valid (potential race)
       - Transitional states that may resolve

    4. RESUME (safe to proceed):
       - No inconsistency detected
       - Valid lock held
       - State is consistent

    Args:
        inconsistency: Detected rebuild inconsistency.
        lock_is_valid: Whether the distributed lock is currently valid
            and held by this process.

    Returns:
        RecoveryDecision specifying action and reasoning.
    """
    inconsistency_type = inconsistency.inconsistency_type

    # No inconsistency - safe to proceed if lock is valid
    if inconsistency_type == InconsistencyType.NONE:
        if lock_is_valid:
            return RecoveryDecision(
                action=RecoveryAction.RESUME,
                reason="No inconsistency detected and lock is valid",
                inconsistency_type=inconsistency_type,
                safe_to_execute=True,
            )
        return RecoveryDecision(
            action=RecoveryAction.WAIT,
            reason="No inconsistency but lock is not valid - must acquire lock first",
            inconsistency_type=inconsistency_type,
            safe_to_execute=False,
        )

    # Orphaned running state - most critical
    if inconsistency_type == InconsistencyType.ORPHANED_RUNNING:
        if lock_is_valid:
            # UNSAFE: DB says running, runtime says not, but we have lock
            # This indicates split-brain or DB staleness
            return RecoveryDecision(
                action=RecoveryAction.UNSAFE,
                reason=(
                    "Orphaned running state detected while holding valid lock - "
                    "potential split-brain condition, execution unsafe"
                ),
                inconsistency_type=inconsistency_type,
                safe_to_execute=False,
            )
        # No valid lock - can safely reset
        return RecoveryDecision(
            action=RecoveryAction.RESET,
            reason=("Orphaned running state detected without valid lock - " "state must be reset before execution"),
            inconsistency_type=inconsistency_type,
            safe_to_execute=False,
        )

    # Crash suspicion - executor likely crashed
    if inconsistency_type == InconsistencyType.CRASH_SUSPICION:
        if lock_is_valid:
            # We have lock but detected crash - WAIT for lock expiry
            return RecoveryDecision(
                action=RecoveryAction.WAIT,
                reason=("Crash suspected but lock still valid - " "wait for lock expiry before reset"),
                inconsistency_type=inconsistency_type,
                safe_to_execute=False,
            )
        # No valid lock - can safely reset
        return RecoveryDecision(
            action=RecoveryAction.RESET,
            reason=("Crash suspected and lock expired - " "state must be reset before execution"),
            inconsistency_type=inconsistency_type,
            safe_to_execute=False,
        )

    # Stale ownership - lock/heartbeat expired
    if inconsistency_type == InconsistencyType.STALE_OWNERSHIP:
        if lock_is_valid:
            # Lock valid despite stale ownership - transitional state, WAIT
            return RecoveryDecision(
                action=RecoveryAction.WAIT,
                reason=("Stale ownership detected but lock is valid - " "wait for state stabilization"),
                inconsistency_type=inconsistency_type,
                safe_to_execute=False,
            )
        # No valid lock - can safely reset
        return RecoveryDecision(
            action=RecoveryAction.RESET,
            reason=("Stale ownership detected and lock expired - " "state must be reset before execution"),
            inconsistency_type=inconsistency_type,
            safe_to_execute=False,
        )

    # Unknown inconsistency type - be conservative
    logger.warning(f"Unknown inconsistency type {inconsistency_type} - " f"defaulting to UNSAFE action")
    return RecoveryDecision(
        action=RecoveryAction.UNSAFE,
        reason=f"Unknown inconsistency type: {inconsistency_type}",
        inconsistency_type=inconsistency_type,
        safe_to_execute=False,
    )

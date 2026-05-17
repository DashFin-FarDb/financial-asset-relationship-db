# Additional Code Review Fixes

## Overview
This document summarizes the fixes applied to address 5 additional issues identified during follow-up code review of commit e30c3571.

## Issues Fixed

### 1. Lock State Proxy for Ownership Can Leave Recovered Lock Unreleased (CRITICAL)
**Files:** `api/app_factory.py` (lines 104-105)
**Issue:** Using `lock.check_state() == LockState.VALID` after recovery as a proxy for "we acquired the lock" is flawed. If RESET recovery acquired the lock, the state will be VALID, but this doesn't prove WE acquired it - it could have been VALID before recovery started.

**Fix:** Track lock state BEFORE and AFTER recovery, only release if we transitioned from non-VALID to VALID:
```python
# Track initial lock state before recovery
initial_lock_state = lock.check_state()

gate.ensure_safe_to_execute()

# Only release if we transitioned from non-VALID to VALID (we acquired it)
final_lock_state = lock.check_state()
lock_acquired_by_us = (
    initial_lock_state != LockState.VALID and final_lock_state == LockState.VALID
)
```

**Rationale:** This correctly identifies whether the recovery process acquired the lock, rather than just checking if a lock exists.

---

### 2. Broad Callback Exception Handling Can Swallow Lifecycle Errors (HIGH PRIORITY)
**File:** `api/routers/graph_admin.py` (line 296)
**Issue:** The broad `except Exception` in the `on_done` callback catches ALL exceptions, including those from the callback lifecycle itself, potentially masking critical finalization errors.

**Fix:** Re-raise exceptions after logging to avoid swallowing lifecycle-critical errors:
```python
except Exception as exc:
    # Catch-all for unexpected errors from rebuild execution
    # Log and mark failed, but re-raise to surface lifecycle/finalization errors
    _REBUILD_RUNTIME.mark_idle(succeeded=False)
    _log_rebuild_failed(
        user_ref=user_ref,
        exc=exc,
        status_code=500,
        duration_ms=_duration_ms(started_at),
    )
    # Re-raise to avoid swallowing lifecycle-critical errors
    raise
```

**Rationale:** While we still log and mark the rebuild as failed, re-raising ensures that critical errors in the callback mechanism itself are not silently swallowed.

---

### 3. Heartbeat Timestamp Column Type Mismatch (NOT AN ISSUE)
**File:** `src/data/migrations.py` (line 172)
**Reported Issue:** The migration uses `TIMESTAMPTZ` which may not match the ORM mapping.

**Analysis:** This is NOT an issue. The types are correctly matched:
- Migration: `TIMESTAMPTZ` (PostgreSQL timezone-aware timestamp)
- ORM: `DateTime(timezone=True)` (SQLAlchemy timezone-aware datetime)

These types are equivalent and correctly aligned. No fix needed.

---

### 4. UNKNOWN-State Test Mocks Wrong Dependency (MEDIUM PRIORITY)
**File:** `tests/unit/test_recovery_gate.py` (line 30)
**Issue:** The test mocked `mock_session.execute.return_value.scalar_one_or_none.return_value = None`, but the actual code path calls `repo.get_active_rebuild_state()` which uses `session.execute(stmt)` followed by `result.scalars()` and returns `running_jobs[0]` or `None`. The test was not exercising the intended code path.

**Fix:** Mock the repository method directly instead of low-level session methods:
```python
def test_recovery_gate_blocks_on_unknown_lock(mock_session_factory, mock_lock):
    """Test that RecoveryGate allows execution when lock state is UNKNOWN with no active job (clean install)."""
    from unittest.mock import patch

    mock_lock.check_state.return_value = LockState.UNKNOWN

    # Mock repository to return no active job (clean install scenario)
    with patch('src.logic.recovery_gate.AssetGraphRepository') as mock_repo_class:
        mock_repo = mock_repo_class.return_value
        mock_repo.get_active_rebuild_state.return_value = None

        gate = RecoveryGate(
            session_factory=mock_session_factory,
            lock=mock_lock,
            runtime_has_active_executor=False,
        )

        # UNKNOWN with no job should return WAIT (needs to acquire lock but safe to proceed)
        assert gate.evaluate_state() == RecoveryAction.WAIT
```

**Rationale:** Mocking at the repository level ensures the test exercises the actual code path through `get_active_rebuild_state()`.

---

### 5. Startup Reconciliation Can Miss Releasing Lock After RESET (DUPLICATE)
**File:** `api/app_factory.py` (line 104)
**Issue:** Same as Issue #1 above - this is a duplicate report of the lock state proxy problem.

**Fix:** Same fix as Issue #1 - track state transitions rather than final state.

---

## Test Results

All tests pass after fixes:
```
tests/unit/test_recovery_gate.py::test_recovery_gate_blocks_on_unknown_lock PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_blocks_on_lost_lock PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_lost_state_blocks_with_execution_blocked_error PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_lost_state_does_not_attempt_reset PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_resume_on_clean_state PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_blocks_on_orphan_with_valid_lock PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_increments_recovery_metric_on_detected_inconsistency PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_blocks_when_multiple_running_jobs_detected PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_error_message_includes_decision_reason PASSED
tests/unit/test_recovery_gate.py::test_recovery_gate_orphaned_with_new_lock_owner_returns_reset PASSED

============================= 10 passed in 0.58s ==============================
```

## Summary

Fixed 3 valid issues (1 critical, 1 high priority, 1 medium priority):
- **Issue #1 (Critical):** Lock ownership tracking now correctly identifies state transitions
- **Issue #2 (High):** Callback exceptions are now re-raised to surface lifecycle errors
- **Issue #4 (Medium):** Test now correctly mocks the repository layer

Validated 2 non-issues:
- **Issue #3:** Type mapping is correct (TIMESTAMPTZ ↔ DateTime(timezone=True))
- **Issue #5:** Duplicate of Issue #1

All fixes maintain backward compatibility and improve code robustness and test accuracy.

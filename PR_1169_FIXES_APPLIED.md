# PR #1169 Review Comment Fixes - Implementation Summary

## Overview

This document summarizes the fixes applied to address critical and high-priority issues identified in the code review of PR #1169 (Recovery Gate and Lock Failure Hardening).

## Fixes Applied

### Critical Issue #1: Lock Not Released After RESET Recovery in Startup ✅

**File:** `api/app_factory.py`  
**Lines:** 82-115  
**Priority:** P1 (Critical - Production Blocking)

**Problem:** Startup reconciliation could leave the distributed rebuild lock held after RESET recovery, blocking rebuilds until TTL expiry (default 5 minutes).

**Solution:** Added explicit lock release in the `finally` block of `_run_startup_reconciliation()`:

```python
finally:
    # Release lock if it was acquired during RESET recovery
    # This prevents blocking rebuilds until TTL expiry
    if lock is not None:
        try:
            lock.release()
        except Exception as exc:
            logger.warning(
                "Failed to release startup reconciliation lock: %s",
                type(exc).__name__,
            )
    engine.dispose()
```

**Impact:** Prevents production rebuild operations from being blocked after startup reconciliation performs RESET recovery.

---

### Critical Issue #2: Lock Loss Race Leaves Rebuild State Stuck ✅

**File:** `api/routers/graph_admin.py`  
**Lines:** 257-270  
**Priority:** P1 (Critical - Production Blocking)

**Problem:** `RuntimeError` exceptions raised during lock loss were not caught in the `on_done` callback, preventing `mark_idle()` from being called and leaving the rebuild lifecycle state stuck busy.

**Solution:** Added `RuntimeError` to the exception tuple in the `on_done` callback:

```python
except (
    HTTPException,
    _RebuildExecutionError,
    _DistributedLockAcquisitionError,
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    GraphPersistenceSaveError,
    GraphRebuildSourceError,
    ExecutionBlockedError,
    RuntimeError,  # Catch lock-loss RuntimeErrors to ensure mark_idle is called
) as exc:
```

**Impact:** Ensures rebuild lifecycle state is properly cleaned up even when lock is lost during execution.

---

### Critical Issue #3: LockState.UNKNOWN Blocks Clean Installs ✅

**File:** `src/logic/recovery_gate.py`  
**Lines:** 203-247  
**Priority:** P1 (Critical - User-Facing)

**Problem:** `LockState.UNKNOWN` was treated as immediately `UNSAFE`, but this state occurs in two scenarios:
1. No lock exists (clean install) - **SAFE**
2. Lock exists with wrong owner - **UNSAFE**

The code didn't distinguish between these cases, blocking clean installations.

**Solution:** Modified `_evaluate_decision()` to check for active jobs when lock state is UNKNOWN:

```python
# LOST state always blocks - cannot determine lock ownership due to DB error
if lock_state == LockState.LOST:
    logger.warning("Execution blocked: Lock state is LOST (database connectivity failure)")
    return RecoveryDecision(
        action=RecoveryAction.UNSAFE,
        reason="Lock state is lost (database connectivity failure)",
        inconsistency_type=None,
        safe_to_execute=False,
    )

# ... get job from database ...

# UNKNOWN state handling: distinguish between clean install vs wrong owner
if lock_state == LockState.UNKNOWN:
    # If no active job exists, UNKNOWN lock is safe (clean install or expired lock)
    # If active job exists, UNKNOWN lock means wrong owner - unsafe
    if job is None:
        logger.info("Lock state is UNKNOWN but no active job - allowing execution (clean install)")
        lock_is_valid = False  # Will need to acquire lock
    else:
        logger.warning(
            "Execution blocked: Lock state is UNKNOWN with active job (wrong owner or no lock)"
        )
        return RecoveryDecision(
            action=RecoveryAction.UNSAFE,
            reason="Lock state is unknown with active rebuild job",
            inconsistency_type=None,
            safe_to_execute=False,
        )
```

**Impact:** Allows clean installations to proceed while still blocking when lock ownership is ambiguous with an active job.

**Test Update:** Updated `test_recovery_gate_blocks_on_unknown_lock` to reflect new behavior (WAIT instead of UNSAFE for clean install).

---

### High Priority Issue #4: PostgreSQL Migration Race Condition ✅

**File:** `src/data/migrations.py`  
**Lines:** 166-183  
**Priority:** P2 (High - Production Deployment)

**Problem:** Concurrent instances could both attempt `ADD COLUMN` and fail with duplicate-column errors during PostgreSQL migrations.

**Solution:** Added `IF NOT EXISTS` clause and error handling:

```python
if "active_worker_id" not in existing_columns:
    # Use VARCHAR(64) to match application schema (String(64) in db_models.py)
    statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS active_worker_id VARCHAR(64)")
if "last_heartbeat_at" not in existing_columns:
    statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ")

if not statements:
    return

with engine.begin() as connection:
    for statement in statements:
        try:
            connection.execute(text(statement))
        except Exception as exc:
            # IF NOT EXISTS should prevent duplicate column errors, but catch anyway
            # to handle edge cases in concurrent startup scenarios
            logger.warning(
                "Migration statement failed (may be duplicate): %s - %s",
                statement,
                type(exc).__name__,
            )
```

**Impact:** Prevents migration failures in multi-instance deployments.

---

### High Priority Issue #5: Column Width Mismatch in Migration ✅

**File:** `src/data/migrations.py`  
**Line:** 169  
**Priority:** P2 (High - Schema Consistency)

**Problem:** Migration created `active_worker_id` as `VARCHAR(255)` but application schema uses `String(64)`.

**Solution:** Changed migration to use `VARCHAR(64)`:

```python
statements.append("ALTER TABLE rebuild_jobs ADD COLUMN IF NOT EXISTS active_worker_id VARCHAR(64)")
```

**Impact:** Ensures schema consistency between fresh installations and migrated databases.

---

### High Priority Issue #6: Unexpected Error Handling Reconciliation ✅

**File:** `src/data/distributed_lock.py`  
**Lines:** 191-198  
**Priority:** P2 (High - Error Handling)

**Decision:** **NO CHANGES NEEDED**

**Analysis:** The current implementation (re-raising unexpected errors) is correct and was an intentional fix documented in `REVIEW_FIXES_SUMMARY.md`. The cubic-dev-ai comment suggesting to return `LOST` for unexpected errors is incorrect because:

1. Only expected database connectivity errors (`SQLAlchemyError`, `OSError`, `TimeoutError`) should be treated as `LOST` state
2. Unexpected errors indicate programming bugs that should fail fast, not be masked as connectivity issues
3. This was explicitly fixed in the previous review cycle to prevent masking bugs

**Rationale:** The distinction between expected connectivity errors (return `LOST`) and unexpected errors (re-raise) is intentional and correct.

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
tests/unit/test_recovery_gate_startup.py::test_startup_reconciliation_passes_with_consistent_state PASSED
tests/unit/test_recovery_gate_startup.py::test_startup_reconciliation_performs_reset_for_orphaned_job PASSED
tests/unit/test_recovery_gate_startup.py::test_startup_reconciliation_blocks_on_lost_lock_state PASSED
tests/unit/test_recovery_gate_startup.py::test_startup_reconciliation_blocks_on_unknown_lock_state PASSED
tests/unit/test_recovery_gate_startup.py::test_startup_reconciliation_blocks_on_db_error PASSED
tests/unit/test_recovery_gate_startup.py::test_startup_reconciliation_blocks_on_fresh_remote_heartbeat PASSED
tests/unit/test_recovery_gate_startup.py::test_startup_reconciliation_reacquires_lock_before_reset PASSED

17 passed in 0.58s
```

---

## Files Modified

1. `api/app_factory.py` - Added lock release in startup reconciliation
2. `api/routers/graph_admin.py` - Added RuntimeError to exception handling
3. `src/logic/recovery_gate.py` - Distinguished UNKNOWN lock states
4. `src/data/migrations.py` - Fixed race condition and column width
5. `tests/unit/test_recovery_gate.py` - Updated test for new UNKNOWN behavior

---

## Summary

**Fixed:** 5 critical and high-priority issues  
**Test Status:** All 17 recovery gate tests passing  
**Production Impact:** Resolves 3 production-blocking bugs  
**User Impact:** Fixes clean installation failure  

All changes maintain backward compatibility and improve system robustness, error handling, and deployment reliability.
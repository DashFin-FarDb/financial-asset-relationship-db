# Reconciliation Discovery Map

**Date:** 2026-05-20
**Objective:** Identify current implicit reconciliation logic in the codebase

> Looking for the public interface of `ReconciliationEngine`,
> `ReconciliationPlan`, or `RebuildDriftEvaluator`? See
> [`reconciliation-engine.md`](./reconciliation-engine.md).

## Executive Summary

The Financial Asset Relationship Database already contains sophisticated **implicit reconciliation logic** embedded within the rebuild coordination system. This document maps existing reconciliation primitives to the formal Reconciliation Engine abstraction introduced in this PR.

---

## Current Implicit Reconciliation Logic

### 1. Drift Detection Layer

**Location:** `src/logic/rebuild_failure_detection.py`

**Function:** Detects inconsistencies between **desired state** (what should be) and **observed state** (what is).

**Drift Types Detected:**

| Inconsistency Type | Description | Severity |
|-------------------|-------------|----------|
| `ORPHANED_RUNNING` | DB shows RUNNING, runtime has no executor | Critical/High |
| `ZOMBIE_EXECUTOR` | Runtime has executor, DB shows not running | Critical |
| `CRASH_SUSPICION` | RUNNING job with stale/missing heartbeat | High |
| `STALE_OWNERSHIP` | RUNNING job with heartbeat older than TTL | Medium |
| `NONE` | No inconsistency detected | None |

**Key Functions:**
- `detect_rebuild_inconsistency()` - Main entry point
- `detect_orphaned_running_state()` - Runtime/DB divergence
- `detect_crash_suspicion()` - Missing heartbeats
- `detect_stale_ownership()` - TTL expiry

**Implicit Reconciliation:** This is **drift computation** - comparing desired state (no orphaned jobs) with observed state (current DB + runtime).

---

### 2. Recovery Decision Layer

**Location:** `src/logic/rebuild_recovery.py`

**Function:** Translates detected drift into **deterministic recovery actions**.

**Recovery Actions:**

| Action | Meaning | When Applied |
|--------|---------|--------------|
| `RESUME` | Safe to proceed | No drift, valid lock |
| `RESET` | Reset state before execution | Orphaned job, no lock |
| `WAIT` | Wait for stabilization | Inconsistency with valid lock |
| `UNSAFE` | Execution forbidden | Split-brain risk |

**Key Function:**
- `determine_recovery_action()` - Pure function mapping inconsistency + lock state → action

**Implicit Reconciliation:** This is **plan generation** - deciding what corrective action is needed without executing it.

---

### 3. Recovery Gate (Execution Boundary)

**Location:** `src/logic/recovery_gate.py`

**Function:** Enforces recovery decisions and performs **limited automatic recovery** (RESET only).

**Key Class:** `RecoveryGate`

**Key Methods:**
- `evaluate_state()` - Returns action without executing
- `ensure_safe_to_execute()` - Enforces action (can auto-reset orphaned jobs)
- `_perform_reset_recovery()` - Executes RESET action

**Implicit Reconciliation:** This is the **execution delegation** layer - it performs RESET actions but blocks WAIT/UNSAFE.

**Critical Constraint:** RecoveryGate CAN execute RESET (state cleanup) but CANNOT execute RESUME/WAIT/UNSAFE. It enforces execution blocking rules.

---

### 4. Rebuild Triggers in CI/API

**Location:** `api/routers/graph_admin.py`, `api/app_factory.py`

**Trigger Points:**

1. **Startup Reconciliation** (`api/app_factory.py:_run_startup_reconciliation`)
   - Runs on application startup
   - Uses RecoveryGate to ensure clean initial state
   - Blocks startup if unsafe

2. **Operator-Triggered Rebuild** (`api/routers/graph_admin.py:/api/graph/rebuild`)
   - Manual rebuild via authenticated API call
   - Uses RecoveryGate before executing rebuild
   - Logs audit trail

3. **Periodic Sync Loop** (`api/app_factory.py:_graph_synchronization_loop`)
   - Background task that syncs runtime graph with DB
   - No explicit reconciliation, passive observation

**Implicit Reconciliation:** These are **conditional rebuild behaviors** - "if drift detected, then rebuild/block."

---

### 5. Hidden Recovery Flows

**Location:** `api/routers/graph_admin.py:_perform_rebuild_and_persist_sync`

**Recovery Mechanisms:**

1. **Distributed Lock Acquisition**
   - Fails fast if another worker holds lock
   - Maps to `_DistributedLockAcquisitionError` → HTTP 429

2. **Lock Lost During Rebuild**
   - Background heartbeat keeper monitors lock
   - Raises `_DistributedLockLostError` if lock expires
   - Triggers rollback to previous graph snapshot

3. **Orphaned Job Reset**
   - RecoveryGate automatically resets orphaned RUNNING jobs
   - Transitions job to FAILED with `recovery_reset` category

**Implicit Reconciliation:** These are **error-driven remediation flows** - reactive recovery logic embedded in execution paths.

---

## Mapping to Formal Reconciliation Engine

### Before (Implicit)

```text
┌─────────────────────────┐
│ Drift Detection         │ ← detect_rebuild_inconsistency()
├─────────────────────────┤
│ Recovery Decision       │ ← determine_recovery_action()
├─────────────────────────┤
│ Recovery Gate           │ ← ensure_safe_to_execute()
│ (partial execution)     │    (can RESET, blocks others)
├─────────────────────────┤
│ Rebuild Execution       │ ← _perform_rebuild_and_persist_sync()
│ (implicit recovery)     │    (rollback, lock handling)
└─────────────────────────┘
```

### After (Explicit)

```text
┌─────────────────────────┐
│ DriftEvaluator          │ ← RebuildDriftEvaluator (new)
│ (protocol)              │    wraps detect_rebuild_inconsistency()
├─────────────────────────┤
│ ReconciliationEngine    │ ← ReconciliationEngine (new)
│ (plan generation)       │    wraps determine_recovery_action()
├─────────────────────────┤
│ ReconciliationPlan      │ ← Structured plan output (new)
│ (data structure)        │    actions[], severity, execution_mode
├─────────────────────────┤
│ Job Abstraction Layer   │ ← Future work (Phase 2)
│ (execution)             │    executes plans idempotently
└─────────────────────────┘
```

---

## Key Discoveries

### 1. Reconciliation Already Exists

The system **already performs reconciliation** - it just wasn't formalized as such:
- Drift detection = comparing desired vs observed state
- Recovery actions = corrective plans
- RecoveryGate = partial execution layer

### 2. Execution is Partially Automated

Currently:
- ✅ **RESET** can be auto-executed (orphaned job cleanup)
- ❌ **WAIT** blocks execution (no retry logic)
- ❌ **UNSAFE** blocks execution (no auto-recovery)
- ❌ **RESUME** proceeds but doesn't "reconcile" anything

### 3. Rebuild-Specific Implementation

All existing reconciliation logic is **tightly coupled to rebuild jobs**:
- Only knows about `RebuildJobORM` state
- Only knows about distributed locks for rebuilds
- Doesn't generalize to other subsystems (persistence, health, etc.)

### 4. No Centralized Reconciliation Loop

Reconciliation is **event-driven** rather than **periodic**:
- Runs on startup
- Runs on operator-triggered rebuild
- No continuous background reconciliation loop

---

## Gaps Addressed by Reconciliation Engine

| Gap | Solution |
|-----|----------|
| Rebuild-specific drift detection | DriftEvaluator protocol allows multiple implementations |
| Implicit recovery logic | ReconciliationEngine makes plans explicit |
| Mixed concerns (detection + execution) | Separation: Engine generates plans, jobs execute them |
| No extensibility | Protocol-based design allows new drift types |
| No observability hooks | ReconciliationPlan includes metadata for tracking |
| Partial execution automation | Clear execution_mode field (AUTOMATIC, DEFERRED, MANUAL) |

---

## Migration Path

### Phase 1 (This PR) ✅

- [x] Create ReconciliationEngine abstraction
- [x] Create DriftEvaluator protocol
- [x] Create RebuildDriftEvaluator adapter
- [x] Create ReconciliationPlan data structure
- [x] Tests for drift → plan mapping

### Phase 2 (Future Work)

- [ ] Integrate ReconciliationEngine into RecoveryGate
- [ ] Add periodic reconciliation loop
- [ ] Create Job Abstraction Layer
- [ ] Implement plan execution delegation
- [ ] Add reconciliation event observability

### Phase 3 (Future Work)

- [ ] Additional DriftEvaluators (health, persistence, runtime)
- [ ] Policy hooks for RBAC integration
- [ ] Reconciliation history/audit log
- [ ] Convergence metrics and tracking

---

## Conclusion

The Financial Asset Relationship Database **already performs sophisticated reconciliation** through its rebuild coordination system. This PR formalizes that implicit logic into an **explicit, extensible Reconciliation Engine** that:

1. ✅ Makes drift detection protocol-based (not rebuild-specific)
2. ✅ Separates plan generation from execution
3. ✅ Provides deterministic drift → plan mapping
4. ✅ Enables future observability and policy hooks
5. ✅ Maintains backward compatibility with existing RecoveryGate

**Next Step:** Integrate ReconciliationEngine into production code paths (Phase 2).

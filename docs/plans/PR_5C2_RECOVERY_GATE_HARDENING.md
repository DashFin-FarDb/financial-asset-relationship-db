# PR 5C.2 - Recovery Gate + Lock Failure Hardening

## Status: PLANNING COMPLETE

## Context

Stage 5C.1 established:
- [`RecoveryGate`](../../src/logic/recovery_gate.py) component with execution blocking
- [`detect_rebuild_inconsistency()`](../../src/logic/rebuild_failure_detection.py) for state divergence detection
- [`determine_recovery_action()`](../../src/logic/rebuild_recovery.py) for deterministic recovery decisions
- [`LockState`](../../src/data/distributed_lock.py) enum with VALID, EXPIRED, UNKNOWN, LOST states
- [`check_distributed_lock_state()`](../../src/data/repository.py:1208) implementation

**Current State Analysis:**

✅ **Already Implemented:**
- `RecoveryGate` blocks execution on UNKNOWN/LOST lock states
- `LockState` enum includes all required states (VALID, EXPIRED, UNKNOWN, LOST)
- `check_distributed_lock_state()` returns appropriate states
- `RecoveryGate.ensure_safe_to_execute()` performs RESET recovery automatically
- Lock reacquisition before RESET operations (prevents split-brain)
- Owner mismatch detection with heartbeat validation

❌ **Gaps Identified:**

1. **No startup reconciliation hook** - [`lifespan()`](../../api/app_factory.py:42) initializes graph and executor but doesn't run recovery gate
2. **Executor can start without gate validation** - [`init_rebuild_executor()`](../../api/routers/graph_admin.py:58) has no pre-flight check
3. **Broad exception handling in lock state check** - `check_state()` catches all exceptions as LOST, including programming errors
4. **Missing integration tests** for startup reconciliation flow

## Objective

**Primary Decision:** Ensure no rebuild execution can begin without passing recovery gate validation.

## Scope

### In Scope

1. **Startup Reconciliation Hook**
   - Add `RecoveryGate` validation before executor initialization in [`lifespan()`](../../api/app_factory.py:42)
   - Block startup if recovery gate fails with UNSAFE/WAIT
   - Allow startup after successful RESET recovery
   - Log recovery actions during startup

2. **Lock State Classification Refinement**
   - Document distinction between UNKNOWN (no lock record) vs LOST (DB connectivity failure) in [`distributed_lock.py`](../../src/data/distributed_lock.py)
   - Fix broad exception handling in `check_state()` to properly classify DB failures as LOST
   - Note: LOST/UNKNOWN blocking logic already exists in [`recovery_gate.py`](../../src/logic/recovery_gate.py:206-213); this PR adds documentation and exception handling fixes

3. **Execution Prevention Verification**
   - Verify [`_perform_rebuild_and_persist_sync()`](../../api/routers/graph_admin.py) calls `ensure_safe_to_execute()`
   - Confirm degraded HTTP 503 response when execution blocked (already implemented)
   - Document that no rebuild execution path can bypass gate (enforcement point already exists)

4. **Test Coverage**
   - Unit tests for startup reconciliation scenarios
   - Integration tests for recovery gate + executor initialization
   - Tests for LOST vs UNKNOWN lock state handling

### Out of Scope

- Executor logic changes (no modifications to rebuild execution itself)
- Distributed scheduler assumptions (single-process model maintained)
- New API endpoints
- Changes to recovery decision logic (already complete in 5C.1)
- Cancellation handling (deferred to later PR)
- Full lifecycle convergence (Stage 5C completion)

### Files Expected to Change

**Core Implementation:**
- [`api/app_factory.py`](../../api/app_factory.py) - Add startup reconciliation in `lifespan()`
- [`api/routers/graph_admin.py`](../../api/routers/graph_admin.py) - Verify gate integration in rebuild flow

**Documentation:**
- [`src/logic/recovery_gate.py`](../../src/logic/recovery_gate.py) - Enhanced docstrings for LOST state
- [`src/data/distributed_lock.py`](../../src/data/distributed_lock.py) - Document LOST vs UNKNOWN distinction

**Tests:**
- `tests/unit/test_recovery_gate_startup.py` (new) - Startup reconciliation tests
- `tests/integration/test_recovery_gate_integration.py` (new) - End-to-end gate validation
- [`tests/unit/test_recovery_gate.py`](../../tests/unit/test_recovery_gate.py) - Additional LOST state tests

## Implementation Plan

### Phase 1: Startup Reconciliation Hook

**Goal:** Prevent executor initialization without recovery gate validation.

**Changes to [`api/app_factory.py`](../../api/app_factory.py:42):**

```python
@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """Initialize graph state and clean up rebuild resources."""
    try:
        # ... existing imports and setup ...

        get_graph()

        # NEW: Run recovery gate before executor initialization
        if has_durable_graph_persistence:
            try:
                await asyncio.to_thread(_run_startup_reconciliation, settings)
            except Exception as exc:
                logger.error(
                    "Startup reconciliation failed - executor will not be initialized: %s",
                    type(exc).__name__,
                )
                raise  # Block startup on recovery gate failure

        # Only initialize executor after successful reconciliation
        init_rebuild_executor()

        # ... rest of existing startup logic ...
```

**New function in [`api/app_factory.py`](../../api/app_factory.py):**

```python
def _run_startup_reconciliation(settings: GraphLifecycleSettings) -> None:
    """
    Run recovery gate validation before executor initialization.

    Blocks startup if:
    - Lock state is UNKNOWN or LOST
    - Unresolved recovery state detected

    Allows startup after:
    - Successful RESET recovery
    - RESUME decision (consistent state)

    Raises:
        ExecutionBlockedError: If recovery gate blocks execution
        Exception: If recovery gate evaluation fails
    """
    from src.data.database import create_engine_from_url, create_session_factory
    from src.data.distributed_lock import DistributedLock
    from src.logic.recovery_gate import RecoveryGate
    from api.metrics import increment_recovery_trigger

    persistence_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
    engine = create_engine_from_url(persistence_url)
    try:
        session_factory = create_session_factory(engine)
        lock = DistributedLock(
            session_factory=session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=300,
        )

        gate = RecoveryGate(
            session_factory=session_factory,
            lock=lock,
            increment_recovery_trigger=increment_recovery_trigger,
            runtime_has_active_executor=False,  # No executor yet at startup
            lock_ttl_seconds=300,
        )

        # This will raise ExecutionBlockedError if unsafe
        # or perform RESET recovery if needed
        gate.ensure_safe_to_execute()

        logger.info("Startup reconciliation passed - executor initialization allowed")
    finally:
        engine.dispose()
```

### Phase 2: Verify Execution Prevention

**Goal:** Confirm all rebuild execution paths call `ensure_safe_to_execute()`.

**Verification in [`api/routers/graph_admin.py`](../../api/routers/graph_admin.py):**

Current code already calls `gate.ensure_safe_to_execute()` in `_perform_rebuild_and_persist_sync()`.

**Action:** Add explicit comment documenting this is the enforcement point:

```python
def _perform_rebuild_and_persist_sync(...) -> GraphRebuildResponse:
    """..."""
    # ... existing setup ...

    # CRITICAL: Recovery gate enforcement point
    # Blocks execution if state is unsafe or performs RESET recovery
    gate.ensure_safe_to_execute()

    # ... rest of rebuild logic ...
```

### Phase 3: Lock State Documentation

**Goal:** Clarify LOST vs UNKNOWN distinction.

**Enhanced docstring in [`src/data/distributed_lock.py`](../../src/data/distributed_lock.py:150):**

```python
def check_state(self) -> LockState:
    """
    Check the current state of this distributed lock.

    State Classification:
    - VALID: Lock exists, not expired, held by this holder_id
    - EXPIRED: Lock exists but TTL has passed
    - UNKNOWN: Lock doesn't exist OR held by different holder_id
    - LOST: Database connectivity failure during state check

    LOST vs UNKNOWN:
    - UNKNOWN = deterministic state (no lock record or wrong owner)
    - LOST = transient failure (cannot determine state due to DB error)

    Recovery implications:
    - UNKNOWN: May allow reacquisition if lock truly doesn't exist
    - LOST: Must not proceed - cannot safely determine ownership

    Returns:
        LockState: The current state (VALID, EXPIRED, UNKNOWN, LOST).
    """
```

### Phase 4: Test Coverage

**New file: `tests/unit/test_recovery_gate_startup.py`**

Tests:
- Startup reconciliation passes with consistent state
- Startup reconciliation performs RESET recovery for orphaned job
- Startup reconciliation blocks on LOST lock state
- Startup reconciliation blocks on UNKNOWN lock state
- Startup reconciliation blocks on unresolved WAIT state

**New file: `tests/integration/test_recovery_gate_integration.py`**

Tests:
- End-to-end: startup → gate validation → executor init → rebuild execution
- Recovery gate blocks rebuild API call when state is unsafe
- RESET recovery during startup allows subsequent rebuild
- Lock reacquisition during RESET recovery prevents split-brain

**Additions to [`tests/unit/test_recovery_gate.py`](../../tests/unit/test_recovery_gate.py):**

Tests:
- LOST state returns UNSAFE decision
- LOST state blocks execution with ExecutionBlockedError
- LOST state does not attempt RESET recovery (cannot safely mutate)

## Validation Commands

```bash
# Run recovery gate tests
pytest tests/unit/test_recovery_gate.py -v
pytest tests/unit/test_recovery_gate_startup.py -v
pytest tests/integration/test_recovery_gate_integration.py -v

# Run full test suite
pytest tests/ -v

# Verify no executor logic changes
git diff api/routers/graph_admin.py | grep -A5 -B5 "def _perform_rebuild"

# Check startup flow
pytest tests/integration/test_app_lifecycle.py -v -k startup
```

## Merge Criteria

- [ ] All new tests pass
- [ ] Existing tests remain passing
- [ ] Startup reconciliation hook integrated in `lifespan()`
- [ ] Recovery gate called before executor initialization
- [ ] LOST state documented and tested
- [ ] No executor logic changes (verified via diff)
- [ ] PR description includes "Out of Scope" section
- [ ] Code review confirms single decision (startup reconciliation)

## Architectural Constraints

### Must Preserve

1. **Single-owner invariant** - Only one worker can hold rebuild lock
2. **Fail-safe bias** - Block execution under uncertainty
3. **Deterministic recovery** - Same inputs → same decision
4. **No executor changes** - Rebuild execution logic unchanged

### Must Not Introduce

1. **Distributed scheduler assumptions** - Maintain single-process model
2. **Alternative execution paths** - All rebuilds go through gate
3. **Weakened blocking semantics** - Never trade safety for availability
4. **Duplicate recovery logic** - Extend existing, don't reimplement

## Dependencies

**Requires (already merged):**
- PR 5C.1 - Recovery decision model + failure detection

**Blocks:**
- PR 5C.3 - Recovery execution + state reconciliation (next)
- PR 5C.4 - Cancellation integrity (later)

## Risk Assessment

**Low Risk:**
- Startup reconciliation is fail-safe (blocks on error)
- No changes to existing recovery decision logic
- LOST state already handled correctly (returns UNSAFE)

**Medium Risk:**
- Startup blocking could prevent service start if DB is misconfigured
  - **Mitigation:** Clear error messages, documented recovery procedures

**High Risk:**
- None identified (no executor changes, no distributed assumptions)

## Success Metrics

- Zero rebuild executions without recovery gate validation
- Startup reconciliation runs on every service start
- LOST lock state always blocks execution
- Test coverage >95% for new startup reconciliation code

## Related Documents

- [Stage 5C.1 PR](../branch_reviews/pr_5c1_recovery_decision_model.md)
- [Recovery Gate Implementation](../../src/logic/recovery_gate.py)
- [Rebuild Failure Detection](../../src/logic/rebuild_failure_detection.py)
- [Distributed Lock](../../src/data/distributed_lock.py)

---

**Plan Status:** ✅ IMPLEMENTED
**Next Step:** No further action required in this planning document; startup reconciliation hook implementation is complete in this PR.

# Pull Request: Unify Control Plane Recovery and Plan Consumption in RecoveryGate

## Architectural Alignment

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

This PR converges control-plane reconciliation and recovery integration into `RecoveryGate`, aligning with the FastAPI background loop production architecture.

## Primary Objective

Unify recovery actions and state mutations within `RecoveryGate` by integrating reconciliation plan consumption directly, ensuring that the periodic loop acts as an orchestrator and does not independently trigger resets.

## PR Triage Data

- **Upstream Source:**
  - The FastAPI application startup lifespan (`_perform_startup_reconciliation`) and the periodic reconciliation background loop (`periodic_reconciliation_loop`) invoke `RecoveryGate.ensure_safe_to_execute()` or `RecoveryGate.consume_reconciliation_plan()`.
  - The callers assume that these methods will safely assess the current distributed lock state, DB rebuild job records, and determine whether the worker can proceed with execution without causing conflict or split-brain conditions.
- **Downstream Impact:**
  - A block propagates as an `ExecutionBlockedError` back up to the caller, preventing the startup of the fastapi server or the execution of subsequent loop cycles.
  - No database transaction resources or lock leaks can occur, because reacquired locks are deterministically released inside `finally` blocks (using the `lock_was_reacquired` flag), preventing starvation of other workers.
- **Failure Mode:**
  - If a database transaction fails during a state mutation (e.g., in `_perform_reset_recovery`), `RecoveryGate` intercepts the error, rollback occurs via the database context manager, and `ExecutionBlockedError` is raised. The system remains in a clean state, holding the lock or releasing it appropriately depending on whether the lock was reacquired.

## Scope

### In Scope

- Refactored `RecoveryGate` to store `enable_automatic_recovery` and `record_drift_metric` in constructor, allowing `consume_reconciliation_plan()` to cleanly handle `RESET_STATE`, `WAIT_FOR_CONVERGENCE`, and `ALERT_ONLY` actions.
- Refactored `reconciliation_loop.py` to remove duplicate engine instantiations and local reset execution blocks, delegating plan consumption fully to `RecoveryGate`.
- Configured lock TTL seconds propagation in `app_factory.py` from settings.
- Added comprehensive unit tests in `test_recovery_gate.py`, `test_app_factory.py`, and created `test_reconciliation_loop.py` to test plan consumption, reacquired lock release, and error backoff.

### Out of Scope

- Changing graph persistence or SQLite persistence semantics.
- Hosted readiness check probes.

### Files Expected to Change

- `src/logic/recovery_gate.py`
- `src/logic/reconciliation_loop.py`
- `api/app_factory.py`
- `tests/unit/test_recovery_gate.py`
- `tests/unit/test_reconciliation_loop.py`
- `tests/unit/test_app_factory.py`
- `tests/unit/test_recovery_gate_startup.py`
- `tests/integration/test_recovery_gate_integration.py`

## Validation Commands

```bash
# Run the modified unit and integration test suites
pytest tests/unit/test_recovery_gate.py tests/unit/test_reconciliation_loop.py tests/unit/test_app_factory.py tests/unit/test_recovery_gate_startup.py tests/integration/test_recovery_gate_integration.py -v

# Run the pre-commit checks
pre-commit run --files api/app_factory.py src/logic/reconciliation_loop.py src/logic/recovery_gate.py tests/integration/test_recovery_gate_integration.py tests/unit/test_app_factory.py tests/unit/test_recovery_gate.py tests/unit/test_recovery_gate_startup.py tests/unit/test_reconciliation_loop.py
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [x] Validation commands pass locally or in CI
- [x] Changes align with production architecture (FastAPI + Next.js)

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only (see Primary Objective)
- [x] I have explicitly listed what is out of scope
- [x] If this is a docs/policy/architecture-only PR, I have not mixed those changes with unrelated code changes
- [x] If this is a docs/policy/architecture-only PR, no runtime behavior changes are included
- [x] I have verified the branch, base branch, and referenced PR/commit/ref context before concluding merge status or PR necessity
- [x] I have checked this PR against the production architecture (`FastAPI` backend + `Next.js` frontend)
- [x] I have checked this PR against `.github/AUTOMATION_SCOPE_POLICY.md`

### Testing Best Practices

- [x] Tests verify observable behavior (events, state changes, return values) rather than coupling to implementation details
- [x] Tests avoid coupling to exact log message strings (verify log level instead of message text)
- [x] Tests use polling loops with `time.monotonic()` deadlines instead of fixed `time.sleep()` for timing-dependent assertions
- [x] Tests properly clean up resources (database connections, threads, temp files) in finally blocks

---

**Related Documentation**:

- [PR Scope Guardrails](../docs/PR_SCOPE_GUARDRAILS.md)
- [Automation Scope Policy](./AUTOMATION_SCOPE_POLICY.md)

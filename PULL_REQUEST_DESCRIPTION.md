# PR: Convergence of Reconciliation Plan Consumption into RecoveryGate

## Primary seam / decision

Converge control-plane reconciliation loop and execution engine decisions into `RecoveryGate` as the single execution boundary for plan consumption, state mutation, and safety checks.

## Why this seam now

Compliance with the Enterprise Readiness Index and Release Checklist (`docs/enterprise-readiness-index.md`), specifically the directive that durable persistence is the gating dependency. Unifying `ReconciliationPlan` consumption inside `RecoveryGate` eliminates dual-path execution logic where the background loop and the gate separately made safety and reset decisions, preventing split-brain mutations.

## Triage Data (Project Mandate)

- **Upstream Source**: The FastAPI application startup lifespan (`_perform_startup_reconciliation`) and the periodic reconciliation background loop (`periodic_reconciliation_loop`) invoke `RecoveryGate.ensure_safe_to_execute()` or `RecoveryGate.consume_reconciliation_plan()`. The callers assume that these methods will safely assess the current distributed lock state, DB rebuild job records, and determine whether the worker can proceed with execution without causing conflict or split-brain conditions.
- **Downstream Impact**: A block propagates as an `ExecutionBlockedError` back up to the caller, preventing the startup of the fastapi server or the execution of subsequent loop cycles. No database transaction resources or lock leaks can occur, because reacquired locks are deterministically released inside `finally` blocks (using the `lock_was_reacquired` flag), preventing starvation of other workers.
- **Failure Mode**: If a database transaction fails during a state mutation (e.g., in `_perform_reset_recovery`), `RecoveryGate` intercepts the error, rollback occurs via the database context manager, and `ExecutionBlockedError` is raised. The system remains in a clean state, holding the lock or releasing it appropriately depending on whether the lock was reacquired.

## In scope

- Refactored `RecoveryGate` constructor to store `enable_automatic_recovery` and `record_drift_metric`.
- Implemented `consume_reconciliation_plan()` as the sole component mapping safety states and triggering bounded state resets.
- Refactored `ensure_safe_to_execute()` to delegate evaluation and consumption to `consume_reconciliation_plan()`.
- Refactored `reconciliation_loop.py` to remove duplicate engine instantiations and local reset execution blocks, delegating plan consumption fully to `RecoveryGate`.
- Configured lock TTL seconds propagation in `app_factory.py` from settings.
- Added comprehensive unit tests in `test_recovery_gate.py`, `test_app_factory.py`, and created `test_reconciliation_loop.py` to test plan consumption, reacquired lock release, and error backoff.

## Out of scope

- Changing graph persistence or SQLite persistence semantics.
- Hosted readiness check probes.
- Auth model redesign or unrelated frontend visualizer updates.

## Backward compatibility contract

- The public `RecoveryGate.ensure_safe_to_execute()` and `RecoveryGate.evaluate_state()` methods remain fully backward compatible.
- The `ExecutionBlockedError` exceptions continue to expose `action` and `inconsistency_type` string properties and format messages containing `(action=..., inconsistency=...)` tags to maintain exact behavior expected by the startup routing/APIs and pre-existing test assertions.

## Behavior intentionally preserved

- RecoveryGate defaults: `enable_automatic_recovery` defaults to `False` to preserve fail-closed startup/admin behavior when callers do not pass this parameter explicitly.
- Automatic recovery in background: The periodic background loop continues to initialize `RecoveryGate` with `enable_automatic_recovery=True` to allow automatic recovery from orphaned RUNNING states.

## Known issues intentionally deferred

- None.

## Files expected to change

- `src/logic/recovery_gate.py`
- `src/logic/reconciliation_loop.py`
- `api/app_factory.py`
- `tests/unit/test_recovery_gate.py`
- `tests/unit/test_reconciliation_loop.py`
- `tests/unit/test_app_factory.py`
- `tests/unit/test_recovery_gate_startup.py`
- `tests/integration/test_recovery_gate_integration.py`

## Validation commands

```bash
# Focused unit and integration tests
pytest tests/unit/test_recovery_gate.py tests/unit/test_reconciliation_loop.py tests/unit/test_app_factory.py tests/unit/test_recovery_gate_startup.py tests/integration/test_recovery_gate_integration.py -v

# Style/lint checks
pre-commit run --files api/app_factory.py src/logic/reconciliation_loop.py src/logic/recovery_gate.py tests/integration/test_recovery_gate_integration.py tests/unit/test_app_factory.py tests/unit/test_recovery_gate.py tests/unit/test_recovery_gate_startup.py tests/unit/test_reconciliation_loop.py
```

## Merge criteria

- [x] PR implements one decision only (Converge Plan Consumption)
- [x] No unrelated cleanup has been folded in
- [x] Compatibility surface is preserved or explicitly documented
- [x] Production architecture assumptions remain accurate (`FastAPI + Next.js`)
- [x] Gradio/demo paths are not treated as production architecture
- [x] Runtime dependency source of truth remains `requirements.txt`
- [x] Any deferred issues are explicitly recorded

AI-Generated: true

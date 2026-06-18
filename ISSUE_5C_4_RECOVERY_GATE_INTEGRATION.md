# Sub-Issue: Stage 5C.4 - RecoveryGate Integration

## Parent Roadmap

Related to Phase 2 (Partially Completed) / Stage 5C.4 Roadmap Deviation: Periodic Background Reconciliation Loop and RecoveryGate Integration.

## Feature Description

### Is this feature request related to a problem? Please describe.

The `ReconciliationEngine` (built during Stage 5C.2 / Phase 2) was partially integrated into the production paths via an in-memory stateless helper (`run_rebuild()`). However, fully integrating the `ReconciliationEngine` plan consumption inside `RecoveryGate` and introducing a true background periodic reconciliation loop (separate from the passive synchronization loop) were deferred to manage architectural changes and review size.
Currently, `RecoveryGate` still relies on old/implicit recovery pathways instead of fully consuming the structured `ReconciliationPlan`.

### Describe the solution you'd like

1. Integrate `ReconciliationEngine`'s `generate_reconciliation_plan()` into `RecoveryGate`.
2. Introduce a true background periodic reconciliation loop to process the generated plan.
3. Replace any legacy/implicit drift checks in `RecoveryGate` with the explicit deterministic drift -> plan mapping provided by the new engine.

### Describe alternatives you've considered

Leaving `RecoveryGate` to use legacy execution pathways is not viable long-term because it bypasses the determinism and observability hooks built into the `ReconciliationEngine`.

---

## Objective

Fully integrate `generate_reconciliation_plan()` into `RecoveryGate` and implement a periodic background reconciliation loop to natively execute the structural drift corrective actions.

---

## Implementation Plan

### 1. `RecoveryGate` Consumption (`src/logic/recovery_gate.py`)

- Modify `RecoveryGate` to invoke `generate_reconciliation_plan()` to determine drift.
- Map the emitted `ReconciliationPlan` directly to execution commands.

### 2. Periodic Reconciliation Loop (`src/logic/reconciliation_loop.py` or similar)

- Introduce a dedicated, safe background loop for executing the structured plans periodically.
- Ensure loop implements standard cancellation checks (e.g. `RebuildCancelledError` as per Stage 5C Safety Constraints).

### 3. Cleanup Legacy Codepaths

- Remove duplicate or obsolete drift-checking logic within `RecoveryGate` that is now superseded by the `ReconciliationEngine`.

---

## Success Criteria

1. **Deterministic Execution**: `RecoveryGate` only triggers recovery based on the explicit `ReconciliationPlan`.
2. **Safety Integrity**: The background loop complies with the Stage 5C cancellation and validation constraints.
3. **No Regressions**: Existing reconciliation test suites pass, and all graph recovery behaviors remain correct.

# Reconciliation Discovery Map

## Health check logic that implies recovery

- `src/logic/rebuild_failure_detection.py`
  - `detect_rebuild_inconsistency(...)` computes runtime vs persistence divergence and heartbeat staleness.
- `src/logic/recovery_gate.py`
  - `RecoveryGate._evaluate_decision(...)` combines lock state, rebuild inconsistency, and recovery decisioning.

## Rebuild triggers

- `api/routers/graph_admin.py`
  - `_perform_rebuild_and_persist_sync(...)` starts controlled rebuild execution.
- `api/app_factory.py`
  - `_run_startup_reconciliation(...)` performs startup reconciliation gate checks before executor initialization.

## CI-driven conditional behaviors

- `.github/workflows/ci.yml`
  - Python lint/test gates are the primary CI contract.
- `tools/ci/check_coordination_invariants.py`
  - Enforces distributed-coordination invariants in rebuild execution paths.

## Hidden "if drift then rebuild" logic

- `src/logic/rebuild_failure_detection.py`
  - Drift signal source (`InconsistencyType`) for coordination anomalies.
- `src/logic/rebuild_recovery.py`
  - `determine_recovery_action(...)` converts drift into deterministic recovery actions.
- `src/logic/recovery_gate.py`
  - `evaluate_and_reconcile(...)` / `ensure_safe_to_execute(...)` applies decision outcomes during control-plane checks.

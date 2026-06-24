# Failure-Mode and Scale Validation

## Date

2026-06-24

## Scope

This document records controlled test evidence for restart, crash, stale-owner, and representative-scale graph
persistence behavior.

## Environment

- Backend: FastAPI test app and rebuild orchestration helpers
- Persistence: file-backed SQLite for app/rebuild paths, in-memory SQLite for RecoveryGate state-machine checks
- Runtime: pytest integration suite
- Graph sizes:
  - 250 assets / 1,000 relationships
  - 1,000 assets / 5,000 relationships

## Failure-Mode Results

| Scenario | Expected | Test |
|---|---|---|
| Restart after persisted rebuild | persisted graph loads after runtime reset | `test_promotion_gate_sequence_rebuild_restart_and_persisted_startup` |
| Crash before persist | job fails, durable truth remains empty or unchanged | `test_rebuild_crash_before_persist_marks_failed_without_partial_graph_truth` |
| Crash after persist metadata failure | graph truth remains loadable and internally consistent | `test_rebuild_failure_after_persist_does_not_corrupt_durable_graph_truth` |
| Fresh foreign owner | reset blocked while owner heartbeat is fresh | `test_recovery_does_not_reset_running_job_with_fresh_foreign_heartbeat` |
| Stale owner | reset allowed only through RecoveryGate lock reacquisition | `test_recovery_resets_stale_running_job_after_lock_reacquisition` |
| Lock lost | rebuild aborts fail-closed before persistence success | `test_lock_lost_during_rebuild_aborts_before_success_marking` |
| Restart during live rebuild | restarted instance does not take ownership from a fresh owner | `test_restart_during_live_rebuild_does_not_steal_fresh_owner` |

## Baseline Timings

| Path | Graph size | Baseline | Guardrail |
|---|---:|---:|---:|
| repository save/load | 250 / 1,000 | recorded by test log | non-SLO |
| repository save/load | 1,000 / 5,000 | recorded by test log | non-SLO |
| startup persisted load | 250 / 1,000 | recorded by test log | < 15s |
| rebuild persist path | 250 / 1,000 | recorded by test log | < 20s |

## Notes

These timings are regression baselines, not production SLOs. The validation keeps SQLite compatibility and does not add
architecture, schema, frontend, scheduler, queue, or API-contract changes.

Local focused validation completed successfully:

```bash
pytest tests/integration/test_graph_persistence_scale_validation.py -q
# 4 passed

pytest tests/integration/test_distributed_hosting_failure_modes.py -q
# 6 passed
```

# Active Context

## Current Phase

Implementation / Integration

## Current Task

Integrating `ReconciliationEngine` plan generation into `RecoveryGate` and adding a periodic background reconciliation loop in `api/app_factory.py`.

## Focus Areas

- `src/logic/recovery_gate.py`
- `api/app_factory.py`
- `src/logic/reconciliation_engine.py`

## Recently Modified Files

- `docs/tech_spec.md` (Updated rebuild_jobs schema to match migration DDL)
- `docs/reconciliation-engine.md` (Decoupled run_rebuild helper)
- `docs/reconciliation-discovery-map.md` (Updated state and Roadmap deviation)

## Open Questions

- None.

## Next Steps

- Formulate implementation plan for replacing legacy inconsistency detection in `RecoveryGate` with `ReconciliationEngine.generate_reconciliation_plan()`.
- Plan background reconciliation loop.

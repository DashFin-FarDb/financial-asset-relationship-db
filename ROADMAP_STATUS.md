# Roadmap Status

> Historical stage ledger. Current programme authority is the
> [FarDB Project Continuity Ledger](docs/strategy/fardb-project-continuity.md); dated strategy snapshots and generated
> memory do not override it.

## Current programme checkpoint — 2026-08-13

**Repository evidence cutoff:** `main@2dd9f64136eb653284b0f5330a16ee99f6b0b491`

| Work                                                   | Status                    | Evidence / next action                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------ | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CQ-01 — Separate runtime and migration authority       | Complete                  | PR [#1608](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1608), verified squash `1a49cee56255ec4f50495fa9bdd80ddd3f8f6763`                                                                                                                                                                                                                                                         |
| CQ-02 — Read-only schema compatibility verification    | Complete                  | Closed in the same merge; exact PostgreSQL 15/16 CI passed                                                                                                                                                                                                                                                                                                                                                 |
| QH-01 — Ignore generated knowledge previews            | Complete                  | PR [#1632](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1632), verified squash `5b2685c5ff0635cfd586798cbe2df33a33145216`; later generated pushes were canceled at Vercel's verified-commit gate, so ignore-rule execution remains operationally unconfirmed                                                                                                                      |
| External DeepSource timeout/configuration contexts     | Accepted non-blocking     | [#1631](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1631) closed as not planned; no source repair or threshold weakening                                                                                                                                                                                                                                                       |
| CQ-03 — One PostgreSQL migration ledger and drift gate | ADR ratified; CQ-03B next | Accepted [ADR 0009](docs/adr/0009-postgresql-migration-ledger-and-drift-contract.md), merged [PR #1634](https://github.com/DashFin-FarDb/financial-asset-relationship-db/pull/1634), [GitHub #1633](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1633), and [Linear DAS-62](https://linear.app/dashfin/issue/DAS-62/cq-03-establish-postgresql-migration-ledger-and-drift-gate) |
| PostgreSQL request-path statement timeout              | P2 follow-up              | Bounded dedicated issue [#1623](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1623); does not displace CQ-03                                                                                                                                                                                                                                                                     |

CQ-03A completed as design and ratification only. CQ-03B is now the next bounded phase: recover and materialize the
repository ledger without repairing provider history, mutating hosted schema, changing credentials, or promoting
production.

Broad scanner-driven module decomposition remains deferred. Reduce complexity only when a characterized seam is
touched by CQ-03 or later authority work.

## Phase 1.3 - Lifecycle Tracing

- [x] Phase 1.3.a - Trace Context Model and Propagation (PR #1264)
- [x] Phase 1.3.b - Middleware Refactoring
- [x] Phase 1.3.c - Startup and Rebuild Engine Tracing (PR #1269)

## Stage 5C.3 - Executor Crash Recovery & Cancellation Integrity

- [x] Stage 5C.3A - Execution Identity
- [x] Stage 5C.3B - Checkpointed Recovery Strategy
- [x] Stage 5C.3C - Cancellation Integrity

## Stage 5C.4 - Periodic Background Reconciliation

- [x] **5C.4 RecoveryGate Integration:** startup and periodic callers ask `RecoveryGate` for a reconciliation plan.
  The gate constructs `RebuildDriftEvaluator` and passes it to `ReconciliationEngine`; the engine invokes the
  evaluator's `evaluate_drift()` and returns the plan that those callers consume.

## Phase 1.4 - Observability Enhancements (To Be Done)

- [ ] Phase 1.4.a - Implement Rebuild Queue Metrics
- [ ] Phase 1.4.b - Implement State Transition Counters
- [ ] Phase 1.4.c - Implement Lock Acquisition Metrics
- [ ] Phase 1.4.d - Implement Startup Metrics

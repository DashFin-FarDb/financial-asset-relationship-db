# Distributed Hosting Invariants

For the governing operational semantics, see the canonical
[State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md).
[ADR 0004: Distributed Hosting Semantics](../adr/0004-distributed-hosting-semantics.md)
remains the historical decision record.

This document tracks the distributed hosting invariant matrix originally defined
by PR 6 and validated across PR 7 (`failure-mode-and-scale-validation.md`),
`H-P2-01`–`H-P2-05` hardening PRs, the 5 operational drills
(`operational-drill-execution-records.md`), and the PostgreSQL 18.6 `SCALE10K`
baseline (`../evidence-records/production-scale-pg18-baseline-2026-11-27.md`).

| Invariant | Expected behavior | Validation target |
| --- | --- | --- |
| Single writer | Two concurrent rebuild requests cannot both persist graph truth. | integration/concurrency |
| Multi-reader | Multiple instances can serve reads without rebuild lock. | integration/startup |
| Fresh owner protected | A `RUNNING` job with fresh heartbeat from another worker is not reset. | recovery gate |
| Stale owner recoverable | A `RUNNING` job with expired heartbeat can be reset only after lock reacquisition. | recovery gate |
| Lock lost aborts writer | Writer aborts before persist, commit, or success marking when `lock_lost` is set. | graph_admin/rebuild |
| Unknown ownership blocks | `UNKNOWN` and `LOST` lock states block mutation. | recovery gate |
| Startup does not steal live rebuild | Restarted instance does not reset a freshly heartbeating active rebuild. | startup/recovery |
| Redeploy after completed persist loads durable graph | New instance loads persisted graph and reports persisted startup source. | hosted readiness |
| Bounded health is not durable truth | `/api/health/detailed` alone is insufficient for promotion. | readiness smoke |
| Periodic reconciliation is not a rebuild worker | Reconciliation loop does not call rebuild execution directly. | unit/reconciliation_loop |
| Split-brain requires manual action | `UNSAFE_SPLIT_BRAIN` plans do not auto-reset. | reconciliation/recovery |
| TTL consistency | All instances in one environment use the same lock TTL. | config/settings |

## Validation Boundary

Repository-level automated tests, operational drills, and local PostgreSQL 18.6
scale benchmarks cover these invariants for `main` (see
`failure-mode-and-scale-validation.md` and `operational-drill-execution-records.md`).
Hosted staging/production promotion still requires target-environment evidence
for the exact release SHA:

- RecoveryGate for stale-owner and unsafe-plan behavior.
- Rebuild orchestration for lock-loss aborts and fencing-token validation before
  persistence or success marking.
- Startup/load paths for restart and redeploy evidence.
- Hosted readiness smoke checks (`--require-persistence`) for durable graph truth proof.

# Distributed Hosting Invariants

For the governing operational semantics, see the canonical
[State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md).
[ADR 0004: Distributed Hosting Semantics](../adr/0004-distributed-hosting-semantics.md)
remains the historical decision record.

This document is the PR 7 validation checklist. PR 6 defines the expected
behavior; PR 7 should convert these rows into failure-mode, startup, recovery,
and hosted-readiness tests.

| Invariant | Expected behavior | Future test target |
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

These are not claims that the PR 7 tests already exist. They are acceptance
targets for the next validation PR.

PR 7 should prefer tests that prove behavior at the same boundary operators
depend on:

- RecoveryGate for stale-owner and unsafe-plan behavior.
- Rebuild orchestration for lock-loss aborts before persistence or success
  marking.
- Startup/load paths for restart and redeploy evidence.
- Hosted readiness smoke checks for durable graph truth proof.

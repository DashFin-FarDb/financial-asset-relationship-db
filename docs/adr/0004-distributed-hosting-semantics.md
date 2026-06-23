# ADR 0004: Distributed Hosting Semantics

For the broader enterprise-readiness audit and rollout plan, see
[docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

## Status

Accepted

## Date

2026-06-23

## Context

FarDb can be hosted with more than one backend instance. Backend instances may
concurrently serve reads, perform startup load, run bounded health checks, and
observe rebuild state. They must not concurrently write graph truth.

The selected hosted topology is Vercel-hosted Next.js frontend, Vercel
serverless FastAPI backend, PostgreSQL-compatible graph persistence,
PostgreSQL-compatible application database for staging/production, and
environment-variable secrets. The operating model distinguishes local, preview,
staging, and production environments. This ADR extends that model with explicit
multi-instance rebuild, restart, and lock-ownership semantics.

ADR 0003 defines the rebuild heartbeat strategy: the active rebuild owner
refreshes the `graph_rebuild` distributed lock and rebuild job heartbeat at
`max(1, lock_ttl_seconds // 3)`. Failure to refresh either signal is treated as
lock loss by the active rebuild worker.

## Decision

FarDb uses a single-writer / multi-reader model.

Only one rebuild writer may hold the `graph_rebuild` distributed lock and
persist graph truth at a time. Multiple backend instances may serve read traffic
from local in-memory runtime graph snapshots, provided staging/production
promotion has already proved that the runtime graph was loaded from durable
graph persistence.

## Semantics

### 1. Authority model

FarDb separates three concepts:

- **Durable graph truth**: the persisted graph state in
  `ASSET_GRAPH_DATABASE_URL`.
- **Runtime graph**: the in-memory graph snapshot loaded by a backend instance
  during startup or refreshed after rebuild.
- **Rebuild control plane**: the lock, rebuild job state, heartbeat,
  RecoveryGate, ReconciliationEngine, and periodic reconciliation loop.

In staging and production, durable graph truth is authoritative. Runtime graph
state is a cache/snapshot, not the source of truth.

`ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL`. Application
database health does not prove graph persistence. A deployment may serve an
in-memory graph without durable graph configuration in local or explicitly
non-durable preview environments, but that behavior is not sufficient for
staging/production promotion.

### 2. Single-writer rule

Exactly one backend instance may execute the graph rebuild/persist writer path
at a time.

The writer must hold the `graph_rebuild` distributed lock before mutating
rebuild state or persisting rebuilt graph truth. A backend instance that does
not hold the lock may serve reads but must not persist graph truth.

A backend instance that loses lock ownership during rebuild must abort before
persisting graph truth, committing the persistence transaction, or marking the
job succeeded.

### 3. Multi-reader rule

Multiple backend instances may serve read traffic concurrently.

Read instances do not need to hold the rebuild lock. During rolling redeploy or
refresh windows, read instances may temporarily serve different in-memory
snapshots. Staging/production promotion requires proof that the runtime graph
was loaded from durable persistence, not just that a bounded health endpoint is
healthy.

### 4. Rebuild lock ownership

Lock-state semantics are:

| Lock state | Required behavior |
| --- | --- |
| `VALID` and held by current writer | Writer may continue. |
| `VALID` but held by another writer | Current instance must not mutate. |
| `EXPIRED` | A new writer may attempt acquisition through the lock API only. |
| `UNKNOWN` | Treat as insufficient ownership proof. Do not mutate graph truth. |
| `LOST` | Treat as unsafe. Do not mutate graph truth. |
| Lock conflict | Do not retry as if transient. Surface contention/blocking. |
| Transient DB/network error | Retry only where the implementation explicitly supports retry. Otherwise block/fail-safe. |

The default rebuild lock TTL is 300 seconds. All instances sharing one graph
persistence boundary must use consistent rebuild lock TTL configuration.

### 5. Heartbeat and liveness

The heartbeat proves active rebuild liveness only when both signals remain
fresh:

- the distributed lock is refreshed by the current holder; and
- the rebuild job row is updated with `last_heartbeat_at` and
  `active_worker_id` for the same execution.

Per ADR 0003, the refresh interval is `max(1, lock_ttl_seconds // 3)`. Failure
to refresh the lock or job heartbeat signals lock loss to the running rebuild
operation. The rebuild writer must poll the lock-loss signal before graph build,
before persistence, before commit, and before success marking.

### 6. Split-brain handling

Split-brain means two or more backend instances believe they are authorized to
mutate rebuild state or persist graph truth for the same rebuild window.

If split-brain is suspected, mutation must block. Specifically:

- if lock ownership cannot be proven, block mutation;
- if a running job has a fresh heartbeat from another `active_worker_id`, block
  mutation;
- if lock state is `LOST`, block mutation;
- if persistence is unavailable, block mutation;
- if reconciliation classifies the state as `UNSAFE_SPLIT_BRAIN` or
  `INTEGRITY_COMPROMISED`, do not auto-reset.

Operator action is required for unsafe split-brain classifications.

`ReconciliationEngine` remains plan-only. It never mutates external state,
executes database jobs, or writes persistence. Only RecoveryGate or explicit
rebuild orchestration may consume reconciliation plans to perform side effects.

### 7. Stale-owner mutation rules

A stale owner is a rebuild job whose recorded owner is no longer proving
liveness through both lock ownership and heartbeat freshness. A stale owner is
not the same as a competing live owner.

Recovery mutation is allowed only when all of the following are true:

1. There is a `RUNNING` rebuild job requiring recovery.
2. The job heartbeat is missing, invalid, or older than
   `REBUILD_LOCK_TTL_SECONDS`.
3. The current instance holds or successfully reacquires the rebuild lock.
4. The active job is not freshly heartbeating under a different
   `active_worker_id`.
5. RecoveryGate classifies the plan as resettable, not split-brain or manual
   investigation.
6. Cancellation/shutdown has not been signaled before mutation.

Recovery mutation is forbidden when any of the following are true:

1. Another worker has a fresh heartbeat.
2. The lock is validly held by another worker.
3. Lock state cannot be determined.
4. Persistence is unavailable.
5. More than one `RUNNING` job exists.
6. Reconciliation returns `ALERT_ONLY`, `WAIT_FOR_CONVERGENCE`,
   `EVALUATION_FAILED`, `UNSAFE_SPLIT_BRAIN`, or `INTEGRITY_COMPROMISED`.

### 8. Restart/redeploy behavior

**Scenario A - restart with no in-flight rebuild**

The new instance loads durable graph truth. Startup evidence must show
persisted graph load in staging/production. No recovery mutation is expected.

**Scenario B - restart while another instance is actively rebuilding**

The new instance must not take over if the active owner is freshly
heartbeating. Rebuild API attempts should return contention/blocked behavior.
Read traffic may continue from the available runtime snapshot.

**Scenario C - redeploy kills the active rebuild owner**

The heartbeat stops. The lock eventually expires if not refreshed. A later
instance may recover only after stale-owner conditions are satisfied. Recovery
should mark the stale job failed/reset according to RecoveryGate rules before a
new rebuild starts.

**Scenario D - redeploy during persistence commit**

If lock ownership is lost or uncertain before commit/success marking, the
writer must abort. If durable persistence commit completed but success marking
did not, reconciliation must classify and recover job metadata without
corrupting graph truth.

### 9. Periodic reconciliation behavior

Periodic reconciliation is a control-plane safety mechanism, not an independent
rebuild worker.

It may inspect lock, job, and runtime state. It may consume
RecoveryGate-approved reconciliation plans. It must not bypass RecoveryGate. It
must not start graph rebuild work directly. It must not mutate graph truth.

Periodic reconciliation may perform bounded recovery of stale rebuild job
metadata only through RecoveryGate-approved reset semantics.

### 10. Operator expectations

Backend scale-out is permitted for read serving. Scale-out does not increase
rebuild writer concurrency. Operators must assume one rebuild writer globally
per graph persistence boundary.

Operators must ensure:

- `REBUILD_LOCK_TTL_SECONDS` is consistent across instances in the same
  environment;
- all instances sharing `ASSET_GRAPH_DATABASE_URL` share the same coordination
  database boundary, or an explicitly documented `coordination_database_url`;
- rolling redeploy may leave an in-flight rebuild in stale state, and recovery
  occurs through lock expiry plus reconciliation, not blind takeover;
- suspected split-brain requires manual operator intervention.

### 11. Testable invariants

The future validation checklist lives in
[docs/testing/distributed-hosting-invariants.md](../testing/distributed-hosting-invariants.md).
PR 6 documents the invariants; PR 7 is responsible for proving them through
failure-mode and scale tests.

## Consequences

- Multi-instance backend serving is supported as multi-reader serving.
- Rebuild writer concurrency remains globally single-writer per graph
  persistence boundary.
- Recovery is intentionally conservative: unknown ownership, lock loss,
  persistence failure, and fresh competing owners block mutation.
- Staging/production promotion depends on durable graph truth evidence, not
  bounded health alone.
- PR 7 can convert the documented invariants into failure-mode and scale
  validation without first resolving semantic ambiguity.

## Non-goals

- No production code changes.
- No schema changes.
- No frontend changes.
- No new rebuild endpoint.
- No new distributed scheduler.
- No multi-region support claim.
- No Redis, queue, or external coordinator introduction.
- No backup/restore runbook; that belongs to PR 9.
- No failure-injection implementation; that belongs to PR 7.

## References

- [ADR 0002: Hosted Deployment and Durable Persistence](./0002-hosted-deployment-and-persistence.md)
- [ADR 0003: Distributed Lock Refresh and Heartbeat Strategy](./0003-distributed-lock-refresh-and-heartbeat-strategy.md)
- [Enterprise Deployment Operating Model](../enterprise-deployment-operating-model.md)
- [Reconciliation Engine](../reconciliation-engine.md)
- [Distributed Hosting Invariants](../testing/distributed-hosting-invariants.md)

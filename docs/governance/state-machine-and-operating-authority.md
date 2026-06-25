# State Machine and Operating Authority

**Status:** Current authority
**Scope:** Rebuild coordination, runtime graph lifecycle, durable graph persistence, operator ownership, and exception handling
**Runtime impact:** Documentation only. This specification does not change runtime behaviour.

This document is the canonical operational authority for FarDb rebuild, recovery, persistence, promotion, rollback handoff, and exception-handling semantics.

ADRs remain historical decision records. They explain why decisions were made at a point in time. When an ADR, audit, roadmap, runbook, or implementation comment conflicts with this document about current operational interpretation, this document is the current authority until the implementation and this document are changed together in a reviewed PR.

## Source-of-truth implementation references

This document consolidates the current interpretation of:

- `RebuildJobStatus` and rebuild-job fields in [`src/data/db_models.py`](../../src/data/db_models.py)
- atomic rebuild-job update rules in [`src/data/repository.py`](../../src/data/repository.py)
- runtime graph lifecycle states and transitions in [`api/graph_lifecycle.py`](../../api/graph_lifecycle.py)
- distributed lock states, lifecycle states, fencing tokens, and TTL cap in [`src/data/distributed_lock.py`](../../src/data/distributed_lock.py)
- rebuild heartbeat, checkpoint, cancellation, and persistence guards in [`api/routers/graph_admin.py`](../../api/routers/graph_admin.py)
- stale-owner and inconsistency detection in [`src/logic/rebuild_failure_detection.py`](../../src/logic/rebuild_failure_detection.py)
- RecoveryGate and reconciliation safety handling in [`src/logic/recovery_gate.py`](../../src/logic/recovery_gate.py)
- distributed-hosting validation targets in [`docs/testing/distributed-hosting-invariants.md`](../testing/distributed-hosting-invariants.md)

## Authority boundaries

This specification governs operational interpretation. It does not replace:

- ADR 0002 for the historical hosted persistence decision;
- ADR 0003 for the historical lock-refresh and heartbeat decision;
- ADR 0004 for the historical distributed-hosting semantics decision;
- ADR 0005 or the DR runbook for backup schedule, retention, RPO/RTO, or restore procedure details.

Disaster-recovery procedure details live in [ADR 0005](../adr/0005-backup-restore-dr-strategy.md) and the [backup/restore/DR runbook](../runbooks/backup-restore-dr.md). This document only defines the state-machine and authority rules that operators must respect before, during, and after those procedures.

## Rebuild job state machine

### RebuildJobStatus states

| State | Value | Terminal | Meaning |
| --- | --- | --- | --- |
| `PENDING` | `pending` | No | Job row exists but no execution owner has started it. |
| `RUNNING` | `running` | No | One execution attempt has claimed the job and assigned an `execution_id`. |
| `SUCCEEDED` | `succeeded` | Yes | Rebuild completed, graph truth was persisted, success metadata was written. |
| `FAILED` | `failed` | Yes | Rebuild failed with bounded failure category/message and completion metadata. |
| `CANCELLED` | `cancelled` | Yes | Cooperative cancellation completed and cancellation finalization was recorded. |
| `CANCEL_REQUESTED` | `cancel_requested` | No | Cancellation has been requested and an executing owner must cooperatively stop before finalization. |

Terminal rebuild-job states are `SUCCEEDED`, `FAILED`, and `CANCELLED`. Terminal states are not reopened or mutated into another lifecycle status by the repository transition helpers. Any retry is a new rebuild job, not a resurrection of the terminal job.

`CANCEL_REQUESTED` is intentionally non-terminal. It is a request boundary. The active owner discovers the request through heartbeat failure diagnosis and completes the cooperative abort path before finalizing the job as `CANCELLED`.

### Allowed rebuild-job transitions

The following table mirrors the atomic conditional-update rules in `AssetGraphRepository`.

| From | To / operation | Required guard | Notes |
| --- | --- | --- | --- |
| none | `PENDING` | `create_rebuild_job()` creates a new UUID job row. `requested_by` is bounded to 64 chars; `source` is bounded to 32 chars. | Initial creation only. |
| `PENDING` | `RUNNING` | `job_id` exists, current status is `PENDING`, supplied `execution_id` length is at most 64 chars. | `started_at`, `updated_at`, and `execution_id` are set atomically. |
| `RUNNING` | `SUCCEEDED` | current status is `RUNNING`; stored `execution_id` equals supplied `execution_id`; `duration_ms`, `node_count`, and `edge_count` are non-negative. | Success metadata and `completed_at` are written atomically. |
| `PENDING` | `FAILED` | current status is `PENDING`; bounded failure category/message; non-negative duration. | No execution identity is required because execution may not have started. |
| `RUNNING` | `FAILED` | current status is `RUNNING`; stored `execution_id` equals supplied `execution_id`; bounded failure category/message; non-negative duration. | A stale or superseded owner cannot fail a job it no longer owns. |
| `PENDING` | `CANCEL_REQUESTED` | current status is `PENDING`. | Cancellation request is recorded with `cancellation_requested_at`. |
| `RUNNING` | `CANCEL_REQUESTED` | current status is `RUNNING`. | Request is recorded; the active execution owner must observe and finalize cooperatively. |
| `CANCEL_REQUESTED` | `CANCELLED` | current status is `CANCEL_REQUESTED`; stored `execution_id` equals supplied `execution_id`. | Finalization is owner-only. Already-`CANCELLED` is treated as idempotent success by the repository helper. |
| `RUNNING` | heartbeat update | current status is `RUNNING`; stored `execution_id` equals supplied `execution_id`; `active_worker_id` is either unset or equals supplied worker id. | Updates `active_worker_id`, `last_heartbeat_at`, and `updated_at`. |
| `RUNNING` | checkpoint update | current status is `RUNNING`; stored `execution_id` equals supplied `execution_id`. | Updates `checkpoint_data` and `updated_at`. |
| any status with matching execution | source update | stored `execution_id` equals supplied `execution_id`; source is null or at most 32 chars. | Used to record rebuild source for the current execution attempt. |

### Forbidden rebuild-job transitions and mutations

The following transitions or mutations are forbidden by the current repository contract:

- `PENDING -> SUCCEEDED`
- `PENDING -> CANCELLED` without passing through owner-valid `CANCEL_REQUESTED -> CANCELLED`
- `RUNNING -> PENDING`
- `RUNNING -> CANCELLED` without first recording `CANCEL_REQUESTED`
- `SUCCEEDED -> any other status`
- `FAILED -> any other status`
- `CANCELLED -> any other status`
- `CANCEL_REQUESTED -> SUCCEEDED`
- `CANCEL_REQUESTED -> FAILED` through the normal failure helper
- any success, failure, cancellation-finalization, heartbeat, checkpoint, or source mutation where the supplied `execution_id` does not match the stored `execution_id`
- any heartbeat mutation where another `active_worker_id` has already claimed ownership
- any checkpoint mutation outside `RUNNING`
- any heartbeat mutation outside `RUNNING`; `CANCEL_REQUESTED` is diagnosed as cooperative cancellation rather than accepted as a heartbeat state
- any recovery mutation when multiple `RUNNING` jobs exist
- any stale-owner mutation before lock ownership is reacquired or proven safe by RecoveryGate

## Runtime graph lifecycle state machine

### GraphRuntimeLifecycleState states

| State | Terminal | Meaning |
| --- | --- | --- |
| `UNINITIALIZED` | No | No runtime graph is currently initialized for this process. |
| `INITIALIZING` | No | The process is selecting or constructing the runtime graph. |
| `READY` | No | Runtime graph is available for read serving. |
| `REBUILDING` | No | A rebuild attempt is in progress and runtime publication is controlled by rebuild completion. |
| `FAILED` | No | Runtime initialization or rebuild failed; recovery/retry paths may re-enter initialization or rebuild. |
| `SHUTTING_DOWN` | No | Shutdown sequence has begun. |
| `STOPPED` | Operationally terminal | Normal shutdown reached stopped state. The only outgoing transition is explicit reset to `UNINITIALIZED` for test isolation or administrative restart paths. |

Runtime lifecycle state is process-local. Rebuild-job state is durable coordination state. A process may be `READY` while no job is active, or `READY` after synchronizing a graph from the latest successful rebuild. A durable `RUNNING` job without a matching runtime active executor is classified through inconsistency detection rather than inferred only from runtime lifecycle state.

### Allowed runtime lifecycle transitions

| From | Allowed to | Notes |
| --- | --- | --- |
| `UNINITIALIZED` | `INITIALIZING`, `REBUILDING`, `SHUTTING_DOWN` | Rebuild may be the first hosted lifecycle operation after process start. |
| `INITIALIZING` | `READY`, `FAILED`, `SHUTTING_DOWN` | Initialization succeeds, fails, or is interrupted by shutdown. |
| `READY` | `REBUILDING`, `SHUTTING_DOWN` | Normal read-serving state can enter rebuild or shutdown. |
| `REBUILDING` | `READY`, `FAILED`, `SHUTTING_DOWN` | Rebuild success returns to ready; rebuild failure marks failed. |
| `FAILED` | `INITIALIZING`, `REBUILDING`, `SHUTTING_DOWN` | Recovery, retry, or shutdown may follow failure. |
| `SHUTTING_DOWN` | `STOPPED` | Normal shutdown progression only. |
| `STOPPED` | `UNINITIALIZED` | Explicit reset for administrative restart or test isolation only. |

A transition to the current state is a no-op. Every other transition not listed above is invalid and raises a runtime transition error.

### Relationship between runtime lifecycle and job state

- `PENDING` is durable job intent; it does not prove process-local `REBUILDING`.
- `RUNNING` means a durable job has an execution owner. The owning process should be in, or be entering, `REBUILDING`; divergence is evaluated through `runtime_has_active_executor`, heartbeat, lock state, and `InconsistencyType`.
- `SUCCEEDED` permits runtime synchronization to publish the rebuilt graph and set/keep runtime state `READY`.
- `FAILED` maps to rebuild completion with `succeeded=False` and may place the runtime in `FAILED` until reinitialization or a later rebuild.
- `CANCEL_REQUESTED` is not a runtime state. It is detected by the heartbeat path and translated into a local cancellation event.
- `CANCELLED` is durable job finalization after cooperative abort. Runtime state follows the rebuild failure/cancellation path rather than becoming a separate cancellation lifecycle state.

## Distributed lock and fencing-token invariants

### LockState states

`LockState` is the database-observed lock state returned by lock checks.

| State | Meaning | Required behaviour |
| --- | --- | --- |
| `VALID` | Lock exists, has not expired, and is held by the current `holder_id`. | Current writer may continue, subject to all other guards. |
| `EXPIRED` | Lock exists but TTL has passed. | A new writer may attempt acquisition through the lock API only. Expiry alone is not permission to mutate. |
| `UNKNOWN` | Lock does not exist, is held by another holder, or ownership cannot be proven. | Treat as insufficient ownership proof. Do not mutate rebuild state or graph truth. |
| `LOST` | State check failed due to database/connectivity loss, or lifecycle marked ownership lost. | Treat as unsafe. Abort or block mutation. |

### LockLifecycleState states

`LockLifecycleState` is the process-local lifecycle of the coordination primitive.

| State | Meaning |
| --- | --- |
| `INITIAL` | Lock object created but no lease has been acquired. |
| `ACQUIRED` | Lock acquisition succeeded and returned a fencing token. |
| `REFRESHED` | Lock refresh succeeded and returned a new fencing token. |
| `CONTENTED` | Another holder or retry ceiling prevented acquisition/refresh. |
| `LOST` | Refresh/check/acquire error made ownership unsafe. |
| `RELEASED` | Current holder released the lock row. |

### Fencing-token invariant

Fencing tokens are derived from the lock row `updated_at` timestamp at microsecond precision and returned with the same atomic write result that acquired or refreshed the lock. The invariant is monotonicity across successful writes to the same lock: a later successful acquisition or refresh must produce a fencing token greater than the earlier token for that lock row.

A writer must not invent a fencing token from local time or a cached read. The token is evidence of a successful coordination write, not a process-local timestamp.

### TTL invariant

`MAX_TTL` is 300 seconds in `src/data/distributed_lock.py`. `DistributedLock` rejects `ttl_seconds > MAX_TTL`, and rebuild orchestration clamps the operational lock TTL to 300 seconds before constructing the lock. RecoveryGate also bounds its lock TTL with `max(1, min(lock_ttl_seconds, MAX_TTL))`.

All instances sharing one graph persistence boundary must use consistent `REBUILD_LOCK_TTL_SECONDS`. Inconsistent TTL configuration is an operator configuration fault because it changes stale-owner classification and recovery timing.

## Heartbeat, stale-owner, and inconsistency invariants

A rebuild owner proves liveness through both signals:

1. the `graph_rebuild` distributed lock remains refreshable by the current holder; and
2. the rebuild job row accepts heartbeat updates for the same `execution_id` and `active_worker_id`.

`active_worker_id` is the worker identity that claimed heartbeat ownership. Once set, heartbeat updates from a different worker are rejected. `execution_id` is the durable identity of the execution attempt; owner-only mutations require it to match the stored job row.

`last_heartbeat_at` is the durable liveness timestamp used to classify stale ownership. A `RUNNING` job is stale when no heartbeat has ever been recorded or when the heartbeat age exceeds the lock TTL. Crash suspicion is similar but requires `active_worker_id` and uses a configurable heartbeat threshold, defaulting to the TTL when unspecified.

`InconsistencyType` classifications are:

| Type | Meaning |
| --- | --- |
| `NONE` | No detected rebuild coordination inconsistency. |
| `STALE_OWNERSHIP` | A `RUNNING` job has missing or TTL-stale heartbeat evidence. |
| `ORPHANED_RUNNING` | Database says `RUNNING`, but runtime reports no active executor. |
| `ZOMBIE_EXECUTOR` | Runtime reports an active executor but there is no compatible running DB job. |
| `CRASH_SUSPICION` | A worker is assigned but heartbeat is missing or stale beyond the crash-suspicion threshold. |

Detection priority is zombie executor without a DB job, orphaned running, crash suspicion, stale ownership, then none.

## Durable graph-persistence invariants

Durable graph truth for staging and production lives in `ASSET_GRAPH_DATABASE_URL`. Runtime graph state is an in-memory snapshot/cache. `DATABASE_URL` or application-database health is not proof of graph durability.

Persistence invariants:

- the rebuild writer must hold a valid distributed lock before mutating rebuild state or persisting graph truth;
- RecoveryGate must allow execution before the rebuild job is created and run;
- lock loss or cancellation must be checked before graph build, before persistence, immediately before database commit, and before success marking;
- lock loss before commit or before success marking aborts the writer path and prevents success finalization;
- checkpoint writes are best-effort progress metadata and require `RUNNING` plus matching `execution_id`;
- checkpoint callbacks do not write when local lock-loss or cancellation events are set;
- graph snapshot restore after rebuild failure is best-effort rollback safety, not the DR restore procedure;
- `SUCCEEDED` means graph persistence and success metadata were both completed for the owning execution attempt;
- bounded readiness is not durable graph truth.

The bounded-health versus durable-truth rule is strict: `GET /api/health/detailed` can prove bounded service health, in-memory graph availability, and application DB reachability. It cannot prove staging/production durable graph truth unless accompanied by persisted startup evidence such as `graph.persistence_loaded == true`, `graph.startup_source == "persisted"`, and expected persisted graph counts or sentinels.

## Formal invariants

The following invariants are the current review and operating contract:

1. Only one active rebuild owner may exist per graph persistence boundary.
2. Multiple backend instances may serve reads without holding the rebuild lock.
3. Scale-out does not increase rebuild writer concurrency.
4. A writer must hold `graph_rebuild` before mutating rebuild state or persisting graph truth.
5. A stale owner may never mutate state.
6. A fresh owner with a valid heartbeat from another worker must not be reset.
7. A stale owner is recoverable only after lock reacquisition and RecoveryGate approval.
8. Lock state `UNKNOWN` or `LOST` blocks mutation.
9. Lock loss aborts the writer before persistence, commit, or success marking.
10. `execution_id` mismatch blocks owner-only mutation.
11. `active_worker_id` mismatch blocks heartbeat ownership takeover.
12. More than one `RUNNING` rebuild job is unsafe and blocks recovery mutation.
13. `UNSAFE_SPLIT_BRAIN` and `INTEGRITY_COMPROMISED` plans do not auto-reset.
14. Periodic reconciliation is not a rebuild worker and must not write graph truth.
15. A restarted instance must not steal a freshly heartbeating active rebuild.
16. A redeployed instance may recover a dead owner only through stale-owner classification, lock reacquisition, and RecoveryGate-approved reset semantics.
17. Staging/production promotion requires durable graph evidence, not bounded health alone.
18. All instances in one environment must use the same rebuild lock TTL and coordination database boundary.

## Operator ownership and handoff boundaries

Role names align with [`docs/enterprise-deployment-operating-model.md`](../enterprise-deployment-operating-model.md).

| Role | Owns | Handoff boundary |
| --- | --- | --- |
| Deploy operator | Executes deployment to the target environment. | Hands to Promotion approver for gate review before staging/production promotion. |
| Promotion approver | Confirms promotion gates and durable graph-persistence evidence. | Blocks promotion if durable evidence is incomplete or contradicted. |
| Rollback executor | Performs Vercel rollback/promotion to a previous known-good deployment. | Hands to Persistence-verification operator after rollback; does not perform data restore by rollback alone. |
| Backup Operator | Verifies backup health and performs ad-hoc backups before risky changes. | Hands to Restore Operator when recovery requires restore execution. |
| Restore Operator | Executes database restore and post-restore verification under the DR runbook. | Hands restored environment to Persistence-verification operator and Incident Commander for service verification. |
| Secret/config maintainer | Owns environment variables, secrets, and rotation. | Confirms `DATABASE_URL`, `ASSET_GRAPH_DATABASE_URL`, `COORDINATION_DATABASE_URL`, and secret settings before promotion or restore verification. |
| Persistence-verification operator | Runs and records durable graph-persistence smoke evidence. | Hands pass/fail evidence to Promotion approver or Incident Commander. |
| Incident Commander | Escalation point for restore failures, data-loss events, RTO/RPO risk, split-brain, and emergency override. | Coordinates exception approval and closure evidence. |
| Rebuild recovery operator | Executes or supervises RecoveryGate-approved rebuild recovery actions. | Escalates to Incident Commander when RecoveryGate returns manual, unsafe, split-brain, integrity-compromised, or evaluation-failed plans. This may be the same person as another role, but the responsibility must be explicit. |
| Exception approver | Explicit maintainer approval for documented exceptions. | Approval must be recorded in the PR or incident record and follow the governance exception rules below. This may be the Incident Commander or maintainer, depending on context. |

One person may hold multiple roles, but the active responsibility must be explicit in the change, incident, or release record.

## Exception authority and handling paths

Exception handling must follow the CI-gate exception model in [`docs/GOVERNANCE.md`](../GOVERNANCE.md): an exception must state the affected gate or invariant, reason, risk assessment, expiry or follow-up issue, and explicit maintainer approval. Exceptions must be narrow, time-bound, and visible in the PR, release, or incident record. Permanent policy changes require a normal reviewed PR.

| Exception condition | Required action | Approval / authority | Manual-intervention rule |
| --- | --- | --- | --- |
| Suspected split-brain | Block mutation. Preserve evidence. Do not auto-reset. | Incident Commander plus explicit maintainer/Exception approver. | Required. `UNSAFE_SPLIT_BRAIN` must not auto-reset. |
| Stale ownership | Wait until stale-owner conditions hold, reacquire/prove lock, then allow only RecoveryGate-approved reset semantics. | Rebuild recovery operator may proceed only with RecoveryGate approval; Incident Commander if ambiguous. | Required if multiple running jobs, unknown ownership, or fresh competing heartbeat exists. |
| Lock loss | Active writer aborts before persistence/commit/success marking; mark failure only through matching owner path where safe. | Rebuild recovery operator; Incident Commander if graph persistence state is ambiguous. | No mutation while lock state is `UNKNOWN` or `LOST`. |
| Failed restore handoff | Stop promotion/restart closure. Return to DR runbook verification and classify RTO/RPO risk. | Restore Operator plus Incident Commander. | Do not treat Vercel rollback as data restore. Do not clear restored lock/job rows until no live writer remains. |
| Incomplete durable-persistence evidence | Block staging/production promotion. Rerun durable graph-persistence smoke after rebuild/restart or approved baseline. | Promotion approver. | Basic health is insufficient. Evidence must prove persisted startup source and expected graph counts/sentinels. |
| Degraded readiness | Classify as bounded health failure or durable graph-persistence failure. Roll back code only when deployment regression is indicated. | Deploy operator and Rollback executor; Incident Commander if service-impacting. | After rollback, durable graph-persistence smoke must be rerun for staging/production. |
| Emergency override | Record an explicit exception request with affected invariant/gate, reason, risk, expiry/follow-up, and maintainer approval. | Incident Commander plus explicit maintainer/Exception approver. | Override cannot make unsafe mutation safe. It can only authorize a documented manual path with evidence and follow-up. |

## Evidence rules

Capture evidence that proves state, ownership, and durability without exposing secrets.

Required evidence when relevant:

- rebuild job ID, status transition, bounded actor/user reference, `execution_id`, and sanitized failure category/message;
- lock acquisition/refresh/check result, lock lifecycle event type, holder ID, and fencing token where emitted;
- `active_worker_id` and bounded heartbeat timing evidence needed to classify stale ownership;
- RecoveryGate/ReconciliationEngine decision, `InconsistencyType`, action, safety state, and reason;
- durable graph-persistence smoke output showing persisted startup source, `persistence_loaded`, expected graph counts, and sentinel checks where approved;
- deployment, rollback, restore, and promotion timestamps and responsible operator roles;
- exception request fields required by governance policy.

Do not capture or commit:

- raw database URLs, connection strings, passwords, tokens, JWT secrets, or provider credentials;
- raw `.env` contents;
- full graph dumps unless explicitly approved and scrubbed;
- raw stack traces or exception text containing secrets or connection details;
- private customer/user data beyond bounded, sanitized operational identifiers.

## PR update trigger

A PR must update this document when it changes any of the following governed behaviours:

- rebuild job states, state transitions, terminal-state interpretation, or conditional-update guards;
- runtime graph lifecycle states or transition graph;
- distributed lock ownership, fencing-token semantics, lock state classification, TTL bounds, or retry/refresh behaviour;
- heartbeat, stale-owner, `active_worker_id`, `last_heartbeat_at`, or `execution_id` semantics;
- durable graph-persistence promotion evidence or bounded-health interpretation;
- rollback/restore handoff boundaries;
- operator authorization, exception authority, or manual-intervention paths.

If a PR changes one of these behaviours and does not update this document, reviewers should treat the PR as incomplete unless the PR explicitly proves the canonical interpretation is unchanged.

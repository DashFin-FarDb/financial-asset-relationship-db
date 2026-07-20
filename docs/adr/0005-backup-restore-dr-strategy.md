# ADR 0005: Backup, Restore, and Disaster Recovery Strategy

For the broader enterprise-readiness audit and rollout plan, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

## Status

Accepted

**Current interpretation:** This ADR remains a historical decision record for backup, restore, and DR strategy. Current rebuild/recovery state-machine semantics, operator authority, rollback/restore handoff boundaries, and exception paths are governed by the canonical [State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md).

## Date

2026-06-24

## Context

FarDb now has durable hosted persistence and explicit distributed hosting semantics. The remaining enterprise recovery gap is operational: staging and production need documented recovery objectives, backup mechanisms, restore verification, and ownership boundaries.

FarDb uses a dual-database architecture:

1. **Auth/Coordination DB** (`api/database.py`): API-layer application persistence for authentication and related control-plane state. It supports SQLite for local development and PostgreSQL for hosted staging/production. `DATABASE_URL` remains canonical, with hosted-provider fallback support where configured.
2. **Asset Graph DB** (`src/data/database.py`): SQLAlchemy-backed persistence for graph truth and rebuild coordination tables. It supports SQLite locally and PostgreSQL-compatible storage in hosted environments through `ASSET_GRAPH_DATABASE_URL`.

The two database boundaries may point to the same physical PostgreSQL instance or to separate logical databases. Operators must treat them as separate recovery concerns unless the deployment explicitly documents a shared database boundary.

The rebuild coordination plane may also be isolated through `COORDINATION_DATABASE_URL`. **Landed runtime placement** (`api/routers/graph_admin.py`): `distributed_locks` use the coordination session (`COORDINATION_DATABASE_URL`, falling back through `DATABASE_URL` then `POSTGRES_URL` in settings), while `rebuild_jobs` (heartbeats/checkpoints) use the domain / Asset Graph session (`ASSET_GRAPH_DATABASE_URL`). DR procedures must resolve the actual deployed connection-string topology and clean up **table-scoped** (locks vs jobs) before restart.

Graph data and coordination/auth data have different recovery properties. Graph data can be rebuilt from source data through `RebuildExecutor` when source data remains available and fresh enough for the target environment. Coordination/auth data is less replaceable: user credentials, rebuild job history, lock state, and checkpoint metadata cannot be fully reconstructed from the graph source feed alone.

The distributed rebuild control plane also introduces timing constraints. `distributed_locks` rows expire through TTL semantics, with the current default maximum operational assumption of 300 seconds. A restored lock row with a future `expires_at` can temporarily block new rebuild lock acquisition until it expires or is cleared by an operator.

## Decision

FarDb adopts a documented disaster recovery strategy for staging and production covering the Auth/Coordination DB and Asset Graph DB.

### Recovery objectives

| Data class | RPO target | RTO target | Notes |
| --- | --- | --- | --- |
| Graph data | Tied to approved source-data freshness | 2 hours for full service restoration, including verification | Graph truth is important but rebuildable through `RebuildExecutor` if source data remains available. |
| Coordination/auth data | 1 hour | 2 hours for full service restoration, including verification | Includes auth/application state and rebuild coordination state that cannot be completely inferred from graph source data. |

The 2-hour RTO includes restore execution, schema verification, application restart/redeployment, health verification, lifecycle verification, and functional smoke testing.

### Backup mechanism

Provider-managed point-in-time recovery (PITR) is the primary backup and restore mechanism for hosted PostgreSQL providers such as Supabase, Neon, and Vercel Postgres where available.

`pg_dump` is the portable fallback mechanism. It must be used for ad-hoc backups before risky operations and for providers or tiers where PITR is unavailable, disabled, or insufficiently retained.

### Retention policy

Hosted staging and production should maintain:

| Backup type | Retention |
| --- | --- |
| Daily backups | 7-day rolling retention |
| Weekly snapshots | 30-day retention |

Provider-managed PITR retention must meet or exceed the intended recovery window. If a provider tier cannot satisfy the retention policy, operators must supplement it with scheduled `pg_dump` snapshots retained outside the primary database service.

### Data classification

| Classification | Tables / state | Recovery priority | Rationale |
| --- | --- | --- | --- |
| **Critical / Non-rebuildable** | `distributed_locks`, `rebuild_jobs` coordination state, user credentials if stored | Highest | These records control operator access, rebuild coordination, checkpoints, and lock ownership. They cannot be regenerated from graph source data alone. |
| **Important / Rebuildable** | `assets`, `asset_relationships`, `regulatory_events`, `regulatory_event_assets` | High | These records represent graph truth. They should be restored when possible but can be rebuilt from source through `RebuildExecutor` if backup data is unavailable or stale. |

Graph data backup loss is recoverable when source data is available and an approved rebuild can be run. In that case, the graph RPO is bounded by source data freshness and rebuild acceptance criteria rather than by database backup age alone.

Coordination state is transient relative to graph truth. Restoring exact mid-rebuild state is lower priority than ensuring clean restart capability. During restore, any `rebuild_jobs` rows in in-flight states should be cleaned up before application restart so RecoveryGate does not classify restored historical state as a live orphaned rebuild.

`distributed_locks` TTL behavior constrains restore timing. Stale locks should auto-expire after the configured TTL, with 300 seconds as the current default maximum operational assumption. Operators may clear restored lock rows only after confirming no live writer from the restored environment is still active.

### Restore strategy

Restores must prefer a clean, verified recovery point over partial repair. Operators should restore to a scratch database first where possible, verify schema and key table sanity, then promote the restored database connection string into the target environment.

Restoration must distinguish deployment rollback from data restore. Vercel rollback/promotion can restore application code and configuration but does not restore PostgreSQL database state.

## Consequences

### Positive

1. Staging and production now have explicit RPO/RTO assumptions instead of implicit best effort recovery.
2. Backup and restore expectations are aligned to the dual-database architecture.
3. Graph data can use its rebuildability without incorrectly treating control-plane state as rebuildable.
4. Provider-managed PITR is the primary path while retaining `pg_dump` portability.
5. Release gating can distinguish a documented DR strategy from a rehearsed restore.

### Negative

1. PITR availability and retention vary by provider and plan, so operators must verify provider settings for each hosted environment.
2. `pg_dump` fallback introduces operational custody requirements for backup files and credentials.
3. Restoring coordination state may require manual cleanup of stale lock and rebuild job rows before restart.
4. The 2-hour RTO assumes database admin access and provider console access are available when the incident begins.

### Neutral

1. This ADR documents strategy and operating assumptions. It does not create automated backup jobs.
2. Local SQLite databases remain developer-owned and are not covered by staging/production RPO/RTO commitments.
3. Cross-region failover is not claimed by this strategy.

## Non-goals

- Automated backup orchestration is deferred.
- Cross-region database replication and cross-region failover are deferred.
- Continuous restore rehearsal automation is deferred.
- Provider-specific infrastructure-as-code changes are out of scope.
- Runtime code changes are out of scope.

## References

- [State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md): current operational authority for rebuild/recovery state-machine semantics and operator handoff boundaries
- [Backup, Restore, and DR Runbook](../runbooks/backup-restore-dr.md)
- [ADR 0002: Hosted Deployment and Durable Persistence](./0002-hosted-deployment-and-persistence.md)
- [ADR 0003: Distributed Lock Refresh and Heartbeat Strategy](./0003-distributed-lock-refresh-and-heartbeat-strategy.md)
- [ADR 0004: Distributed Hosting Semantics](./0004-distributed-hosting-semantics.md)
- [Enterprise Deployment Operating Model](../enterprise-deployment-operating-model.md)

## Authors

- Claude (AI Agent)
- DashFin-FarDb Organization

## Review and Approval

This ADR was created as part of PR 9 / issue #1279 to close the documented enterprise backup, restore, and disaster recovery strategy gap.

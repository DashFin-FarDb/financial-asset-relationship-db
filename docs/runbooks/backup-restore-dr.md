# Backup, Restore, and Disaster Recovery Runbook

For strategy, recovery objectives, and data classification, see [ADR 0005: Backup, Restore, and Disaster Recovery Strategy](../adr/0005-backup-restore-dr-strategy.md).

## Preamble

This runbook defines operator procedures for backing up, restoring, and verifying FarDb staging and production databases.

Use this runbook when:

- verifying provider-managed backup/PITR health;
- taking an ad-hoc backup before a risky migration, deployment, or destructive operation;
- restoring the Auth DB, Coordination DB, Asset Graph DB, or any combined database boundary;
- recovering from data loss, accidental destructive writes, failed migrations, or database-provider incidents;
- proving that restore procedures remain executable for enterprise release readiness.

The intended audience is operators with database, hosting, and deployment authority. It is not an end-user support document.

This runbook distinguishes application rollback from data restore. Vercel rollback/promotion restores application code and configuration only; it does not restore database state.

## Prerequisites

Operators must have the following access before starting backup or restore work:

- Database administrator credentials or equivalent connection strings for each affected database.
- Vercel dashboard access for environment variables, deployment restart/redeployment, and rollback/promotion operations.
- Provider console access for the hosted PostgreSQL provider, such as Supabase, Neon, or Vercel Postgres.
- Permission to read and update `DATABASE_URL`, `POSTGRES_URL`, `COORDINATION_DATABASE_URL`, `ASSET_GRAPH_DATABASE_URL`, and any provider-specific database settings.
- Secure storage for portable dump files when using `pg_dump`.
- Access to deployment logs and `GET /api/health/detailed` for post-restore verification.

Do not paste database credentials, full connection strings, backup contents, or raw exception traces into public issues, PR comments, or support channels.

## Backup Procedures

### 1. Identify database boundaries

FarDb can use up to three logical PostgreSQL database boundaries, although a deployment may map more than one boundary to the same physical database:

- Auth DB: `DATABASE_URL`, with `POSTGRES_URL` as a provider fallback where configured.
- Coordination DB: `COORDINATION_DATABASE_URL`, falling back to `DATABASE_URL` and then `POSTGRES_URL` when unset.
- Asset Graph DB: `ASSET_GRAPH_DATABASE_URL`.

The Coordination DB is the authoritative location for rebuild coordination state when `COORDINATION_DATABASE_URL` is set separately. This includes `rebuild_jobs` and `distributed_locks`; omitting this boundary from backup or restore can lose checkpoint state or resurrect stale lock/job state after a DR event.

For each environment, resolve and record the effective connection strings before backup:

```bash
# Auth DB
export AUTH_DATABASE_URL="${DATABASE_URL:-$POSTGRES_URL}"

# Coordination DB; falls back through the same order as the settings layer
export COORD_DATABASE_URL="${COORDINATION_DATABASE_URL:-$AUTH_DATABASE_URL}"

# Asset Graph DB
export GRAPH_DATABASE_URL="$ASSET_GRAPH_DATABASE_URL"
```

Back up every distinct effective connection string. If two or more logical boundaries resolve to the same physical database, one full database backup may cover those boundaries, but the operator must record that topology in the incident or release evidence.

### 2. Provider-managed backup verification

Provider-managed PITR is the primary mechanism for hosted PostgreSQL.

For each affected environment and every distinct database boundary:

1. Open the provider console for the database instance.
2. Confirm backups or PITR are enabled for the database or branch/project.
3. Confirm the available restore window meets the retention policy in ADR 0005.
4. Identify the latest available restore point and the earliest available restore point.
5. Confirm whether restore creates a new database/branch/project or overwrites the existing instance.
6. Record provider, environment, database boundary, restore window, and timestamp of verification.

Provider-specific expectations:

- **Supabase**: verify point-in-time recovery or scheduled backups in the project database backup settings. Confirm the project tier retention window.
- **Neon**: verify history/restore capability for the relevant branch and identify the timestamp range available for branch restore.
- **Vercel Postgres**: verify backup/restore capability in the storage dashboard and confirm the plan-specific retention behavior.

If provider-managed restore is unavailable or does not meet the target window, take a portable backup with `pg_dump`.

### 3. Portable `pg_dump` backup procedure

Resolve the connection strings from the target environment as shown in the boundary-identification step. Then create timestamped dump files for every distinct database boundary.

For a deployment where all three logical boundaries are separate:

```bash
export BACKUP_TS="$(date -u +%Y%m%dT%H%M%SZ)"

pg_dump "$AUTH_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="fardb-auth-${BACKUP_TS}.dump"

pg_dump "$COORD_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="fardb-coordination-${BACKUP_TS}.dump"

pg_dump "$GRAPH_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="fardb-graph-${BACKUP_TS}.dump"
```

If multiple logical boundaries point to the same database, run one dump for that physical database and label it clearly:

```bash
pg_dump "$DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="fardb-combined-${BACKUP_TS}.dump"
```

Do not create duplicate dumps of the same physical database unless required by the deploying organization's custody process. Store dumps in the approved backup location for the deploying organization. Do not commit dump files to the repository.

### 4. Backup verification

A backup is not considered valid until it has been restored to a scratch database and inspected.

Prepare a scratch database, then restore:

```bash
createdb fardb_restore_scratch

pg_restore \
  --dbname="postgresql://USER:PASSWORD@HOST:PORT/fardb_restore_scratch" \
  --no-owner \
  --no-acl \
  --single-transaction \
  "fardb-graph-${BACKUP_TS}.dump"
```

Run key table sanity checks on any scratch restore containing graph or coordination tables:

```sql
SELECT COUNT(*) AS assets_count FROM assets;
SELECT COUNT(*) AS relationships_count FROM asset_relationships;
SELECT COUNT(*) AS regulatory_events_count FROM regulatory_events;
SELECT COUNT(*) AS rebuild_jobs_count FROM rebuild_jobs;
SELECT COUNT(*) AS distributed_locks_count FROM distributed_locks;
```

For the Auth DB, run equivalent checks for application/auth tables present in that boundary. If user credentials are stored, verify the credentials table exists and has expected row counts without exposing hashes or secrets.

For a separate Coordination DB, verify `rebuild_jobs` and `distributed_locks` from the coordination scratch restore, not from the graph scratch restore.

### 5. Backup schedule recommendation

ADR 0005 defines the retention policy:

- daily full backups with 7-day rolling retention;
- weekly snapshots retained for 30 days.

Operators should align provider PITR retention and portable `pg_dump` snapshots to that policy. Take an ad-hoc `pg_dump` before major migrations, destructive maintenance, or production restore rehearsal.

## Pre-Restore Quiescence Procedure

The goal of quiescence is to prevent new writes or rebuild synchronization while restore is being prepared.

### 1. Stop application graph mutation

Call `begin_shutdown()` from the application lifecycle boundary to transition the graph lifecycle state to `SHUTTING_DOWN` and then `STOPPED`. This prevents `synchronize_runtime_graph()` from accepting new runtime graph data while the restore is in progress.

For hosted deployments, this is usually performed by stopping traffic, disabling the affected deployment, or entering the administrative shutdown path that invokes `begin_shutdown()` before database restore. Where direct invocation is not available in the hosted environment, use deployment controls to prevent requests from reaching the backend during restore.

### 2. Verify no active rebuild is in progress

Use `/api/health/detailed` if the application is still reachable and safe to query. If the application is offline, query the effective Coordination DB directly:

```sql
SELECT job_id, status, active_worker_id, last_heartbeat_at, updated_at
FROM rebuild_jobs
WHERE status IN ('running', 'cancel_requested')
ORDER BY updated_at DESC;
```

If any active rebuild exists, prefer to wait for it to complete or fail before restore unless the restore is required because the rebuild itself corrupted state.

### 3. Handle live distributed locks before restore

Inspect the rebuild lock in the effective Coordination DB:

```sql
SELECT lock_name, holder_id, expires_at, updated_at
FROM distributed_locks
WHERE lock_name = 'graph_rebuild';
```

If the current live database contains a `distributed_locks` row with a future `expires_at`, either:

1. wait for TTL expiry; the operational maximum assumption is 300 seconds; or
2. manually delete the row after confirming no live rebuild writer from the current environment is active.

Manual deletion:

```sql
DELETE FROM distributed_locks
WHERE lock_name = 'graph_rebuild';
```

This live-database quiescence step does not clean the restored database. PITR or `pg_restore` can reintroduce historical `distributed_locks` and `rebuild_jobs` rows, so the post-restore, pre-restart cleanup step below must still be executed on the restored Coordination DB.

### 4. Record in-flight rebuild state for incident evidence

Before restoring, record any in-flight `rebuild_jobs` rows and the selected restore timestamp in the incident or rehearsal evidence. Do not rely on pre-restore updates to `rebuild_jobs` for cleanup: the restore operation overwrites the current database state with the selected historical state.

RecoveryGate false-orphan prevention must be performed after restore and before application restart, against the restored Coordination DB.

## Restore Execution Procedure

### 1. Provider-managed PITR restore

Use provider-managed PITR when available.

General procedure:

1. Identify the target restore timestamp in UTC.
2. Confirm the timestamp is inside the provider restore window.
3. Prefer restore-to-new database, branch, or project when the provider supports it.
4. Initiate restore in the provider console.
5. Record the original database identifier, restored database identifier, restore timestamp, operator, and provider job status.
6. Restore every distinct affected boundary: Auth DB, Coordination DB, Asset Graph DB, or the combined database if they share one physical database.
7. Update the target environment connection string only after scratch verification passes.

Provider notes:

- **Supabase**: initiate restore from the project backup/PITR surface. Prefer restore to a new project or safe restore target where available, then verify before switching application configuration.
- **Neon**: restore by creating a new branch at the chosen timestamp or using the provider's restore flow. Verify the branch before promoting it.
- **Vercel Postgres**: use the storage dashboard restore flow available for the attached database. Confirm whether restore is in-place or creates a separate restored instance before proceeding.

### 2. Portable `pg_restore` procedure

Prefer restoring into an empty target database. This keeps restore execution atomic with `--single-transaction` and avoids destructive cleanup of an existing database:

```bash
createdb fardb_restore_target

pg_restore \
  --dbname="$TARGET_DATABASE_URL" \
  --no-owner \
  --no-acl \
  --single-transaction \
  "fardb-graph-${BACKUP_TS}.dump"
```

Use `--clean` only when the operator has confirmed the target database can be overwritten. Do not combine `--clean` with `--single-transaction` unless the target schema is known to match the dump exactly; a failed `DROP` can abort the active transaction and roll back the entire restore. For overwrite restores, use `--if-exists` and run without `--single-transaction`:

```bash
pg_restore \
  --dbname="$TARGET_DATABASE_URL" \
  --no-owner \
  --no-acl \
  --clean \
  --if-exists \
  "fardb-graph-${BACKUP_TS}.dump"
```

If Auth DB, Coordination DB, and Asset Graph DB are separate, restore each dump to its corresponding target database. Do not restore the graph dump over the auth or coordination database, or the auth/coordination dump over the graph database.

### 3. Post-restore, pre-restart coordination cleanup

Run this step after PITR/`pg_restore` has completed and before any application process is allowed to start against the restored database. Execute it against the restored Coordination DB. If `COORDINATION_DATABASE_URL` is unset, this means the restored database reached through the settings fallback order.

Inspect restored locks:

```sql
SELECT lock_name, holder_id, expires_at, updated_at
FROM distributed_locks
WHERE lock_name = 'graph_rebuild';
```

If a restored `distributed_locks` row has a future `expires_at`, either wait for TTL expiry or delete the row after confirming the old holder cannot still be running against the restored environment:

```sql
DELETE FROM distributed_locks
WHERE lock_name = 'graph_rebuild';
```

A restored lock row with a mismatched `holder_id` can block new lock acquisition until it expires or is cleared.

Clean up restored in-flight rebuild jobs so RecoveryGate does not classify historical state as a live orphaned rebuild. For schemas using the current `sanitized_failure_category` and `sanitized_failure_message` columns:

```sql
UPDATE rebuild_jobs
SET status = 'failed',
    sanitized_failure_category = 'pre_restore_cleanup',
    sanitized_failure_message = 'Marked failed after restore and before restart to ensure clean RecoveryGate evaluation.',
    completed_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE status IN ('running', 'cancel_requested');
```

If a future schema renames `sanitized_failure_category` to `failure_category`, use the equivalent field name in that environment. The operator intent must remain `pre_restore_cleanup`.

### 4. Post-restore schema verification

For hosted PostgreSQL restores, the restored schema should come from PITR or the `pg_restore` dump. Do not run `migrations/001_initial.sql` through `psql`; the repository SQL migration files are SQLite-oriented, and a full PostgreSQL restore already contains schema and data.

If the restore point predates repository compatibility migrations, run the repository initialization path against the restored database before restarting live traffic.

Current startup behavior (verified from `src.data.database.init_db(engine)` and `src.data.migrations`):

- `Base.metadata.create_all(engine)` creates any missing ORM tables.
- On SQLite file databases, `apply_migrations()` runs repository migration steps `001` through `004` (including execution/checkpoint/cancellation columns).
- On PostgreSQL, `apply_postgresql_heartbeat_migration(engine)` applies idempotent compatibility updates to `rebuild_jobs`, including:
  - `active_worker_id`
  - `last_heartbeat_at`
  - `execution_id`
  - `checkpoint_data`
  - `cancellation_requested_at`
  - the status constraint values `('pending', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled')`

For local SQLite validation only, use `src.data.migrations.apply_migrations()`.

Inspect the expected tables:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'assets',
    'asset_relationships',
    'regulatory_events',
    'regulatory_event_assets',
    'rebuild_jobs',
    'distributed_locks'
  )
ORDER BY table_name;
```

On PostgreSQL restores, also verify rebuild compatibility columns:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'rebuild_jobs'
  AND column_name IN (
    'active_worker_id',
    'last_heartbeat_at',
    'execution_id',
    'checkpoint_data',
    'cancellation_requested_at'
  )
ORDER BY column_name;
```

Also verify the expanded status check constraint (required for `cancel_requested` / `cancelled`):

```sql
SELECT constraint_name, check_clause
FROM information_schema.check_constraints
WHERE constraint_schema = 'public'
  AND constraint_name = 'ck_rebuild_jobs_status';
```

The result should contain both `cancel_requested` and `cancelled` in `check_clause`.

If any expected compatibility column is missing, or the status constraint is absent/outdated, run the standard app initialization path before declaring restore readiness.

### 5. Rollback guidance for failed restore

If restore fails mid-way, do not attempt partial manual recovery inside the failed target database. Drop or abandon the failed target, create a new empty target, and re-run restore from the same backup or provider restore point.

If two restore attempts fail, escalate to the Incident Commander.

## Post-Restore Verification Procedure

### 1. Data integrity checks

Run row-count checks:

```sql
SELECT COUNT(*) AS assets_count FROM assets;
SELECT COUNT(*) AS relationships_count FROM asset_relationships;
SELECT COUNT(*) AS regulatory_events_count FROM regulatory_events;
SELECT COUNT(*) AS regulatory_event_assets_count FROM regulatory_event_assets;
SELECT COUNT(*) AS running_rebuild_jobs_count FROM rebuild_jobs WHERE status = 'running';
```

Run foreign-key/orphan checks for graph relationships:

```sql
SELECT COUNT(*) AS orphaned_relationships
FROM asset_relationships ar
LEFT JOIN assets source_asset ON source_asset.id = ar.source_asset_id
LEFT JOIN assets target_asset ON target_asset.id = ar.target_asset_id
WHERE source_asset.id IS NULL OR target_asset.id IS NULL;
```

Run regulatory event orphan checks. The current schema has both a primary event asset on `regulatory_events.asset_id` and related assets through the `regulatory_event_assets` join table, so verify both relationships:

```sql
SELECT COUNT(*) AS orphaned_primary_regulatory_events
FROM regulatory_events re
LEFT JOIN assets primary_asset ON primary_asset.id = re.asset_id
WHERE primary_asset.id IS NULL;

SELECT COUNT(*) AS orphaned_regulatory_event_assets
FROM regulatory_event_assets rea
LEFT JOIN regulatory_events re ON re.id = rea.event_id
LEFT JOIN assets related_asset ON related_asset.id = rea.asset_id
WHERE re.id IS NULL OR related_asset.id IS NULL;
```

Expected results:

- `running_rebuild_jobs_count` is `0`.
- orphan counts are `0`.
- `assets_count` and `relationships_count` match the selected backup/scratch restore baseline or the approved restored source-data baseline.

### 2. Application restart and health verification

Restart the backend process or trigger a new Vercel deployment after updating database connection strings.

Verify health:

```bash
curl -fsS "$BASE_URL/api/health/detailed"
```

Expected result:

- `/api/health/detailed` returns a healthy status.
- In staging and production, startup evidence confirms the graph loaded from persisted durable graph truth, not fallback sample/cache generation.

Where the hosted readiness checker is available, run:

```bash
python scripts/check_hosted_readiness.py "$BASE_URL" --require-persistence
```

### 3. Functional smoke test

Trigger an existing graph-read path and verify a valid response. The canonical lightweight read endpoint is the paginated assets endpoint:

```bash
curl -fsS "$BASE_URL/api/assets?per_page=1"
```

Expected result:

- The response is valid JSON.
- The response includes the paginated assets contract (`items`, `total`, `page`, `per_page`, `has_more`).
- `total` matches the restored baseline or the approved post-rebuild baseline.

Optional additional checks when an approved sentinel baseline exists:

```bash
curl -fsS "$BASE_URL/api/relationships"
curl -fsS "$BASE_URL/api/visualization"
```

Confirm expected sentinel assets and directed relationship strengths are present.

## Operator Ownership

The deploying organization must assign named owners for the following roles before treating staging or production as enterprise-ready.

| Role                   | Responsibility                                                                                                                                                 | Required access                                                                               |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **Backup Operator**    | Verifies provider-managed backup health, confirms retention windows, and executes ad-hoc backups before major changes.                                         | Provider console read access, database read/backup access, secure backup storage access.      |
| **Restore Operator**   | Executes restore procedures, runs post-restore/pre-restart cleanup, performs post-restore verification, and updates database connection strings when approved. | Database admin access, provider console restore access, Vercel environment/deployment access. |
| **Incident Commander** | Owns escalation, coordinates restore decisions, accepts residual risk, and decides whether RTO breach or data loss must be declared.                           | Incident-management authority and access to the responsible engineering/operator contacts.    |

One person may hold multiple roles, but the active role for each incident must be explicit in the incident record.

Escalate to the Incident Commander if:

- restore fails after two attempts;
- data integrity checks fail after restore;
- the 2-hour RTO threshold is at risk of being exceeded;
- the selected restore point implies data loss beyond the documented RPO;
- provider-managed PITR is unavailable when it was assumed available;
- restored coordination state suggests split-brain or unsafe rebuild ownership.

Contact and paging routing for the DashFin-FarDb deployment:

- Backup Operator contact: DashFin-FarDb Operations / designated backup owner.
- Restore Operator contact: DashFin-FarDb Operations / designated database restore owner.
- Incident Commander contact: DashFin-FarDb Operations / designated production incident lead.
- Paging/escalation channel: DashFin-FarDb production incident channel and provider emergency-support channel for the active hosted database provider.

Private personal contact details, phone numbers, and provider account identifiers must remain in the deploying organization's private incident-management system, not in this public repository.

## Completion Criteria

A restore incident or rehearsal is complete only when:

1. the selected database restore point is documented;
2. stale lock and in-flight rebuild job state have been resolved on the restored Coordination DB;
3. schema verification passes;
4. graph integrity checks pass;
5. the application has restarted successfully;
6. `/api/health/detailed` is healthy;
7. lifecycle state reaches `READY`;
8. graph functional smoke testing passes;
9. hosted readiness with `--require-persistence` passes for staging/production restore rehearsal evidence;
10. RPO target, observed RPO, RTO target, and observed RTO are recorded;
11. any RPO/RTO target miss is classified as blocking or non-blocking with a follow-up issue;
12. the restore rehearsal evidence record is attached to the release-candidate evidence issue or incident record;
13. the Incident Commander or designated promotion approver accepts closure.

## Restore Rehearsal Evidence Record

Use this structure in the release-candidate evidence issue or incident record. Do not include secrets, raw database URLs,
database dump contents, bearer tokens, private keys, or unredacted logs.

```text
Restore rehearsal date:
Restore operator:
Source environment:
Restore point:
Restore target:
Backup/restore mechanism:
Effective database-boundary topology:
Auth DB boundary result:
Coordination DB boundary result:
Asset graph DB boundary result:
Scratch restore verification results:
Target miss classification (blocking/non-blocking):
Readiness requirement: hosted readiness run with --require-persistence
Post-restore readiness result:
Post-restore health evidence:
Post-restore assets/sentinel evidence:
Persisted graph startup source:
Persisted graph counts or sentinel baseline:
RPO target:
Observed RPO:
RTO target:
Observed RTO:
Decision: Passed / Failed / Blocked
Follow-up issues:
```

# Backup, Restore, and Disaster Recovery Runbook

For strategy, recovery objectives, and data classification, see [ADR 0005: Backup, Restore, and Disaster Recovery Strategy](../adr/0005-backup-restore-dr-strategy.md).

## Preamble

This runbook defines operator procedures for backing up, restoring, and verifying FarDb staging and production databases.

Use this runbook when:

- verifying provider-managed backup/PITR health;
- taking an ad-hoc backup before a risky migration, deployment, or destructive operation;
- restoring the Auth/Coordination DB, the Asset Graph DB, or both;
- recovering from data loss, accidental destructive writes, failed migrations, or database-provider incidents;
- proving that restore procedures remain executable for enterprise release readiness.

The intended audience is operators with database, hosting, and deployment authority. It is not an end-user support document.

This runbook distinguishes application rollback from data restore. Vercel rollback/promotion restores application code and configuration only; it does not restore database state.

## Prerequisites

Operators must have the following access before starting backup or restore work:

- Database administrator credentials or equivalent connection strings for each affected database.
- Vercel dashboard access for environment variables, deployment restart/redeployment, and rollback/promotion operations.
- Provider console access for the hosted PostgreSQL provider, such as Supabase, Neon, or Vercel Postgres.
- Permission to read and update `DATABASE_URL`, `POSTGRES_URL`, `ASSET_GRAPH_DATABASE_URL`, and any provider-specific database settings.
- Secure storage for portable dump files when using `pg_dump`.
- Access to deployment logs and `GET /api/health/detailed` for post-restore verification.

Do not paste database credentials, full connection strings, backup contents, or raw exception traces into public issues, PR comments, or support channels.

## Backup Procedures

### 1. Identify database boundaries

FarDb may use one or two logical PostgreSQL database boundaries:

- Auth/Coordination DB: `DATABASE_URL`, with `POSTGRES_URL` as a provider fallback where configured.
- Asset Graph DB: `ASSET_GRAPH_DATABASE_URL`.

If `DATABASE_URL` and `ASSET_GRAPH_DATABASE_URL` resolve to different connection strings, back up both. If they point to the same physical database, one full database backup may cover both boundaries, but the operator must record that topology in the incident or release evidence.

### 2. Provider-managed backup verification

Provider-managed PITR is the primary mechanism for hosted PostgreSQL.

For each affected environment:

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

Resolve the connection strings from the target environment:

```bash
# Auth/Coordination DB
export AUTH_DATABASE_URL="$DATABASE_URL"

# Provider fallback if DATABASE_URL is intentionally unset
export AUTH_DATABASE_URL="${AUTH_DATABASE_URL:-$POSTGRES_URL}"

# Asset Graph DB
export GRAPH_DATABASE_URL="$ASSET_GRAPH_DATABASE_URL"
```

Create timestamped dump files:

```bash
export BACKUP_TS="$(date -u +%Y%m%dT%H%M%SZ)"

pg_dump "$AUTH_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="fardb-auth-${BACKUP_TS}.dump"

pg_dump "$GRAPH_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="fardb-graph-${BACKUP_TS}.dump"
```

If both environment variables point to the same database, run a single dump and label it clearly:

```bash
pg_dump "$DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="fardb-combined-${BACKUP_TS}.dump"
```

Store dumps in the approved backup location for the deploying organization. Do not commit dump files to the repository.

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

Run key table sanity checks:

```sql
SELECT COUNT(*) AS assets_count FROM assets;
SELECT COUNT(*) AS relationships_count FROM asset_relationships;
SELECT COUNT(*) AS regulatory_events_count FROM regulatory_events;
SELECT COUNT(*) AS rebuild_jobs_count FROM rebuild_jobs;
SELECT COUNT(*) AS distributed_locks_count FROM distributed_locks;
```

For the Auth/Coordination DB, run equivalent checks for application/auth tables present in that boundary. If user credentials are stored, verify the credentials table exists and has expected row counts without exposing hashes or secrets.

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

Use `/api/health/detailed` if the application is still reachable and safe to query. If the application is offline, query the database directly:

```sql
SELECT job_id, status, active_worker_id, last_heartbeat_at, updated_at
FROM rebuild_jobs
WHERE status IN ('running', 'cancel_requested')
ORDER BY updated_at DESC;
```

If any active rebuild exists, prefer to wait for it to complete or fail before restore unless the restore is required because the rebuild itself corrupted state.

### 3. Handle distributed locks

Inspect the rebuild lock:

```sql
SELECT lock_name, holder_id, expires_at, updated_at
FROM distributed_locks
WHERE lock_name = 'graph_rebuild';
```

If a `distributed_locks` row exists with a future `expires_at`, either:

1. wait for TTL expiry; the operational maximum assumption is 300 seconds unless `REBUILD_LOCK_TTL_SECONDS` has been configured differently; or
2. manually delete the row after confirming no live rebuild writer from the restored environment is active.

Manual deletion:

```sql
DELETE FROM distributed_locks
WHERE lock_name = 'graph_rebuild';
```

A restored lock row with a mismatched `holder_id` can block new lock acquisition until it expires or is cleared.

### 4. Clean up in-flight rebuild jobs

Before restarting the application after restore, prevent RecoveryGate from detecting false orphaned jobs caused by restored historical state.

For schemas using the current `sanitized_failure_category` and `sanitized_failure_message` columns:

```sql
UPDATE rebuild_jobs
SET status = 'failed',
    sanitized_failure_category = 'pre_restore_cleanup',
    sanitized_failure_message = 'Marked failed during pre-restore cleanup to ensure clean restart.',
    completed_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE status IN ('running', 'cancel_requested');
```

If a future schema renames `sanitized_failure_category` to `failure_category`, use the equivalent field name in that environment. The operator intent must remain `pre_restore_cleanup`.

## Restore Execution Procedure

### 1. Provider-managed PITR restore

Use provider-managed PITR when available.

General procedure:

1. Identify the target restore timestamp in UTC.
2. Confirm the timestamp is inside the provider restore window.
3. Prefer restore-to-new database, branch, or project when the provider supports it.
4. Initiate restore in the provider console.
5. Record the original database identifier, restored database identifier, restore timestamp, operator, and provider job status.
6. Update the target environment connection string only after scratch verification passes.

Provider notes:

- **Supabase**: initiate restore from the project backup/PITR surface. Prefer restore to a new project or safe restore target where available, then verify before switching application configuration.
- **Neon**: restore by creating a new branch at the chosen timestamp or using the provider's restore flow. Verify the branch before promoting it.
- **Vercel Postgres**: use the storage dashboard restore flow available for the attached database. Confirm whether restore is in-place or creates a separate restored instance before proceeding.

### 2. Portable `pg_restore` procedure

Prepare the target database. Prefer an empty database for restore:

```bash
createdb fardb_restore_target
```

Alternatively, use `--clean` only when the operator has confirmed the target database can be overwritten:

```bash
pg_restore \
  --dbname="$TARGET_DATABASE_URL" \
  --no-owner \
  --no-acl \
  --single-transaction \
  --clean \
  "fardb-graph-${BACKUP_TS}.dump"
```

For an empty target database:

```bash
pg_restore \
  --dbname="$TARGET_DATABASE_URL" \
  --no-owner \
  --no-acl \
  --single-transaction \
  "fardb-graph-${BACKUP_TS}.dump"
```

If Auth/Coordination DB and Asset Graph DB are separate, restore each dump to its corresponding target database. Do not restore the graph dump over the auth database or the auth dump over the graph database.

### 3. Post-restore schema verification

Run the base schema migration idempotently where applicable:

```bash
psql "$TARGET_DATABASE_URL" -f migrations/001_initial.sql
```

For local SQLite restore validation, run the repository migration helper or the migration scripts according to the current local development procedure. For PostgreSQL-hosted environments, confirm the ORM-created schema and provider migration compatibility before switching live traffic.

Then inspect the expected tables:

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

### 4. Rollback guidance for failed restore

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

Run regulatory event orphan checks:

```sql
SELECT COUNT(*) AS orphaned_regulatory_events
FROM regulatory_events re
LEFT JOIN assets asset ON asset.id = re.asset_id
WHERE asset.id IS NULL;

SELECT COUNT(*) AS orphaned_regulatory_event_assets
FROM regulatory_event_assets rea
LEFT JOIN regulatory_events re ON re.id = rea.event_id
LEFT JOIN assets asset ON asset.id = rea.asset_id
WHERE re.id IS NULL OR asset.id IS NULL;
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
- The graph lifecycle state reaches `READY`.
- In staging and production, startup evidence confirms the graph loaded from persisted durable graph truth, not fallback sample/cache generation.

Where the hosted readiness checker is available, run:

```bash
python scripts/check_hosted_readiness.py "$BASE_URL" --require-persistence
```

### 3. Functional smoke test

Trigger a graph read path and verify a valid response:

```bash
curl -fsS "$BASE_URL/api/graph/"
```

If the graph endpoint path differs in the deployed API version, use the canonical graph-read endpoint for that deployment. The smoke test must prove that the API can read restored graph state from the running service.

Optional additional checks when an approved sentinel baseline exists:

```bash
curl -fsS "$BASE_URL/api/assets"
curl -fsS "$BASE_URL/api/relationships"
```

Confirm expected sentinel assets and directed relationship strengths are present.

## Operator Ownership

The deploying organization must assign named owners for the following roles before treating staging or production as enterprise-ready.

| Role | Responsibility | Required access |
| --- | --- | --- |
| **Backup Operator** | Verifies provider-managed backup health, confirms retention windows, and executes ad-hoc backups before major changes. | Provider console read access, database read/backup access, secure backup storage access. |
| **Restore Operator** | Executes restore procedures, runs pre-restore cleanup, performs post-restore verification, and updates database connection strings when approved. | Database admin access, provider console restore access, Vercel environment/deployment access. |
| **Incident Commander** | Owns escalation, coordinates restore decisions, accepts residual risk, and decides whether RTO breach or data loss must be declared. | Incident-management authority and access to the responsible engineering/operator contacts. |

One person may hold multiple roles, but the active role for each incident must be explicit in the incident record.

Escalate to the Incident Commander if:

- restore fails after two attempts;
- data integrity checks fail after restore;
- the 2-hour RTO threshold is at risk of being exceeded;
- the selected restore point implies data loss beyond the documented RPO;
- provider-managed PITR is unavailable when it was assumed available;
- restored coordination state suggests split-brain or unsafe rebuild ownership.

Contact and paging information is organization-specific and must be filled by the deploying team:

- Backup Operator contact: `TODO(deploying-team)`
- Restore Operator contact: `TODO(deploying-team)`
- Incident Commander contact: `TODO(deploying-team)`
- Paging/escalation channel: `TODO(deploying-team)`

## Completion Criteria

A restore incident or rehearsal is complete only when:

1. the selected database restore point is documented;
2. stale lock and in-flight rebuild job state have been resolved;
3. schema verification passes;
4. graph integrity checks pass;
5. the application has restarted successfully;
6. `/api/health/detailed` is healthy;
7. lifecycle state reaches `READY`;
8. graph functional smoke testing passes;
9. the Incident Commander or designated promotion approver accepts closure.

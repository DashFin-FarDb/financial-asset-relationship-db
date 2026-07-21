# Enterprise Deployment Operating Model

For the enterprise-readiness audit, roadmap, PR plan, board, and release criteria, see [docs/enterprise-readiness-index.md](./enterprise-readiness-index.md).

This document defines how the Financial Asset Relationship Database (FarDb) is deployed,
promoted, verified, rolled back, and operated across environments. It distinguishes
between basic service readiness and the stronger durable graph-persistence verification
required for staging and production promotion.

For staging-specific provider boundaries, Vercel environment mapping, preview durability labelling, and promotion
evidence capture, see the [Staging Deployment Operating Baseline](staging-deployment-operating-baseline.md).

For current rebuild/recovery/persistence state-machine semantics, ownership rules, and exception paths, see the canonical [State Machine and Operating Authority](governance/state-machine-and-operating-authority.md).

## Operating Topology

The current selected initial topology is:

- **Frontend host**: Vercel-hosted Next.js frontend.
- **Backend host**: Vercel serverless FastAPI entrypoint using the monorepo deployment model.
- **Graph persistence store**: PostgreSQL-compatible durable store for hosted graph truth.
  Provider choice remains flexible unless selected by a later child issue.
- **Application database store**: PostgreSQL-compatible store for auth/application state in
  staging and production. SQLite is acceptable for local development and explicitly labelled
  non-durable preview/demo deployments only; it must not be treated as staging/production
  durable persistence.
- **Secret source**: Vercel environment variables for hosted deployments.

### Environment Separation

- **Local**: Developer-owned runtime for development and testing. SQLite is allowed.
- **Preview**: May be durable or non-durable. If non-durable, the deployment must be labeled accordingly and must not be treated as proof of production persistence behavior.
- **Staging**: Durable pre-production verification environment. Must use the same persistence boundary class expected for production. The staging provider, Vercel project/deployment mapping, database boundaries, variable-presence checks, preview durability label, and promotion evidence are governed by the [Staging Deployment Operating Baseline](staging-deployment-operating-baseline.md).
- **Production**: Durable authoritative environment.

### Rollback and Restore Ownership

- **Deployment rollback owner**: Designated maintainer/operator with authority to promote a previous known-good Vercel deployment.
- **Data restore owner**: Designated Restore Operator responsible for executing [the backup/restore/DR runbook](runbooks/backup-restore-dr.md) when database recovery is required.
- **Backup/restore runbook status**: Backup, restore, and DR procedures are documented in [docs/runbooks/backup-restore-dr.md](runbooks/backup-restore-dr.md). Strategy and objectives are documented in [ADR 0005](adr/0005-backup-restore-dr-strategy.md).

## Deployment Ownership

- **Frontend**: The Next.js frontend is deployed and served through Vercel.
- **Backend**: The FastAPI backend is deployed through Vercel using the production `api.main:app` entrypoint.

## Required Environment Variables

### Application Database

The application database stores user credentials and other API-level state.

- `DATABASE_URL`: Connection string for the auth/application database.
  - Local/dev: SQLite is acceptable.
  - Preview/demo: SQLite may be used only when the deployment is explicitly labelled non-durable. PostgreSQL-compatible storage is required when preview is used to validate durable persistence behaviour.
  - Staging/production: PostgreSQL-compatible durable database is required.
- `POSTGRES_URL`: Provider fallback used only when `DATABASE_URL` is not set.

### Graph Persistence

The graph persistence store holds durable graph truth. Evidence/metadata persistence is not yet implemented in the current schema/ORM and remains deferred as future work.

- `ASSET_GRAPH_DATABASE_URL`: Connection string for graph persistence.
- `ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL`.
- A healthy auth/application database does **not** prove graph persistence is configured.
- A deployment can serve a graph in memory even when `ASSET_GRAPH_DATABASE_URL` is unset or empty because startup may fall back to cache, real-data fetcher, or sample graph generation.

### Other Required Settings

- `SECRET_KEY`: Long random string for JWT signing.
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`: Bootstrap credentials when the auth/application database does not yet contain a usable user.

### Rebuild coordination (optional)

- `REBUILD_LOCK_TTL_SECONDS`: Time-to-live for the graph rebuild distributed lock in seconds (default: 300). Must be a positive integer. Loaded via `src/config/settings.py` and propagated to graph rebuild orchestration. The heartbeat refresh interval is `max(1, rebuild_lock_ttl_seconds // 3)` per [ADR 0003](adr/0003-distributed-lock-refresh-and-heartbeat-strategy.md).
- `COORDINATION_DATABASE_URL`: Optional PostgreSQL-compatible coordination database connection string for rebuild lock/job coordination. When unset, coordination uses the same boundary as the graph/application startup configuration for the active environment. All backend instances sharing one `ASSET_GRAPH_DATABASE_URL` must share the same coordination database boundary.

## Distributed Hosting Semantics

For the historical decision record, see
[ADR 0004: Distributed Hosting Semantics](adr/0004-distributed-hosting-semantics.md). For current state-machine, ownership, and exception authority, see the canonical [State Machine and Operating Authority](governance/state-machine-and-operating-authority.md).

FarDb supports backend scale-out for read serving using a single-writer /
multi-reader model:

- Multiple backend instances may serve read traffic from runtime graph
  snapshots.
- Scale-out does **not** increase rebuild writer concurrency.
- Operators must assume one rebuild writer globally per graph persistence
  boundary.
- A rebuild writer must hold the `graph_rebuild` distributed lock before
  mutating rebuild state or persisting graph truth.
- A backend instance that does not hold the rebuild lock may serve reads but
  must not persist graph truth.

### Distributed Hosting and Rebuild Ownership

All instances sharing `ASSET_GRAPH_DATABASE_URL` must share the same
coordination database boundary, configured through `COORDINATION_DATABASE_URL`
when that boundary differs from the default environment database boundary.
`REBUILD_LOCK_TTL_SECONDS` must be consistent across instances in the same
environment.

Durable graph truth in `ASSET_GRAPH_DATABASE_URL` is authoritative for staging
and production. Runtime graph state is an in-memory cache/snapshot. A healthy
application database or bounded health response does not prove durable graph
truth.

Rolling redeploy may leave an in-flight rebuild in stale state. Recovery must
occur through lock expiry plus RecoveryGate-approved reconciliation, not blind
takeover. If another worker has a fresh heartbeat, lock ownership cannot be
proven, persistence is unavailable, or split-brain is suspected, the system must
block mutation. Manual operator intervention is required for suspected
split-brain.

Restart/redeploy expectations:

1. With no in-flight rebuild, the new backend instance loads durable graph truth
   and records persisted startup evidence.
2. While another instance is actively rebuilding, a restarted instance must not
   take over if the active owner is freshly heartbeating.
3. If redeploy kills the active rebuild owner, a later instance may recover only
   after stale-owner conditions and lock reacquisition requirements are
   satisfied.
4. During persistence commit, lock loss or uncertain ownership requires the
   writer to abort before commit or success marking.

## Promotion Gates

Promotion requires two different kinds of verification.

### 1. Basic Readiness Gate

The basic readiness gate confirms the service is up and bounded readiness checks are healthy.

Required evidence:

1. Deployment completed successfully.
2. Frontend is reachable.
3. Backend is reachable.
4. `GET /api/health/detailed` returns `status: "healthy"`.
5. Auth/application database reachability is confirmed.

This gate proves bounded readiness only. It does **not** prove the runtime graph was loaded from durable persisted graph truth.

### 2. Durable Graph-Persistence Gate for Staging and Production

Staging and production promotions require explicit proof that the runtime graph was loaded from the durable graph-persistence boundary.

Required evidence:

1. `ASSET_GRAPH_DATABASE_URL` is configured for the target environment.
2. Graph truth is created or refreshed through the explicit authenticated rebuild/persist path, or an approved persisted baseline is used.
3. Backend is restarted or redeployed after persistence is written.
4. Startup evidence confirms persisted graph load rather than fallback generation.
5. Bounded graph counts match the expected persisted baseline.

Recommended diagnostic evidence, when an approved sentinel baseline exists:

1. Sentinel assets are visible through `GET /api/assets`.
2. Directed relationship strengths are visible through `GET /api/relationships`.

### Gate Interpretation Rules

- Preview deployments may pass a basic readiness gate without proving durable graph persistence if they are intentionally non-durable.
- Staging and production promotions must not rely on `GET /api/health/detailed` alone as proof of durable graph truth.

## Verification and Smoke Testing

`GET /api/health/detailed` is a bounded readiness signal only. It confirms in-memory graph availability and auth/application database reachability. It does **not** prove the graph was loaded from `ASSET_GRAPH_DATABASE_URL` unless verified via the persistence-gate check.

For staging and production deployment acceptance, operators must run this durable graph-persistence smoke procedure:

1. Confirm `ASSET_GRAPH_DATABASE_URL` is set in the target environment.
2. Trigger a controlled authenticated graph rebuild/persist operation through `POST /api/graph/rebuild`, or use an approved persisted baseline.
3. Restart or redeploy the backend.
4. Run the hosted readiness checker with `--require-persistence` configured:

   ```bash
   python scripts/check_hosted_readiness.py <base_url> --require-persistence
   ```

5. Confirm the checker exits successfully (exit code 0), verifying that:
   - `/api/health/detailed` `status` is `healthy`
   - `graph.persistence_loaded` is `true`
   - `graph.startup_source` is `"persisted"`
   - graph counts match the expected persisted baseline
   - auth/application database is reachable
6. If an approved sentinel baseline exists, call `GET /api/assets` and confirm known sentinel asset IDs are present.
7. If an approved sentinel baseline exists, call `GET /api/relationships` and confirm known directed relationship strengths are present.
8. Record bounded evidence only. Do not capture secrets, raw connection strings, full graph dumps, or raw exception text.

## Rollback Process

### Deployment Rollback Boundary

- Use Vercel rollback/promotion to restore the previous known-good deployment.
- Deployment rollback affects deployed application code and configuration only.
- Deployment rollback is **not** automatic data restoration.

### Rollback Triggers

Rollback should be considered when any of the following occur after deployment:

- `GET /api/health/detailed` reports degraded readiness.
- Durable graph-persistence smoke fails.
- Sentinel assets or directed relationships are missing after restart/redeploy.
- Severe frontend or backend regression is introduced.

### Post-Rollback Verification

After rollback:

1. Verify frontend reachability.
2. Verify backend reachability.
3. Verify `GET /api/health/detailed` reports `status: "healthy"`.
4. For staging and production, rerun the durable graph-persistence smoke procedure before closing the incident.
5. Dispatch `.github/workflows/post-recovery-readiness.yml` with `recovery_context=post-rollback` and the affected `target_environment`, then attach the `post-rollback-readiness` artifact (H-P1-03) before closing the incident.

### Data Restore Boundary

- Data restore is documented in [docs/runbooks/backup-restore-dr.md](runbooks/backup-restore-dr.md).
- Rollback is not equivalent to database restore.
- Operators must treat schema changes and destructive data operations as restore-sensitive changes and should take an ad-hoc backup before executing them.

## Disaster Recovery

FarDb disaster recovery is governed by [ADR 0005: Backup, Restore, and Disaster Recovery Strategy](adr/0005-backup-restore-dr-strategy.md) and executed through [the backup/restore/DR runbook](runbooks/backup-restore-dr.md).

ADR 0005 defines the staging/production recovery objectives:

- graph data RPO is tied to approved source-data freshness because graph data is rebuildable through `RebuildExecutor`;
- coordination/auth data RPO is 1 hour;
- full service RTO is 2 hours, including restore verification;
- provider-managed PITR is primary for hosted PostgreSQL, with `pg_dump` as the portable fallback.

A Vercel rollback/promotion can recover a previous application deployment, but it does **not** restore `DATABASE_URL`, `POSTGRES_URL`, or `ASSET_GRAPH_DATABASE_URL` data. When data loss, destructive writes, failed migrations, or corrupted graph persistence are suspected, operators must use the DR runbook rather than treating deployment rollback as sufficient recovery.

## Secret Handling

- **Production/Staging**: Secrets such as `SECRET_KEY`, `ADMIN_PASSWORD`, `DATABASE_URL`, `POSTGRES_URL`, and `ASSET_GRAPH_DATABASE_URL` must be configured through the hosting platform's secret-management surface and must never be checked into version control.
- **Preview**: Non-production secrets must still be handled through environment-variable management and must not be embedded in code or docs.
- **Local Development**: Use a local `.env` file or equivalent local environment configuration. Keep it out of version control.

## Operator Responsibilities

The operating model assumes named ownership for the following functions:

- **Deploy operator**: Executes deployment to the target environment.
- **Promotion approver**: Confirms promotion gates are satisfied before staging/production promotion.
- **Rollback executor**: Performs Vercel rollback/promotion to restore the previous known-good deployment.
- **Backup Operator**: Verifies backup health and executes ad-hoc backups before major changes.
- **Restore Operator**: Executes database restore procedures and post-restore verification according to the DR runbook.
- **Secret/config maintainer**: Owns environment-variable configuration and secret rotation.
- **Persistence-verification operator**: Executes and records the durable graph-persistence smoke procedure.
- **Incident Commander**: Escalation point for restore failures, data loss events, and RTO/RPO risk.

The canonical [State Machine and Operating Authority](governance/state-machine-and-operating-authority.md) defines the same operating roles plus explicit rebuild recovery, exception approval, and manual-intervention handoff boundaries.

One person may hold multiple roles, but the responsibilities must be explicit.

## Incident Response Outline

When the deployment is degraded or promotion evidence is incomplete:

1. **Detect**: Check `GET /api/health/detailed` and determine whether the problem is basic readiness or durable graph-persistence verification.
2. **Classify**: Identify which of these conditions applies:
   - degraded readiness
   - durable graph smoke failure
   - missing persisted graph after restart
   - auth/application database unreachable
   - non-durable preview assumptions being incorrectly treated as staging/production evidence
   - suspected data loss or restore requirement
3. **Inspect**: Review backend logs and deployment metadata without exposing secrets to end users.
4. **Mitigate**: Roll back application code/configuration when the current deployment is not trustworthy, or execute the DR runbook when database restore is required.
5. **Re-verify**: Re-run the appropriate readiness, durable graph-persistence, and post-restore checks before restoring promotion confidence.

# Database migration authority

**Applies to:** current FarDB graph, coordination, GRAC, and API credential schemas.
**Command:** `python -m scripts.migrate_database`
**Authority:** an explicit operator execution using migration-owner credentials.

## Contract

FastAPI runtime startup is a read-only compatibility boundary. It checks required tables, columns, named constraints,
indexes, GRAC immutability triggers, PostgreSQL RLS/grant posture, and the API credential schema. It fails closed when
the configured databases are absent or incompatible and never attempts repair.

The operator command is the only supported mutating setup path for this tranche. It wraps the existing custom
migration mechanics and owns:

- SQLAlchemy ORM table creation;
- SQLite compatibility migrations;
- PostgreSQL rebuild-job columns, widths, and status constraint;
- GRAC projection metadata/backfill, checks, triggers, RLS, and grant hardening;
- `user_credentials` table creation and optional initial credential provisioning.

This command does not establish the durable PostgreSQL migration ledger or historical drift baseline. That remains
CQ-03. Do not represent a successful command run as CQ-03 closure.

## First setup or schema-relevant deployment

1. Stop traffic to an unprepared target, or run before deploying application instances that require the new schema.
2. Configure the existing database URL variables with migration-owner credentials for the intended graph,
   coordination, and auth boundaries. Existing URL precedence is unchanged.
3. Configure `SECRET_KEY`. For initial credential provisioning, also configure `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and
   optional `ADMIN_EMAIL`, `ADMIN_FULL_NAME`, or `ADMIN_DISABLED`.
4. Run:

   ```bash
   python -m scripts.migrate_database
   ```

5. Require exit status 0 and record only the emitted component names (`graph`, `coordination`, `auth`). Never record
   raw database URLs or secrets.
6. Replace migration-owner URLs with restricted application-role URLs. Remove `ADMIN_PASSWORD` from the runtime
   environment. Keep `ADMIN_USERNAME` only when required for rebuild-operator authorization.
7. Start FastAPI. A compatibility failure is a deployment blocker: return to this procedure rather than broadening
   the app role.
8. Run the hosted readiness and database-authorization evidence required by the target environment.

When graph and coordination share one URL, the command initializes that engine once. When no durable graph URL is
configured for a local demo, it initializes only the auth database.

## Local SQLite example

```bash
export DATABASE_URL=sqlite:dev.db
export SECRET_KEY=replace-with-a-long-random-secret
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=replace-with-a-strong-password
python -m scripts.migrate_database
unset ADMIN_PASSWORD
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Set `ASSET_GRAPH_DATABASE_URL` and, when separated, `COORDINATION_DATABASE_URL` before the command when local work
requires durable graph/reconciliation persistence.

## Failure and rollback

- A missing-schema or incompatible-schema startup error is evidence that the operator step did not complete against
  the runtime target. Do not retry by granting CREATE, ALTER, TRIGGER, ownership, or grant-management authority to the
  application role.
- If the command fails, retain the target for diagnosis when safe, use the backup/restore procedure for destructive or
  partial migration concerns, and rerun only after the cause is understood.
- Code rollback may restore the prior application version, but database rollback follows the schema change's reviewed
  rollback/restore plan. Restoring the old startup mutation path is not an operational recovery procedure.
- Stop for human review when a new migration tool, dependency, credential channel, destructive provider action, or
  schema-history decision is required.

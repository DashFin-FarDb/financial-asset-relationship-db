# Database migration authority

**Applies to:** current FarDB graph, coordination, GRAC, and API credential schemas.
**Command:** `python -m scripts.migrate_database`
**Authority:** an explicit operator execution using migration-owner credentials.

## Contract

FastAPI runtime startup is a read-only compatibility boundary. It checks required tables, columns, named constraints,
indices, GRAC immutability triggers, PostgreSQL RLS/grant posture, and the API credential schema. It fails closed when
the configured databases are absent or incompatible and never attempts repair.

The operator command is the only supported mutating setup path for this tranche. It wraps the existing custom
migration mechanics and owns:

- SQLAlchemy ORM table creation;
- SQLite compatibility migrations;
- PostgreSQL rebuild-job columns, widths, and status constraint;
- GRAC projection metadata/backfill, checks, immutable-write triggers, exact named RLS policies, and grant hardening;
- `user_credentials` table creation and optional initial credential provisioning;
- stable PostgreSQL `NOLOGIN` capability roles and their exact grants/policies:
  `fardb_runtime_graph`, `fardb_runtime_coordination`, and `fardb_runtime_auth`.

The command creates capability roles but deliberately does not create login roles, passwords, connection strings, or
provider configuration. Runtime login creation, credential custody, role membership, and URL replacement remain a
separate human-controlled provider operation.

## PostgreSQL runtime capability contract

| Capability role | Intended login boundary | Effective data authority |
| --- | --- | --- |
| `fardb_runtime_auth` | `DATABASE_URL` / auth | `SELECT` on `user_credentials`; no credential writes |
| `fardb_runtime_graph` | `ASSET_GRAPH_DATABASE_URL` | graph-domain DML required by repositories; rebuild-job `SELECT`/`INSERT`/`UPDATE`; GRAC `SELECT`/`INSERT` |
| `fardb_runtime_coordination` | `COORDINATION_DATABASE_URL` | `SELECT`/`INSERT`/`UPDATE`/`DELETE` on `distributed_locks` |

GRAC remains physically immutable. PostgreSQL requires UPDATE authority and an UPDATE policy for
`SELECT ... FOR UPDATE`, so the graph capability receives UPDATE only on each GRAC primary-key `id` column and an
exact `fardb_graph_lock_v1` policy with `WITH CHECK (false)`. This supports lifecycle row locking but cannot perform
an update; immutable triggers continue to reject UPDATE, DELETE, and TRUNCATE as defense in depth.

Every runtime login must be `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`, own no protected FarDB object, have no
database/schema `CREATE`, and be a member of exactly the capability roles its URL needs. Do not grant runtime logins
direct table privileges. A shared graph/coordination URL needs both graph and coordination memberships; separated
URLs need one each. The auth login needs only auth membership. Startup rejects missing, extra, elevated, or drifted
capability authority.

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
6. In the provider's protected operator surface, create or select the three restricted login identities and grant
   only the applicable capability membership. For example, the reviewed equivalent of
   `GRANT fardb_runtime_graph TO <graph_login>` belongs on the graph boundary; use both graph and coordination
   memberships only when those boundaries deliberately share one URL. Do not paste login names or commands with
   credentials into public evidence.
7. Replace migration-owner URLs with the corresponding restricted-login URLs. Remove `ADMIN_PASSWORD` from the
   runtime environment. Keep `ADMIN_USERNAME` only when required for rebuild-operator authorization.
8. Start FastAPI. A compatibility failure is a deployment blocker: return to this procedure rather than broadening
   the app role.
9. Prove cold start and restart, exercise graph/coordination/auth runtime operations, and run the hosted readiness and
   database-authorization evidence required by the target environment.

For an isolated PostgreSQL rehearsal, the opt-in integration contract accepts restricted DSNs only through
`FARDB_GRAPH_RUNTIME_DATABASE_URL`, `FARDB_COORDINATION_RUNTIME_DATABASE_URL`, and
`FARDB_AUTH_RUNTIME_DATABASE_URL`, with `RUN_POSTGRES_TESTS=1`. These values are secrets: run the test from an
approved operator environment and retain only bounded pass/fail evidence. The test does not create logins, grant
memberships, or change provider configuration.

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

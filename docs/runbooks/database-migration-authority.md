# Database migration authority

**Applies to:** current FarDB graph, coordination, GRAC, and API credential schemas.
**Commands:** superuser role bootstrap, then `python -m scripts.migrate_database`
**Authority:** two explicit operator executions with separate superuser and migration-owner credentials.

## Contract

FastAPI runtime startup is a read-only compatibility boundary. It checks required tables, columns, named constraints,
indices, GRAC immutability triggers, PostgreSQL RLS/grant posture, and the API credential schema. It fails closed when
the configured databases are absent or incompatible and never attempts repair.

The operator workflow is the only supported mutating setup path for this tranche. The superuser-owned bootstrap
creates the cluster-level capability roles; the normal command wraps the existing custom migration mechanics and owns:

- SQLAlchemy ORM table creation;
- SQLite compatibility migrations;
- PostgreSQL rebuild-job columns, widths, and status constraint;
- GRAC projection metadata/backfill, checks, immutable-write triggers, exact named RLS policies, and grant hardening;
- `user_credentials` table creation and optional initial credential provisioning;
- exact grants and policies for the pre-provisioned PostgreSQL `NOLOGIN` capability roles:
  `fardb_runtime_graph`, `fardb_runtime_coordination`, and `fardb_runtime_auth`.

The normal command does not create a missing capability role when run by a non-superuser migration owner. It fails
closed and directs the operator to `scripts/bootstrap_database_capability_roles.sql`. A superuser connection retains
fallback role creation for isolated development and disposable tests. Neither path creates login roles, passwords,
connection strings, or provider configuration. Runtime login creation, credential custody, role membership, and URL
replacement remain a separate human-controlled provider operation.

## Superuser capability-role bootstrap

Run the static bootstrap once on every distinct PostgreSQL cluster that hosts a FarDB auth, graph, or coordination
database, before using the normal migration owner:

```bash
psql --set=ON_ERROR_STOP=1 "$MIGRATION_DATABASE_URL" \
  --file scripts/bootstrap_database_capability_roles.sql
```

`MIGRATION_DATABASE_URL` in this example must identify the reviewed superuser-owned bootstrap connection. Do not save
or publish its value. The artifact creates only the three fixed `NOLOGIN` roles with restricted attributes. It removes
incoming memberships carrying `ADMIN OPTION`, including PostgreSQL 16's bootstrap-superuser grant to a non-superuser
`CREATEROLE` creator, and then fails closed if any restricted role invariant remains unsafe. It does not grant a
runtime login membership or configure schema objects.

Do not replace this step with a `SECURITY DEFINER` function, a privileged application endpoint, or superuser
credentials in the application environment. Keep bootstrap credentials in the approved operator surface and remove
them before running the normal migration.

## PostgreSQL runtime capability contract

| Capability role              | Intended login boundary     | Effective data authority                                                                                  |
| ---------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------- |
| `fardb_runtime_auth`         | `DATABASE_URL` / auth       | `SELECT` on `user_credentials`; no credential writes                                                      |
| `fardb_runtime_graph`        | `ASSET_GRAPH_DATABASE_URL`  | graph-domain DML required by repositories; rebuild-job `SELECT`/`INSERT`/`UPDATE`; GRAC `SELECT`/`INSERT` |
| `fardb_runtime_coordination` | `COORDINATION_DATABASE_URL` | `SELECT`/`INSERT`/`UPDATE`/`DELETE` on `distributed_locks`                                                |

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
2. Run the superuser capability-role bootstrap above once for each distinct PostgreSQL cluster. Record only bounded
   pass/fail evidence; never record the bootstrap URL.
3. Configure the existing database URL variables with migration-owner credentials for the intended graph,
   coordination, and auth boundaries. Existing URL precedence is unchanged.
4. Configure `SECRET_KEY`. For initial credential provisioning, also configure `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and
   optional `ADMIN_EMAIL`, `ADMIN_FULL_NAME`, or `ADMIN_DISABLED`.
5. Run:

   ```bash
   python -m scripts.migrate_database
   ```

6. Require exit status 0 and record only the emitted component names (`graph`, `coordination`, `auth`). Never record
   raw database URLs or secrets.
7. In the provider's protected operator surface, create or select the three restricted login identities and grant
   only the applicable capability membership. For example, the reviewed equivalent of
   `GRANT fardb_runtime_graph TO <graph_login>` belongs on the graph boundary; use both graph and coordination
   memberships only when those boundaries deliberately share one URL. Do not paste login names or commands with
   credentials into public evidence.
8. Replace migration-owner URLs with the corresponding restricted-login URLs. Remove `ADMIN_PASSWORD` from the
   runtime environment, but keep `ADMIN_USERNAME` in production runtime configuration.
9. Start FastAPI. A compatibility failure is a deployment blocker: return to this procedure rather than broadening
   the app role.
10. Prove cold start and restart, exercise graph/coordination/auth runtime operations, and run the hosted readiness and
    database-authorization evidence required by the target environment.

### Production Compose operator path

The production Compose runtime never runs migrations during API startup. For routine schema migrations after an
enabled administrator credential has been provisioned, leave `ADMIN_PASSWORD` unset so the migration verifies the
existing credential without replacing it:

```bash
# Obtain SECRET_KEY from the approved operator secret surface.
: "${SECRET_KEY:?SECRET_KEY must be set}"
unset ADMIN_PASSWORD
docker compose -f docker-compose.production.yml --profile operator run --rm --build migrate
docker compose -f docker-compose.production.yml up -d api frontend
```

Use the password-bearing path only for initial credential provisioning:

```bash
# Obtain SECRET_KEY from the approved operator secret surface.
: "${SECRET_KEY:?SECRET_KEY must be set}"
export ADMIN_USERNAME=replace-with-the-initial-admin
read -r -s -p "Initial admin password: " ADMIN_PASSWORD
printf '\n'
export ADMIN_PASSWORD
docker compose -f docker-compose.production.yml --profile operator run --rm --build migrate
unset ADMIN_PASSWORD
docker compose -f docker-compose.production.yml up -d api frontend
```

The `migrate` service has no ports and does not remain running. It receives `ADMIN_PASSWORD` only for the initial
credential-provisioning invocation; routine migrations must leave that variable unset, and the `api` service never
receives it. For PostgreSQL, complete the superuser capability-role bootstrap first, then supply migration-owner URLs
to this command as described above.

For an isolated PostgreSQL rehearsal, the opt-in integration contract accepts restricted DSNs only through
`FARDB_GRAPH_RUNTIME_DATABASE_URL`, `FARDB_COORDINATION_RUNTIME_DATABASE_URL`, and
`FARDB_AUTH_RUNTIME_DATABASE_URL`, with `RUN_POSTGRES_TESTS=1`. These values are secrets: run the test from an
approved operator environment and retain only bounded pass/fail evidence. The test does not create logins, grant
memberships, or change provider configuration.

When graph and coordination share one URL, the command initializes that engine once. A coordination-only target still
receives the shared FarDB structural schema; its requested capability set controls the runtime grants and RLS policies,
not which ORM tables the operator creates. When no durable graph or coordination URL is configured for a local demo,
the command initializes only the auth database.

## Local SQLite initial-provisioning example

Store the local signing key once in the gitignored `.env.local` secret surface and reuse it unchanged for every later
run. If `.env.local` already exists, add a persistent `SECRET_KEY` entry through the approved local secret workflow;
do not regenerate the key.

```bash
umask 077
test -e .env.local || python -c 'import secrets; print("SECRET_KEY=" + secrets.token_urlsafe(32))' > .env.local
set -a
. ./.env.local
set +a
: "${SECRET_KEY:?SECRET_KEY must be set}"
export DATABASE_URL=sqlite:dev.db
export ADMIN_USERNAME=admin
read -r -s -p "Initial admin password: " ADMIN_PASSWORD
printf '\n'
export ADMIN_PASSWORD
python -m scripts.migrate_database
unset ADMIN_PASSWORD
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

For later routine local migrations, preserve the existing administrator credential by leaving the bootstrap password
unset:

```bash
set -a
. ./.env.local
set +a
: "${SECRET_KEY:?SECRET_KEY must be set}"
export DATABASE_URL=sqlite:dev.db
unset ADMIN_PASSWORD
python -m scripts.migrate_database
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Set `ASSET_GRAPH_DATABASE_URL` and, when separated, `COORDINATION_DATABASE_URL` before the command when local work
requires durable graph/reconciliation persistence.

## Failure and rollback

- A missing-schema or incompatible-schema startup error is evidence that the operator step did not complete against
  the runtime target. Do not retry by granting CREATE, ALTER, TRIGGER, ownership, or grant-management authority to the
  application role.
- A `required PostgreSQL capability role ... is missing` migration error means the normal migration owner is correctly
  refusing to create a cluster role. Run the static superuser bootstrap against that cluster, remove the superuser
  connection from the environment, and rerun the normal migration.
- If the command fails, retain the target for diagnosis when safe, use the backup/restore procedure for destructive or
  partial migration concerns, and rerun only after the cause is understood.
- Code rollback may restore the prior application version, but database rollback follows the schema change's reviewed
  rollback/restore plan. Restoring the old startup mutation path is not an operational recovery procedure.
- Stop for human review when a new migration tool, dependency, credential channel, destructive provider action, or
  schema-history decision is required.

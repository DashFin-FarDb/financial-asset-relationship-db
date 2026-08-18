# Database migration authority

**Applies to:** current FarDB graph, coordination, GRAC, and API credential schemas.
**Commands:** superuser role bootstrap, ledger validation, then `python -m scripts.migrate_database`
**Authority:** static cluster-role bootstrap plus one profile-scoped repository SQL ledger.

## Contract

FastAPI runtime startup is a read-only compatibility boundary. It checks required tables, columns, named constraints,
indices, GRAC immutability triggers, PostgreSQL RLS/grant posture, and the API credential schema. It fails closed when
the configured databases are absent or incompatible and never attempts repair.

For PostgreSQL, the only schema authority is the exact SQL under
`supabase/ledgers/<component>/migrations/`, composed by `supabase/ledger-profiles.json`. The operator validates those
bytes, validates a protected target-binding document, builds a disposable Supabase CLI projection, and applies one of
four explicit profiles: `auth`, `graph`, `coordination`, or `combined`. The committed repository never contains a flat
`supabase/migrations/` directory, provider link state, or generated projection.

Each disposable projection contains only the selected, digest-rechecked migration bytes plus a fixed mode-`0600`
`supabase/config.toml` with the non-secret local project ID required by the pinned CLI. That generated config carries
no provider reference, target selection, schema definition, seed setting, or executable authority and is deleted with
the projection.

The custom imperative path remains only for SQLite compatibility. PostgreSQL calls to `init_db`, auth schema setup,
GRAC repair, rebuild compatibility repair, or runtime grant provisioning fail closed. PostgreSQL credential seeding is
the sole post-ledger DML performed by the operator command; it runs only after read-only schema and capability-catalog
verification succeeds.

The static superuser bootstrap creates the three cluster-level capability roles before profile execution. Neither the
ledger runner nor any runtime process creates roles, login identities, passwords, connection strings, memberships, or
provider configuration. Runtime login creation, credential custody, role membership, and URL replacement remain a
separate human-controlled provider operation.

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
direct table privileges. An explicitly combined physical target still uses scoped logins: the graph/reconciliation
runtime URL needs graph and coordination memberships, while the auth login needs only auth membership. Separated
graph and coordination URLs need one membership each. Startup rejects missing, extra, elevated, or drifted authority,
including direct or inherited access to another component's tables, columns, sequences, or ledger-owned routines on
a `combined` target.

CQ-03C evaluates `fresh-v1` targets through the read-only
`fardb-pg-catalog-v1+fardb-pg-scope-v1` gate. It compares exact ordered migration identities, the selected profile's
normalized catalog digest, and an explicit runtime-compatibility callback. The evaluator forces a read-only database
transaction, rolls it back after catalog access, and exposes only bounded counts, digests, status, category, and
reason codes. It never repairs schema or migration history.

The public result is `PASS`, `DRIFT_DETECTED`, or `EVALUATION_INCOMPLETE`. A detected primary category follows this
fixed precedence: `LEDGER_HISTORY_MISMATCH`, `PROVIDER_SCHEMA_DRIFT`, then `RUNTIME_COMPATIBILITY_MISMATCH`. An
unavailable check at the same or higher precedence, an unknown `public` object, an unknown profile, or an unadopted
lineage produces `EVALUATION_INCOMPLETE` with a null primary category. Treat either non-pass result as a deployment
blocker; do not broaden scope, infer ownership, or mutate the target to make the gate pass.

The profile digests in `supabase/ledger-profiles.json` are calibrated from identical clean results on disposable
PostgreSQL 15 and 16 builds. Changing a managed migration, catalog normalization, scope classifier, or profile
composition requires a reviewed manifest and digest update. CQ-03D remains a separately approved, permit-bound
hosted-history adoption workflow and never applies DDL.

## Profile manifest and protected target binding

Validate the immutable repository inputs before any execution:

```bash
python -m scripts.postgresql_ledger validate
```

Every configured PostgreSQL logical target must have one entry in a mode-`0600` JSON document named by
`FARDB_POSTGRES_TARGET_BINDINGS_FILE`. The document binds the exact manifest digest, algorithm
`fardb-target-fingerprint-v1`, logical target, profile, lineage, execution class, and three operator-attested immutable
identity inputs. Raw identity inputs are protected evidence: they are not a DSN, hostname, port, mutable project name,
or database name and must never be committed or printed.

Distinct physical targets use their matching single-component profile. Three aliases to one approved shared physical
target must all select `combined` and carry identical immutable identity inputs. Partial sharing, conflicting profiles,
different fingerprints for the same URL, one fingerprint for distinct protected inputs, missing values, control
characters, and a manifest-digest mismatch all stop with `TARGET_IDENTITY_INDETERMINATE` or a bounded profile-conflict
error before an engine, connection, or subprocess starts.

CQ-03B-R2 executes only `fresh-v1` targets classified `disposable` or `loopback`. It rejects `hosted-legacy-v1`, a
hosted execution class, known hosted Supabase endpoints, and a non-loopback hostname labelled as loopback. Every DSN
alias retained for a `combined` target passes that barrier independently before the first execution. Before CQ-03D it
also forbids `supabase link`, `db pull`, `migration repair`, either linked/URL reset variant, linked/project selection,
password flags, dry-run substitution, and any command other than the fixed projected `db push` with an explicit
operator URL. This means the R2 command is not authority to apply or adopt a hosted target.

## First setup or schema-relevant deployment

1. Stop traffic to an unprepared target, or run before deploying application instances that require the new schema.
2. Run the superuser capability-role bootstrap above once for each distinct PostgreSQL cluster. Record only bounded
   pass/fail evidence; never record the bootstrap URL.
3. Configure the existing database URL variables with migration-owner credentials for the intended graph,
   coordination, and auth boundaries. Existing URL precedence is unchanged.
4. For every PostgreSQL URL, prepare the protected target-binding document described above, set mode `0600`, and set
   `FARDB_POSTGRES_TARGET_BINDINGS_FILE` to its absolute path. Complete this only for an approved `fresh-v1`
   disposable or loopback target in R2.
5. Require the reviewed Supabase CLI version `2.114.0`. The migration container installs an exact checksum-pinned
   Linux AMD64 binary; a direct operator environment must provide the same version.
6. Configure `SECRET_KEY`. For initial credential provisioning, also configure `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and
   optional `ADMIN_EMAIL`, `ADMIN_FULL_NAME`, or `ADMIN_DISABLED`.
7. Run:

   ```bash
   python -m scripts.migrate_database
   ```

8. Require exit status 0 and record only the emitted component names (`graph`, `coordination`, `auth`). Never record
   raw database URLs or secrets.
9. In the protected operator surface, create or select the three restricted login identities and grant
   only the applicable capability membership. For example, the reviewed equivalent of
   `GRANT fardb_runtime_graph TO <graph_login>` belongs on the graph boundary; use both graph and coordination
   memberships only when those boundaries deliberately share one URL. Do not paste login names or commands with
   credentials into public evidence.
10. Replace migration-owner URLs with the corresponding restricted-login URLs. Remove `ADMIN_PASSWORD` from the
    runtime environment, but keep `ADMIN_USERNAME` in production runtime configuration.
11. Start FastAPI. A compatibility failure is a deployment blocker: return to this procedure rather than broadening
    the app role.
12. Prove cold start and restart, exercise graph/coordination/auth runtime operations, and run the hosted readiness and
    database-authorization evidence required by the target environment.

### Production Compose operator path

The production Compose runtime never runs migrations during API startup and its `runtime` image contains neither the
Supabase CLI nor ledger sources. The separate `migration` image contains the checksum-pinned CLI and exact ledger. For
SQLite, routine schema migrations after an enabled administrator credential has been provisioned leave
`ADMIN_PASSWORD` unset, so the migration verifies the existing credential without replacing it:

```bash
# Obtain SECRET_KEY from the approved operator secret surface.
: "${SECRET_KEY:?SECRET_KEY must be set}"
: "${ADMIN_USERNAME:?ADMIN_USERNAME must remain set for migration}"
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

The `migrate` service has no ports, is read-only apart from `/data` and `/tmp`, and does not remain running. It receives
`ADMIN_PASSWORD` only for the initial credential-provisioning invocation; routine migrations must leave that variable
unset, and the `api` service never receives it. For a permitted disposable/loopback PostgreSQL rehearsal, complete the
capability-role bootstrap, mount the mode-`0600` binding document without baking it into the image, set
`FARDB_POSTGRES_TARGET_BINDINGS_FILE` to the in-container path, and supply migration-owner URLs. Hosted execution and
history adoption remain blocked until CQ-03D.

The PostgreSQL rehearsal mount is intentionally supplied at invocation time so the protected document is never a
default Compose volume. Use an absolute host path outside the repository:

```bash
: "${FARDB_POSTGRES_TARGET_BINDINGS_HOST_FILE:?set an absolute path to the protected binding document}"
case "$FARDB_POSTGRES_TARGET_BINDINGS_HOST_FILE" in
  /*) ;;
  *) echo "binding document path must be absolute" >&2; exit 1 ;;
esac
chmod 0600 "$FARDB_POSTGRES_TARGET_BINDINGS_HOST_FILE"
docker compose -f docker-compose.production.yml --profile operator run --rm --build \
  --volume "$FARDB_POSTGRES_TARGET_BINDINGS_HOST_FILE:/run/secrets/fardb-postgres-target-bindings.json:ro" \
  --env FARDB_POSTGRES_TARGET_BINDINGS_FILE=/run/secrets/fardb-postgres-target-bindings.json \
  migrate
```

For an isolated PostgreSQL rehearsal, the opt-in integration contract accepts restricted DSNs only through
`FARDB_GRAPH_RUNTIME_DATABASE_URL`, `FARDB_COORDINATION_RUNTIME_DATABASE_URL`, and
`FARDB_AUTH_RUNTIME_DATABASE_URL`, with `RUN_POSTGRES_TESTS=1`. These values are secrets: run the test from an
approved operator environment and retain only bounded pass/fail evidence. The test does not create logins, grant
memberships, or change provider configuration.

When PostgreSQL graph and coordination are distinct, each receives only its component profile. Sharing is permitted
only when auth, graph, and coordination are all explicitly bound to one physical target with `combined`; the runner
never infers that choice. SQLite retains its historical shared local schema behavior. When no durable graph or
coordination URL is configured for a local demo, the command initializes only the auth database.

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

## CQ-03D approval pack and read-only preflight

CQ-03D is not an extension of the normal PostgreSQL migration command. It is a separate, manual, history-only
workflow for one selected hosted target after read-only evidence proves that its schema already equals the reviewed
repository ledger. This section prepares that decision; it does not authorize a connected target operation.

### Approval pack

The ratifier must receive a protected, single-use permit that binds exactly one proposed history marker. Keep the
permit and its raw target evidence outside the repository and do not place its values in a pull request, issue,
workflow log, or this runbook.

The permit must contain all of the following:

- exact reviewed repository SHA;
- `fardb-pg-ledger-v1` manifest SHA-256 and selected build-profile ID;
- selected lineage-profile ID and opaque `fardb-target-fingerprint-v1` target fingerprint;
- exactly one allowlisted canonical migration timestamp;
- the passing CQ-03B/C exact-head evidence references and expected/actual normalized catalog digest;
- passing history, runtime-compatibility, and runtime-authority evidence references;
- named ratifier, approval time, expiry, and an unambiguous consumed/revoked state; and
- an explicit declaration that the proposed action is history-only and must not apply DDL.

Do not issue a permit from an incomplete, stale, or substituted artifact. A changed SHA, manifest, profile, lineage,
target fingerprint, timestamp, expected or actual catalog digest, runtime authority, approval expiry, or evidence
status invalidates it before any command is considered.

### Read-only preflight sequence

1. Confirm the checked-out SHA equals the permit SHA and the worktree contains no unreviewed migration, manifest, or
   normalizer change. Run the repository-only integrity check:

   ```bash
   python -m scripts.postgresql_ledger validate
   ```

   The emitted manifest SHA-256 must exactly equal the permit. Any other result stops the workflow.

2. In the protected operator surface, load the mode-`0600` target-binding document and prove the selected DSN's
   immutable identity equals the permit's opaque fingerprint. Do not print the DSN or raw immutable identity inputs.
   Missing, unavailable, or mismatched proof is `TARGET_IDENTITY_INDETERMINATE` and stops the workflow.
3. Run the reviewed CQ-03D read-only evaluator against that one protected target. It must use a read-only transaction,
   roll it back, select the permit's profile and lineage, and execute the existing history, normalized-catalog,
   runtime-compatibility, and ADR 0007 runtime-authority checks. The public record must report `PASS`, zero
   `not_evaluated_count`, no primary category, and the permit's expected and actual catalog digest. Any
   `DRIFT_DETECTED`, `EVALUATION_INCOMPLETE`, unavailable check, unknown public object, or mismatched digest stops the
   workflow.
4. Run the reviewed read-only migration-list parity check for the same target, profile, lineage, and one timestamp.
   The future operator interface must select the identity-verified target through an explicit
   `--db-url <permit-bound-dsn>` argument and reject `--linked`, `--project-ref`, and retained CLI link or branch state
   before the subprocess starts. It must establish that the permit's marker is the only intended history difference.
   Record only the bounded parity result and timestamp count; do not retain raw provider output.
5. Recheck the permit bindings immediately before any later history action. A target or evidence change after the
   earlier read-only checks is not a warning: revoke the permit and begin again with fresh evidence.

The repository currently exposes the tested `evaluate_profile_drift()` API but has no CQ-03D target-bound operator
command that can perform steps 2–4. No database-connected command is approved by this preparation package. A separate
implementation decision must add and test that narrow operator interface before preflight execution; it must preserve
the protected-binding identity proof, read-only transaction, rollback, and sanitized-output contracts above.

### Prohibited actions and future execution boundary

Until a separate permit is ratified and every read-only preflight result is `PASS`, do not run `supabase db pull`,
`supabase db push`, `supabase db push --dry-run`, `supabase migration repair`, `supabase db reset`, provider SQL,
dashboard SQL, direct DDL/DML, grants, role changes, credential changes, provider-link operations, or deployment
actions against the hosted target.

The later CQ-03D execution workspace may perform only a fixed argument-array equivalent of
`supabase migration repair <timestamp> --status applied --db-url <permit-bound-dsn>` after it rechecks every binding.
The operator interface must obtain that DSN from the protected binding whose immutable identity matches the permit;
it must reject an operator-supplied target override, `--linked`, `--project-ref`, `--local`, and retained CLI link or
branch state before the subprocess starts. It must immediately repeat migration-list parity, normalized drift, runtime
compatibility, runtime authority, and the no-unexpected-pending
`supabase db push --dry-run --db-url <permit-bound-dsn>` verification against that same enforced target. It stops on
any non-`PASS` result and never applies DDL. The permit is then marked consumed outside the repository; it cannot
authorize another timestamp or retry.

### Bounded evidence record

Record the exact SHA, manifest SHA-256, profile ID, lineage ID, opaque target fingerprint, one timestamp, ratifier and
permit lifecycle, public drift status/category/reason codes/counts/digests, bounded parity result, and pass/fail
outcomes. Exclude raw database URLs, hostnames, project references, credentials, role identities, live object names,
raw SQL, provider output, and restricted diagnostics.

## Failure and rollback

- A missing-schema or incompatible-schema startup error is evidence that the operator step did not complete against
  the runtime target. Do not retry by granting CREATE, ALTER, TRIGGER, ownership, or grant-management authority to the
  application role.
- A missing PostgreSQL capability role causes the forward migration to fail without creating it. Run the static
  superuser bootstrap against the disposable/loopback cluster, remove the superuser connection from the environment,
  and rerun only after all target bindings are revalidated.
- `TARGET_IDENTITY_INDETERMINATE` means identity evidence, file protection, manifest binding, or alias resolution is
  incomplete. Do not infer an identity or broaden a profile.
- A hosted-write-barrier failure is expected for hosted or legacy targets in CQ-03B-R2. Do not bypass it with direct
  CLI, provider SQL, link state, another credential, or migration-history repair; CQ-03D requires separate approval.
- If the command fails, retain the target for diagnosis when safe, use the backup/restore procedure for destructive or
  partial migration concerns, and rerun only after the cause is understood.
- Code rollback may restore the prior application version, but database rollback follows the schema change's reviewed
  rollback/restore plan. Restoring the old startup mutation path is not an operational recovery procedure.
- Stop for human review when a new migration tool, dependency, credential channel, destructive provider action, or
  schema-history decision is required.

# Restricted Database Authorization Closure Worksheet

**Classification:** Restricted remediation evidence — **do not commit filled copies** with live topology, object
names, grants, policy text, adviser dumps, connection strings, or credentials.

Copy this file to an approved private store for the target environment. Public evidence uses
[db-authz-public-redacted-pass.md](./db-authz-public-redacted-pass.md) only.

## Header

| Field                             | Value                                          |
| --------------------------------- | ---------------------------------------------- |
| Target environment                | staging / production                           |
| Release commit SHA                |                                                |
| Closure owner                     |                                                |
| Capture window (UTC)              |                                                |
| Provider                          |                                                |
| Shared-boundary decision (if any) | approved / not applicable — document rationale |

## Step 1 — Inventory

- [ ] Exposed schemas listed
- [ ] Tables / views / sequences / functions inventoried
- [ ] Provider Data API routes and roles noted
- [ ] Application / migration / recovery / admin role identities recorded
- [ ] Privileged and security-definer functions inventoried

## Step 2 — Least-privilege design

- [ ] Application role privileges mapped to FastAPI needs only
- [ ] Migration authority separated from request handling
- [ ] Recovery authority limited to state-machine operations
- [ ] Untrusted roles (`FARDB_UNTRUSTED_DATABASE_ROLES` or defaults) have no unintended grants
- [ ] RLS enablement plan for every exposed-schema table

## Step 3 — Negative access tests

| Test case                                    | Expected deny | Result | Notes |
| -------------------------------------------- | ------------- | ------ | ----- |
| Untrusted role relation access               | Deny          |        |       |
| Untrusted role sequence access               | Deny          |        |       |
| Untrusted role function execute              | Deny          |        |       |
| Direct Data API table access (if applicable) | Deny          |        |       |

## Step 4 — Rollback and regression

- [ ] Rollback rehearsal completed
- [ ] Application path verified after enforcement
- [ ] Persisted startup / hosted readiness verified
- [ ] Recovery path verified
- [ ] Restore path verified (or linked restore evidence)

## Step 5 — Credential and log review

- [ ] Access logs reviewed for unexpected role use
- [ ] Credentials rotated where exposure cannot be bounded
- [ ] Steady-state app credentials are not general admin roles

## Step 6 — Apply via governed migration authority

- [ ] Change set identified
- [ ] Applied through approved migration / provider process
- [ ] Change window and operator recorded

## Step 7 — Advisers and bounded checker

Set GitHub Environment **secrets** (not Environment variables—workflows read `secrets.*` only) for exposed schemas so
staging/production/release-evidence authz gates check every inventoried schema before emitting `db_authz: PASS|…`.
Each per-boundary override replaces the global/default inventory for its URL. The global secret
`FARDB_EXPOSED_DATABASE_SCHEMAS` is required only when at least one boundary relies on that default and needs a
non-`public` inventory (include `public` when exposed). When every configured URL has its own override, leave the
global secret unset. When no schema secret is set for a boundary, the gate checks `public` only. Place applicable
secrets on **every** Environment the selected workflow can enter (`staging`, `staging-manual-gate`, `production`,
`production-manual-gate`, `release-evidence` as applicable). Fixed override names:

- `FARDB_EXPOSED_DATABASE_SCHEMAS_DATABASE` → `DATABASE_URL`
- `FARDB_EXPOSED_DATABASE_SCHEMAS_ASSET_GRAPH` → `ASSET_GRAPH_DATABASE_URL`
- `FARDB_EXPOSED_DATABASE_SCHEMAS_COORDINATION` → `COORDINATION_DATABASE_URL`
- `FARDB_EXPOSED_DATABASE_SCHEMAS_POSTGRES` → `POSTGRES_URL`

- [ ] Provider advisers re-run; high-severity findings resolved or excepted
- [ ] If any boundary uses the global/default inventory: Environment **secret** `FARDB_EXPOSED_DATABASE_SCHEMAS` set
      to the full inventoried list for that default (or confirmed `public`-only). Skip when every boundary uses an
      override below
- [ ] Per-boundary overrides set where needed (`FARDB_EXPOSED_DATABASE_SCHEMAS_DATABASE` /
      `_ASSET_GRAPH` / `_COORDINATION` / `_POSTGRES`)
- [ ] Schema secrets present on every Environment that workflow may select (including `*-manual-gate`)
- [ ] Automated gate passed with that schema inventory (`python scripts/check_database_authorization.py`)
- [ ] Schema list (names only) recorded here; do not paste grants or adviser dumps
- [ ] Manual privileged-function review complete: schema, owner, fixed safe search path, and execution grants verified

## Exceptions

High-severity access-control findings close the gate only with a named, time-bounded exception **approved by the
release authority** (ADR 0007). Record that approval in the Approval column.

| Finding | Severity | Named exception owner | Expiry | Approval (release authority) |
| ------- | -------- | --------------------- | ------ | ---------------------------- |
|         |          |                       |        |                              |

## Sign-off (restricted)

| Role                              | Name | Date (UTC) |
| --------------------------------- | ---- | ---------- |
| Closure owner                     |      |            |
| Security reviewer                 |      |            |
| Release authority (if exceptions) |      |            |

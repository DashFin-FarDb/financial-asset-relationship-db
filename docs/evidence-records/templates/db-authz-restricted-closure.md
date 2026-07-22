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

- [ ] Provider advisers re-run; high-severity findings resolved or excepted
- [ ] `python scripts/check_database_authorization.py` passed on every required boundary
- [ ] Manual privileged-function fixed-search-path review complete

## Exceptions

| Finding | Severity | Named exception owner | Expiry | Approval |
| ------- | -------- | --------------------- | ------ | -------- |
|         |          |                       |        |          |

## Sign-off (restricted)

| Role                              | Name | Date (UTC) |
| --------------------------------- | ---- | ---------- |
| Closure owner                     |      |            |
| Security reviewer                 |      |            |
| Release authority (if exceptions) |      |            |

# ADR 0007: Database authorization boundary

## Status

Accepted

## Date

2026-07-15

## Context

FarDB's production path is Next.js and FastAPI. The browser calls the FastAPI product boundary; repository
inspection found no production Supabase client that requires direct browser-to-database access. Hosted
application, graph and recovery processes instead use server-side PostgreSQL connection boundaries.

A read-only provider review on 15 July 2026 confirmed that database access hardening remains a release-blocking
item. Exact live schema, role, policy and adviser details are restricted remediation evidence and must not be
copied into this public ADR, pull-request discussion or CI output.

Database reachability, PostgreSQL durability and application authentication do not by themselves establish a
least-privilege database boundary. Provider Data API grants, row-level security, direct PostgreSQL roles, views
and privileged functions are separate controls and must be verified separately.

## Decision

FarDB adopts the following authorization boundary for hosted PostgreSQL.

### Product ingress

1. FastAPI remains the only production application ingress to canonical database state.
2. Next.js clients do not receive database credentials or bypass FastAPI through a provider Data API.
3. Gradio remains non-production and receives no independent production database authority.

### Provider Data API

1. Provider-managed unauthenticated and authenticated API roles receive no table, view, sequence or function
   authority unless a later ADR approves a bounded product requirement.
   Their database role identities are explicit verification inputs rather than assumed provider-neutral names.
2. Every table in an exposed schema has row-level security enabled even when direct Data API access is revoked.
3. A future direct-client workflow requires explicit ownership predicates, negative tests and a separately
   reviewed policy contract. Authentication alone is not authorization.

### Server-side roles

1. Application, migration, recovery and administrative authority are logically distinct.
2. The application role receives only the data operations required by FastAPI.
3. Migration authority is not used by normal request handling.
4. Recovery authority is limited to the operations defined by the canonical state-machine and operating
   authority.
5. Hosted application credentials must not use a general administrative role as the steady-state identity.

### Policies, views and functions

1. Authorization policy must not rely on user-editable metadata or deprecated role helpers.
2. Update policies require both visibility and post-update validation where row-level policies are used.
3. API-accessible views use invoker security or have untrusted-role access revoked.
4. Privileged functions are kept outside exposed schemas where practical, use a fixed safe search path and have
   execution revoked from untrusted roles.
5. New hosted tables cannot pass the authorization gate while row-level security is disabled in an exposed
   schema.

### Evidence handling

1. Live topology, object names, grants, policy definitions, adviser output and credential decisions remain in a
   restricted remediation record until closure is verified.
2. Public evidence reports only whether each control class passed or failed.
3. CI and operator tooling must not print connection strings, object names, row counts or raw database errors.

## Verification contract

`scripts/check_database_authorization.py` performs a read-only aggregate check for:

- row-level security on exposed-schema tables;
- absence of configured untrusted-role relation-level and column-level table/view access, sequence access and
  function execution;
- absence of unsafe authorization-claim patterns.

One invocation validates and checks every distinct PostgreSQL URL present in the fixed configuration allowlist:

```bash
python scripts/check_database_authorization.py
```

The allowlist comprises `DATABASE_URL`, `ASSET_GRAPH_DATABASE_URL`, `COORDINATION_DATABASE_URL` and
`POSTGRES_URL`. Duplicate URLs are checked once. When environment variables intentionally resolve to one database
boundary, the restricted evidence record may document the approved shared-boundary decision. The checker
defaults the current provider-role identities to `anon` and `authenticated`; another provider must set
`FARDB_UNTRUSTED_DATABASE_ROLES` to its comma-separated untrusted database role identities and retain that choice
in restricted evidence. Missing default provider roles are treated as having no authority. When the role
environment variable is explicitly set, every configured identity must resolve on every checked boundary or the
gate fails closed. Exposed schemas default to `public`; set the Environment secret
`FARDB_EXPOSED_DATABASE_SCHEMAS` to the **full** comma-separated inventoried list (include `public` when exposed).
When inventories differ by database boundary, set `FARDB_EXPOSED_DATABASE_SCHEMAS_*` per URL so the automated gate
checks every exposed schema on the correct boundary before a promotion PASS.
Connection establishment, statement execution and catalog lock waits are time-bounded. The checker produces
bounded pass/fail output and does not replace provider advisers, application integration tests or recovery
exercises.

The checker cannot infer which business functions are privileged solely from catalog shape. The restricted
closure record must therefore inventory privileged and security-definer functions and verify their schema,
owner, fixed safe search path and execution grants as a manual control.

## Remediation sequence

1. Capture the live object, route, role, policy, view and function inventory in a restricted record.
2. Design least-privilege roles and policies against a non-production branch or staging database.
3. Run negative access tests before enabling enforcement.
4. Rehearse rollback and confirm that application, persisted startup, recovery and restore paths still work.
5. Review access logs and rotate any credential whose exposure cannot be bounded.
6. Apply the reviewed change through the governed migration authority.
7. Re-run provider advisers and the bounded checker, then attach redacted closure evidence to the release record.

## Exit criteria

The release-blocking authorization gate closes only when:

- every exposed-schema table passes the row-level-security control;
- untrusted provider roles have no unintended database authority;
- views pass their automated access check, and privileged functions pass both the automated execution check and
  the manual fixed-search-path review;
- application, recovery and restore integration tests pass after enforcement;
- no unresolved high-severity access-control finding remains, except a named, time-bounded exception approved by
  the release authority;
- credential review, rollback evidence and redacted operator sign-off are complete.

## Consequences

### Positive

- The database boundary matches the declared FastAPI production architecture.
- Provider API exposure and direct PostgreSQL access are no longer treated as one control.
- Authorization evidence can be automated without publishing exploitable topology.
- Future medical or other sensitive-domain work inherits a deny-by-default foundation.

### Negative

- Existing connection roles and migrations may require staged changes.
- Enabling enforcement without complete policies can interrupt legitimate application and recovery paths.
- Separate application, migration and recovery roles increase operational setup work.

### Neutral

- PostgreSQL remains the hosted durability baseline.
- This decision does not require Supabase Auth or direct browser database access.
- The rebuild/recovery state machine and operator authority are unchanged.

## Non-goals

- This ADR does not mutate the live database.
- This ADR does not publish the restricted live authorization inventory.
- This ADR does not introduce a browser Supabase client.
- This ADR does not implement domain-level multi-tenancy or end user row ownership.
- This ADR does not close the gate without target-environment evidence.

## References

- [ADR 0001: Production architecture](./0001-production-architecture.md)
- [ADR 0002: Hosted deployment and persistence](./0002-hosted-deployment-and-persistence.md)
- [State machine and operating authority](../governance/state-machine-and-operating-authority.md)
- [Database authorization closure runbook](../runbooks/database-authorization-closure.md)
- [Public redacted pass template](../evidence-records/templates/db-authz-public-redacted-pass.md)
- [Restricted closure worksheet](../evidence-records/templates/db-authz-restricted-closure.md)
- [Supabase: Securing the Data API](https://supabase.com/docs/guides/api/securing-your-api)
- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [PostgreSQL: Row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

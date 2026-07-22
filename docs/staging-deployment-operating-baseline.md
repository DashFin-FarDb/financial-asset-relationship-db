# Staging Deployment Operating Baseline

**Status:** Active
**Issue:** #1306
**Scope:** Staging operating baseline for the FastAPI + Next.js production architecture.

## Purpose

This baseline makes staging deployment operations auditable without introducing new hosting architecture. It records the
required provider boundaries, Vercel environment mapping, environment-variable expectations, preview durability labels,
and staging promotion evidence path.

This document does not contain secret values, raw connection strings, access tokens, provider credentials, or full
deployment logs.

## Baseline Decision

Staging uses the existing hosted topology:

- Vercel-hosted Next.js frontend.
- Vercel serverless FastAPI backend using `api.main:app`.
- Supabase PostgreSQL app/auth database exposed through `DATABASE_URL`.
- Supabase PostgreSQL durable graph database exposed through `ASSET_GRAPH_DATABASE_URL`.
- Optional Supabase PostgreSQL coordination database exposed through `COORDINATION_DATABASE_URL` when separated.
- Vercel environment variables for secret and configuration injection.

No new hosting architecture, queue, scheduler, database abstraction, or persistence rewrite is introduced by this
baseline.

## Current Provider Record

The staging database provider is **Supabase**. The repository does not commit concrete Supabase project IDs, database
instance names, Vercel project IDs, or environment-variable values. Those values are operator-controlled and must be
captured as redacted release evidence.

Before staging promotion, the release-candidate evidence issue must record:

- staging database provider name: Supabase;
- app/auth database boundary label;
- asset graph database boundary label;
- coordination database boundary label, or explicit statement that coordination shares the app/auth boundary;
- confirmation that `ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL`, unless an approved exception is
  recorded;
- Vercel project name or deployment URL used for staging frontend traffic;
- Vercel project name or deployment URL used for staging backend/API traffic.

If any of these records are missing, staging promotion is blocked.

## Vercel Environment Mapping

The selected deployment platform is Vercel. The repository is configured for a monorepo deployment in
[`vercel.json`](../vercel.json):

- requests under `/api/*` route to `api/main.py`;
- all other requests route to the Next.js frontend under `frontend/`;
- `app.py` is excluded from the Vercel build and remains non-production.

Operators must record the following mapping for each release candidate:

| Environment | Required mapping                                                                         | Evidence location                                              |
| ----------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Preview     | Preview deployment URL and durability label: `durable` or `non-durable`.                 | Release-candidate evidence issue.                              |
| Staging     | Vercel project name or deployment URL used for staging frontend and backend/API traffic. | Release-candidate evidence issue.                              |
| Production  | Production project/domain if already known; otherwise explicitly deferred.               | Release-candidate evidence issue or production cutover record. |

Preview deployments must not be treated as staging or production durable proof unless they are explicitly labelled
durable, use PostgreSQL-compatible durable boundaries, and are approved as promotion evidence.

## Staging Database Boundaries

Staging must use Supabase PostgreSQL durable boundaries. SQLite is not accepted as staging durable persistence.

| Boundary              | Environment variable        | Required staging behavior                                                                                                                                | Evidence required                                                                                           |
| --------------------- | --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| App/auth database     | `DATABASE_URL`              | Exists and points to a Supabase PostgreSQL durable app/auth database.                                                                                    | Redacted Supabase project/database label and variable-presence confirmation.                                |
| Asset graph database  | `ASSET_GRAPH_DATABASE_URL`  | Exists and points to the authoritative Supabase PostgreSQL durable graph database. Must be distinct from `DATABASE_URL` unless an exception is approved. | Redacted Supabase project/database label, distinctness confirmation, and hosted persistence smoke evidence. |
| Coordination database | `COORDINATION_DATABASE_URL` | Exists when rebuild lock/job coordination is separated. If absent, coordination fallback boundary is documented.                                         | Redacted Supabase project/database label or explicit shared-boundary statement.                             |

Shared boundaries are allowed only when intentional and documented. If coordination shares the app/auth database, the
release evidence must say so explicitly.

## Required Variable Verification

Before staging promotion, the Secret/config maintainer must confirm:

- `DATABASE_URL` is configured for staging.
- `ASSET_GRAPH_DATABASE_URL` is configured for staging.
- `ASSET_GRAPH_DATABASE_URL` does not point to the same boundary as `DATABASE_URL`, unless an approved exception exists.
- `COORDINATION_DATABASE_URL` is configured if coordination is separated.
- If `COORDINATION_DATABASE_URL` is absent, the fallback boundary is documented.
- `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` are configured through Vercel environment variables.
- No raw secret values are committed or pasted into issues, PRs, logs, or evidence records.

### H-P0-04 / ADR 0007 GitHub Environment secrets

For durable staging **topology**, `COORDINATION_DATABASE_URL` remains conditional when coordination shares another
boundary and that fallback is documented (see Required Variable Verification above). **Separately**, the authz gate
in `staging-promotion.yml` / `production-promotion.yml` (and release-evidence when `hardening_tier=P0`) fails closed
unless these GitHub Environment secrets are all present—partial URL sets must not produce a PASS:

- `ASSET_GRAPH_DATABASE_URL`
- `DATABASE_URL` or `POSTGRES_URL` (at least one)
- `COORDINATION_DATABASE_URL` (required for the authz workflow step even when topology documents a shared-boundary
  fallback—point the secret at the effective coordination boundary)

`hardening_tier=none` on release-evidence is a soft rehearsal and is not H-P0-04 closure. Optional:
`FARDB_UNTRUSTED_DATABASE_ROLES` (defaults apply when unset; leave empty values unset). When inventory includes
non-`public` exposed schemas, set `FARDB_EXPOSED_DATABASE_SCHEMAS` (comma-separated) so the authz gate checks every
schema before PASS; unset defaults to `public` only. Operator procedure:
[Database authorization closure runbook](runbooks/database-authorization-closure.md).

Record only variable presence, provider labels, project labels, redacted URLs, and reviewer sign-off.

## Preview Durability Labels

Every preview deployment used during release evidence capture must be labelled:

- `durable`: the preview uses PostgreSQL-compatible app/auth and graph persistence boundaries suitable for the evidence
  being claimed;
- `non-durable`: the preview may use local, SQLite, in-memory, generated, or otherwise non-authoritative persistence.

Non-durable preview evidence can prove build/deployment shape and bounded health only. It cannot substitute for staging
or production durable graph evidence.

## Staging Promotion Checklist

Open one release-candidate evidence issue using the
[Release candidate evidence capture template](../.github/ISSUE_TEMPLATE/release_candidate_evidence.md), then attach or
link the following evidence:

- [ ] Release commit SHA and full CI run.
- [ ] Staging Vercel project/deployment mapping for frontend and backend/API traffic.
- [ ] Staging database provider recorded as Supabase.
- [ ] Redacted Supabase app/auth, graph, and coordination boundary labels.
- [ ] Confirmation that `DATABASE_URL` exists in staging.
- [ ] Confirmation that `ASSET_GRAPH_DATABASE_URL` exists in staging.
- [ ] Confirmation that `ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL`, or approved exception details.
- [ ] Confirmation that `COORDINATION_DATABASE_URL` exists when coordination is separated, or documented fallback when
      absent.
- [ ] H-P0-04 authz gate: GitHub Environment has asset-graph, auth/app (or postgres fallback), **and**
      `COORDINATION_DATABASE_URL` pointing at the effective coordination boundary (required by the workflow even when
      topology uses a documented shared-boundary fallback; see [closure runbook](runbooks/database-authorization-closure.md)).
- [ ] Preview durability label for any preview evidence used.
- [ ] Hosted readiness with durable persistence required:

  ```bash
  STAGING_BASE_URL="https://staging.example.com"
  python scripts/check_hosted_readiness.py "$STAGING_BASE_URL" --require-persistence
  ```

- [ ] Redacted bounded health output:

  ```bash
  curl -fsS "$STAGING_BASE_URL/api/health/detailed"
  ```

- [ ] Redacted bounded asset smoke output or approved sentinel evidence:

  ```bash
  curl -fsS "$STAGING_BASE_URL/api/assets?per_page=1"
  ```

- [ ] Evidence confirms `graph.persistence_loaded == true`.
- [ ] Evidence confirms `graph.startup_source == "persisted"`.
- [ ] Named deploy, promotion, rollback, restore, and persistence-verification owners are recorded.
- [ ] Security scanner summaries and approved exceptions are attached.
- [ ] DR restore rehearsal evidence is attached or explicitly marked as pending when the release is not final enterprise
      sign-off.

Repository CI success is not hosted durable graph proof. `/api/health/detailed` alone is not hosted durable graph proof.

## Promotion Decision Rule

Staging promotion is blocked when any of the following are true:

- staging provider or boundary records are missing;
- `DATABASE_URL` or `ASSET_GRAPH_DATABASE_URL` is not configured;
- `ASSET_GRAPH_DATABASE_URL` shares the `DATABASE_URL` boundary without an approved exception;
- preview evidence is not clearly labelled durable or non-durable;
- hosted readiness was not run with `--require-persistence`;
- redacted `/api/health/detailed` and `/api/assets?per_page=1` evidence is missing;
- persisted startup evidence does not show `graph.persistence_loaded == true` and `graph.startup_source == "persisted"`;
- named operator ownership is missing;
- unapproved critical/high security findings or undocumented gate exceptions remain.

The promotion approver owns the final gate decision and must link the release-candidate evidence issue from the
promotion record.

## Related Documents

- [Hosted Readiness Evidence Guide](operations/hosted-readiness-evidence-guide.md)
- [Database authorization closure runbook](runbooks/database-authorization-closure.md)
- [Enterprise Deployment Operating Model](enterprise-deployment-operating-model.md)
- [Release Evidence Pack](release-evidence-pack.md)
- [Enterprise Release Checklist](release-checklist.md)
- [Release candidate evidence capture template](../.github/ISSUE_TEMPLATE/release_candidate_evidence.md)
- [State Machine and Operating Authority](governance/state-machine-and-operating-authority.md)

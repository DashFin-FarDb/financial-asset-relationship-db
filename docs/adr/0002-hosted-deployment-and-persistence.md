# ADR 0002: Hosted Deployment and Durable Persistence

For the broader enterprise-readiness audit and rollout plan, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

## Status

Implemented

**Current interpretation:** This ADR remains a historical decision record for hosted deployment and persistence strategy. Current rebuild/recovery state-machine semantics, durable-truth interpretation, operator authority, and exception paths are governed by the canonical [State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md).

## Date

2026-04-30

## Context

FarDb now has a verified local FastAPI + Next.js baseline (PR #1089). Local development uses SQLite (`sqlite:dev.db`). SQLite is not durable on Vercel/serverless filesystems because serverless functions have ephemeral storage — writes are lost between invocations. Hosted production use requires a durable persistence target before feature work depends on stored state.

The current database layer (`api/database.py`) only supports SQLite connections. The asset relationship graph is stored in-memory and rebuilt on every cold start.

## Decision

**FarDb will keep SQLite as the local/development default and use PostgreSQL as the durable hosted persistence target.**

The initial hosted deployment target is the existing Vercel monorepo path for both the Next.js frontend and FastAPI backend.

**PostgreSQL support is landed** in `api/database.py` and the graph persistence layer (Phases 1–3 complete). Hosted staging/production must use PostgreSQL durable boundaries; SQLite remains local/dev (and non-durable demo/preview) only.

## Options Considered

### Option 1: Vercel monorepo + PostgreSQL (Chosen)

**Pros:**
- Vercel already configured (`vercel.json` present)
- Single project for frontend + backend
- Automatic preview deployments
- Zero-config HTTPS and CDN
- PostgreSQL managed options: Vercel Postgres, Neon, Supabase, Railway
- Good Python/FastAPI ecosystem support for PostgreSQL

**Cons:**
- Requires database migration implementation
- Serverless cold starts (acceptable for initial use)

### Option 2: Vercel frontend + separate backend service + PostgreSQL

**Pros:**
- Dedicated backend resources
- More control over backend scaling

**Cons:**
- More complex deployment
- Separate service management
- Higher operational overhead

### Option 3: Managed SQLite-compatible storage

**Pros:**
- Minimal code changes

**Cons:**
- Limited serverless-compatible options
- Turso/libSQL requires dependency changes
- Less mature ecosystem

### Option 4: Hosted file-backed SQLite with persistent volume

**Pros:**
- Existing SQLite code works

**Cons:**
- Not compatible with Vercel serverless
- Requires VM or container hosting
- Connection pooling challenges

### Option 5: Local-first only (defer hosted deployment)

**Pros:**
- No immediate work

**Cons:**
- Blocks hosted use cases
- Delays production feedback

## Consequences

### Positive

- Local/dev remains simple with SQLite (no external dependencies)
- PostgreSQL provides industry-standard durable persistence
- Clear separation between local and production environments
- Hosted deployments possible after PostgreSQL implementation
- Scalable database solution from the start

### Negative

- Requires database layer refactor to support both SQLite and PostgreSQL
- Migration tooling needed (Alembic recommended)
- Connection pooling required for serverless PostgreSQL

### Neutral

- Graph state remains in-memory until Phase 3 introduces durable graph persistence.
- Current hosted deployments with SQLite are explicitly non-durable demos only

### Testing Implications

Current database tests exercise SQLite URIs only. Phase 1 must add PostgreSQL-specific tests for the auth database path, including PostgreSQL URL handling, driver/connection creation, serverless connection pooling assumptions, and continued SQLite compatibility for local development. PostgreSQL support should not be considered complete until both SQLite and PostgreSQL paths are covered.

## Implementation Plan

### Phase 1: PostgreSQL User Auth

Add PostgreSQL support for the API auth/user database while preserving SQLite local dev compatibility.

**Scope:**
- Add PostgreSQL adapter to `api/database.py` ✅
- Add psycopg2-binary driver to `requirements.txt` ✅
- PostgreSQL-compatible DDL for `user_credentials` table ✅
- Automatic placeholder conversion (SQLite `?` → PostgreSQL `%s`) ✅
- POSTGRES_URL fallback support for Vercel deployments ✅
- Maintain backward compatibility with SQLite for local development ✅
- Update deployment docs with PostgreSQL setup guide ✅
- Comprehensive test coverage (unit + opt-in integration) ✅

**Explicitly Deferred to Phase 4:**
- Production-grade connection pooling for serverless
- Database migration tooling (Alembic)

**Current Limitations:**
The Phase 1 implementation creates a new connection per request. This is acceptable for
low-traffic environments but NOT recommended for production at scale. Production deployments
should implement connection pooling (Phase 4) before significant traffic.

**Environment variable handling:**

Vercel Postgres may expose `POSTGRES_*` variables rather than `DATABASE_URL`. Phase 1 adds
explicit settings-layer support for `POSTGRES_URL` as a fallback when `DATABASE_URL` is not set.

### Phase 2: Enhanced Health Checks & Durable Promotion Gate (Completed)

Added `/api/health/detailed` endpoint with database connectivity, graph status, and environment validation. Extended `scripts/check_hosted_readiness.py` and the GitHub Actions workflow with a `--require-persistence` parameter to verify that the graph was loaded successfully from the durable storage boundary during deployment promotion.

### Phase 3: Graph Persistence (Completed)

Implemented graph serialization, deserialization, and PostgreSQL repository boundary support. Verified durability of graph state across application restart cycles.

### Phase 4: Production Optimizations (Future)

Connection pooling tuning, caching strategy, and monitoring remain future production optimizations. Backup and restore strategy/procedures are no longer treated as an undocumented Phase 4 gap: they are documented in [ADR 0005](./0005-backup-restore-dr-strategy.md) and the [backup/restore/DR runbook](../runbooks/backup-restore-dr.md). Automated backup orchestration remains deferred.

## Required Hosted Environment Variables

**Backend (Required):**
- `DATABASE_URL` — Auth/application database. Local/dev: recommended `sqlite:dev.db` or `sqlite:///:memory:` (avoid `sqlite:///./…` under this repo’s custom resolver in `api/database.py`). Hosted staging/production: PostgreSQL URL (**landed** in `api/database.py`; Phase 1 complete).
- `SECRET_KEY` — JWT signing key (≥32 characters outside development/test)
- `ADMIN_USERNAME` — Bootstrap admin username
- `ADMIN_PASSWORD` — Bootstrap admin password

**Backend (Hosted durable graph — required for staging/production promotion):**
- `ASSET_GRAPH_DATABASE_URL` — Durable graph-truth boundary (PostgreSQL in hosted environments)
- `COORDINATION_DATABASE_URL` — Optional; rebuild lock boundary. When unset, settings fall back to `DATABASE_URL` then `POSTGRES_URL`.
- `POSTGRES_URL` — Provider fallback when `DATABASE_URL` is unset (for example Vercel Postgres)

**Backend (Optional):**
- `ENV` — Environment mode (production/staging/development)
- `ALLOWED_ORIGINS` — CORS allowlist (comma-separated)
- `GRAPH_CACHE_PATH` — Graph cache path (ephemeral on serverless)
- `USE_REAL_DATA_FETCHER` — Enable real data fetcher

**Frontend (Required):**
- `NEXT_PUBLIC_API_URL` — API endpoint URL

## Deferred Items

Explicitly out of scope for initial hosted deployment:

- Alternative hosting platforms (AWS, GCP, Azure)
- Self-hosted Docker/Kubernetes deployments
- Multi-region deployments
- Advanced caching (Redis, Vercel KV)
- Real-time WebSocket features
- Advanced auth (OAuth, SAML, multi-tenancy)
- Graph scaling/sharding
- Compliance certifications (SOC2, GDPR)

These are valid future considerations but should not block initial deployment.

## References

- [State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md): current operational authority for durable-truth and rebuild/recovery state-machine interpretation
- [ADR 0001: Production Architecture](0001-production-architecture.md)
- [ADR 0005: Backup, Restore, and Disaster Recovery Strategy](0005-backup-restore-dr-strategy.md)
- [Backup, Restore, and DR Runbook](../runbooks/backup-restore-dr.md)
- [DEPLOYMENT.md](../../DEPLOYMENT.md)
- [VERCEL_DEPLOYMENT_CHECKLIST.md](../../VERCEL_DEPLOYMENT_CHECKLIST.md)
- [Vercel Documentation](https://vercel.com/docs)
- [Vercel Postgres Documentation](https://vercel.com/docs/storage/vercel-postgres)
- [Neon Serverless Postgres](https://neon.tech/)

## Authors

- Claude (AI Agent)
- DashFin-FarDb Organization

## Review and Approval

This ADR was created to establish the hosted deployment and durable persistence strategy after the local development baseline was verified.

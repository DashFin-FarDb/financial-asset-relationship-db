# ADR 0002: Hosted Deployment and Durable Persistence

## Status

Accepted — implementation pending

## Date

2026-04-30

## Context

FarDb now has a verified local FastAPI + Next.js baseline (PR #1089). Local development uses SQLite (`sqlite:dev.db`). SQLite is not durable on Vercel/serverless filesystems because serverless functions have ephemeral storage — writes are lost between invocations. Hosted production use requires a durable persistence target before feature work depends on stored state.

The current database layer (`api/database.py`) only supports SQLite connections. The asset relationship graph is stored in-memory and rebuilt on every cold start.

## Decision

**FarDb will keep SQLite as the local/development default and use PostgreSQL as the durable hosted persistence target.**

The initial hosted deployment target is the existing Vercel monorepo path for both the Next.js frontend and FastAPI backend.

**PostgreSQL support is not yet implemented in the current database layer.** Until PostgreSQL support lands, hosted deployments using SQLite are demo/preview only and must not be treated as durable production persistence.

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

## Implementation Plan

### Phase 1: PostgreSQL User Auth (Next PR)

Add PostgreSQL support for the API auth/user database while preserving SQLite local dev compatibility.

**Scope:**
- Add PostgreSQL adapter to `api/database.py`
- Add connection pooling for serverless
- Add database migration tooling (Alembic)
- PostgreSQL-compatible DDL for `user_credentials` table
- Maintain backward compatibility with SQLite for local development
- Update deployment docs with PostgreSQL setup guide

### Phase 2: Enhanced Health Checks

Add `/api/health/detailed` endpoint with database connectivity, graph status, and environment validation.

### Phase 3: Graph Persistence (Deferred)

Design PostgreSQL schema for assets/relationships and implement graph serialization/deserialization.

### Phase 4: Production Optimizations (Future)

Connection pooling tuning, caching strategy, monitoring, backup procedures.

## Required Hosted Environment Variables

**Backend (Required):**
- `DATABASE_URL` — PostgreSQL connection string (future); currently SQLite for demo/preview only
- `SECRET_KEY` — JWT signing key
- `ADMIN_USERNAME` — Bootstrap admin username
- `ADMIN_PASSWORD` — Bootstrap admin password

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

- [ADR 0001: Production Architecture](0001-production-architecture.md)
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

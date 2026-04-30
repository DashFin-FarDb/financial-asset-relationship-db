# Hosted Deployment and Durable Persistence Strategy

**Status**: Decision Record
**Date**: 2026-04-30
**Issue**: [#1095](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1095)

## Executive Summary

This document defines the hosted deployment and durable persistence strategy for the Financial Asset Relationship Database (FarDb) production architecture (FastAPI backend + Next.js frontend).

**Recommended Path**: Vercel for both frontend and backend with PostgreSQL for durable persistence.

## Current State Audit

### Verified Baseline (as of PR #1089)

- ✅ FastAPI backend starts locally with required env vars
- ✅ Next.js frontend connects to backend
- ✅ `/api/health`, `/api/assets`, `/api/metrics`, `/api/visualization` return valid responses
- ✅ Frontend graph renders without errors
- ✅ Local development uses SQLite (`sqlite:dev.db`)

### Current Architecture Components

**Backend (FastAPI)**
- Entry point: `api.main:app` (thin wrapper)
- Application factory: `api/app_factory.py` (lifespan, middleware, routers)
- Database layer: `api/database.py` (SQLite-focused with connection management)
- Auth layer: `api/auth.py` (JWT-based authentication)
- Graph lifecycle: `api/graph_lifecycle.py` (in-memory graph initialization)
- Settings: `src/config/settings.py` (centralized configuration)

**Frontend (Next.js)**
- Entry point: `frontend/app/page.tsx`
- API client: `frontend/app/lib/api.ts`
- API URL configured via `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`)

**Data Layers**
1. **User credentials**: SQLite database via `DATABASE_URL` (auth/sessions)
2. **Asset graph**: In-memory `AssetRelationshipGraph` initialized at startup
3. **Graph cache**: Optional file-based cache via `GRAPH_CACHE_PATH`

## Mandatory Questions: Answered

### 1. What is the intended hosted shape?

**Answer**: Vercel for both frontend and backend (monorepo deployment)

**Rationale**:
- Vercel is already configured (`vercel.json` present)
- Supports both Next.js and Python serverless functions in a single project
- Automatic preview deployments for PRs
- Zero-config HTTPS and CDN
- Existing documentation references Vercel
- Cost-effective for moderate traffic
- Simpler than managing separate services

**Architecture**:
```
┌─────────────────────────────────────────┐
│           Vercel Project                │
│                                         │
│  ┌──────────────┐   ┌───────────────┐  │
│  │   Next.js    │   │  Python API   │  │
│  │   Frontend   │──▶│  (FastAPI)    │  │
│  │  (Static +   │   │  Serverless   │  │
│  │   SSR)       │   │  Functions    │  │
│  └──────────────┘   └───────┬───────┘  │
│                             │          │
└─────────────────────────────┼──────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   PostgreSQL     │
                    │  (Managed DB)    │
                    │  - User Auth     │
                    │  - Graph Data    │
                    └──────────────────┘
```

### 2. What is the durable database target?

**Answer**: PostgreSQL (managed service)

**Rationale**:
- **SQLite is not durable on Vercel serverless**: Ephemeral filesystem; writes are lost between invocations
- **PostgreSQL advantages**:
  - Industry-standard relational database
  - ACID transactions
  - Connection pooling support
  - Excellent Python/FastAPI ecosystem (`psycopg2`, `asyncpg`, `SQLAlchemy`)
  - Multiple managed options (Vercel Postgres, Neon, Supabase, Railway, Render)
  - Supports both auth credentials and graph persistence in one database
  - Horizontal scaling path if needed

**Provider Options** (in order of integration simplicity):
1. **Vercel Postgres** (recommended for initial deployment)
   - Native Vercel integration
   - Automatic DATABASE_URL injection
   - Built on Neon with pooling
   - Free tier available

2. **Neon** (recommended for flexibility)
   - Serverless PostgreSQL
   - Generous free tier
   - Automatic scaling
   - Branch databases for dev/preview

3. **Supabase**
   - PostgreSQL + auth + realtime
   - Free tier
   - Additional features if needed later

4. **Railway / Render**
   - Simple managed PostgreSQL
   - Predictable pricing

### 3. What parts of the app currently assume SQLite-local semantics?

**Current SQLite Dependencies**:

**A. `api/database.py`**
- `_resolve_sqlite_path()`: Parses `sqlite:///` URIs
- `_DatabaseConnectionManager`: Creates `sqlite3.Connection` objects
- In-memory connection sharing for `sqlite:///:memory:`
- Row factory set to `sqlite3.Row`
- **Migration needed**: Replace with PostgreSQL connection adapter

**B. `src/config/settings.py`**
- `database_url: str | None`: Currently expects SQLite URIs
- `asset_graph_database_url: str | None`: Optional graph persistence URL
- **Migration needed**: Add PostgreSQL connection string validation

**C. Graph initialization (`api/graph_lifecycle.py`)**
- Loads graph in-memory at startup from `create_sample_database()` or `RealDataFetcher`
- No persistence to database currently
- Graph lives only in process memory (lost on serverless cold start)
- **Migration needed**: Add graph persistence/restoration to PostgreSQL

**D. Schema initialization (`api/database.py:initialize_schema`)**
- Creates `user_credentials` table with SQLite-specific DDL
- No migration/versioning system
- **Migration needed**: PostgreSQL-compatible DDL, add migration tooling

**E. Admin bootstrap (`api/auth.py`)**
- Seeds admin user on startup if database is empty
- Relies on `api/database.py` helpers
- **Migration needed**: Works with PostgreSQL after database layer migration

**F. Environment assumptions**
- `.env.example` shows `DATABASE_URL=sqlite:dev.db`
- `DEPLOYMENT.md` warns against SQLite on serverless
- No PostgreSQL configuration guidance yet

### 4. What environment variables are required in hosted deployment?

**Backend Environment Variables (Required)**:

```bash
# Database (PostgreSQL connection string)
DATABASE_URL=postgresql://user:password@host:5432/database
# Example: postgresql://user:pass@ep-xyz.us-east-1.aws.neon.tech/fardb

# Auth (JWT signing secret - CRITICAL: generate unique per environment)
SECRET_KEY=<long-random-string-min-32-chars>

# Bootstrap admin user (only needed on first deploy or empty database)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>

# Optional admin user details
ADMIN_EMAIL=admin@example.com
ADMIN_FULL_NAME=Administrator
ADMIN_DISABLED=false
```

**Backend Environment Variables (Optional)**:

```bash
# Environment mode
ENV=production  # or "staging", "development"

# CORS allowlist (comma-separated origins)
ALLOWED_ORIGINS=https://your-frontend.vercel.app,https://custom-domain.com

# Graph data source (if using real data or caching)
USE_REAL_DATA_FETCHER=false
GRAPH_CACHE_PATH=/tmp/graph-cache.json  # Note: /tmp on Vercel is ephemeral
REAL_DATA_CACHE_PATH=/tmp/real-data-cache.json

# Separate graph persistence (if not using DATABASE_URL for graph)
# ASSET_GRAPH_DATABASE_URL=postgresql://...
```

**Frontend Environment Variables (Required)**:

```bash
# API endpoint (auto-set on Vercel if using same project)
NEXT_PUBLIC_API_URL=https://your-project.vercel.app
```

**Frontend Environment Variables (Optional)**:

```bash
# Network visualization limits (if customizing)
NEXT_PUBLIC_MAX_NODES=500
NEXT_PUBLIC_MAX_EDGES=1000
```

**Vercel-Specific Automatic Variables**:
- `VERCEL_URL`: Automatic deployment URL (can use for `NEXT_PUBLIC_API_URL`)
- `VERCEL_ENV`: Environment type (production/preview/development)
- Vercel Postgres injects `POSTGRES_URL`, `POSTGRES_PRISMA_URL`, `POSTGRES_URL_NON_POOLING`

### 5. What is the correct deployment readiness check?

**Health Check Endpoint**: `GET /api/health`

**Comprehensive Readiness Verification**:

```bash
# 1. Health endpoint responds
curl https://your-project.vercel.app/api/health
# Expected: {"status": "healthy"}

# 2. Database connectivity
# Health endpoint should be enhanced to check:
# - Database connection successful
# - User credentials table exists
# - Can execute basic query

# 3. Graph initialization
# Backend logs should show:
# "Graph initialized successfully"
# Health endpoint should verify graph is loaded

# 4. Frontend can reach backend
# Open https://your-project.vercel.app
# Should load without "Failed to load data" error

# 5. API endpoints return valid data
curl https://your-project.vercel.app/api/assets
curl https://your-project.vercel.app/api/metrics
curl https://your-project.vercel.app/api/visualization

# 6. CORS configured correctly
# Browser console should show no CORS errors when frontend calls API
```

**Recommended Enhancement**: Add `/api/health/detailed` endpoint that checks:
- Database connection status
- Graph initialization status
- Required environment variables present
- User table exists and has at least one user

### 6. Which current docs are authoritative and which are local/demo only?

**Authoritative Production Docs**:
- ✅ `README.md` - Quick start and production setup
- ✅ `DEPLOYMENT.md` - Production deployment guide (Vercel-focused)
- ✅ `VERCEL_DEPLOYMENT_CHECKLIST.md` - Step-by-step deployment checklist
- ✅ `docs/adr/0001-production-architecture.md` - ADR declaring FastAPI + Next.js as production
- ✅ `.env.example` - Environment variable template (needs PostgreSQL update)
- ✅ `vercel.json` - Vercel configuration (authoritative for Vercel deployments)

**Local/Demo Documentation**:
- ⚠️ `docker-compose.yml` - Currently runs Gradio (non-production); needs update for production stack
- ⚠️ `Dockerfile` - Currently builds Gradio image; needs production FastAPI + Next.js variant

**Scripts**:
- ✅ `run-dev.sh` / `run-dev.bat` - Local development only (production uses Vercel)

**Documentation Gaps Identified**:
- No PostgreSQL setup guide
- No database migration documentation
- No graph persistence/restoration guide
- No production environment variable checklist
- No hosted deployment smoke-test procedure

## Recommended Deployment Architecture

### Production Stack

```
User Browser
     │
     ▼
┌─────────────────────────────────────────────────┐
│  Vercel Edge Network (CDN + HTTPS)              │
└────────────┬──────────────────────┬──────────────┘
             │                      │
             ▼                      ▼
    ┌────────────────┐    ┌─────────────────────┐
    │  Next.js       │    │  FastAPI            │
    │  Frontend      │    │  Python Serverless  │
    │  - Static      │───▶│  - /api/* routes   │
    │  - SSR pages   │    │  - JWT auth         │
    │                │    │  - Rate limiting    │
    └────────────────┘    └──────────┬──────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │  PostgreSQL          │
                          │  (Vercel Postgres    │
                          │   or Neon)           │
                          │                      │
                          │  Tables:             │
                          │  - user_credentials  │
                          │  - assets (future)   │
                          │  - relationships     │
                          │  - graph_cache       │
                          └──────────────────────┘
```

### Data Persistence Strategy

**Phase 1: User Authentication (Immediate)**
- Migrate `user_credentials` table to PostgreSQL
- Keep existing schema, port SQLite DDL to PostgreSQL-compatible syntax
- Use connection pooling for serverless environment

**Phase 2: Graph Persistence (Near-term)**
Current: Graph is in-memory only, rebuilt on every cold start from sample data.

Recommended:
1. Add `assets` and `relationships` tables to PostgreSQL
2. Add `graph_metadata` table for cache invalidation
3. Implement graph serialization/deserialization
4. Load graph from database on startup
5. Optional: Cache serialized graph in memory with TTL

**Phase 3: Real-time Updates (Future)**
- Add API endpoints to modify graph
- Implement database-backed graph mutations
- Add WebSocket support for real-time updates (if needed)

## Implementation Roadmap

### Immediate (This PR)
- ✅ Document deployment strategy (this file)
- ✅ Update `.env.example` with PostgreSQL examples
- ✅ Update docs to clarify SQLite is local-only
- ✅ Create follow-up implementation issues

### Phase 1: PostgreSQL User Auth (Next PR)
**Scope**: Migrate user authentication to PostgreSQL

1. Add PostgreSQL dependencies (`psycopg2-binary` or `asyncpg`)
2. Create database adapter layer:
   - Abstract database interface (SQLite for local, PostgreSQL for production)
   - Connection pooling for serverless
3. Update `api/database.py` to support both SQLite and PostgreSQL
4. PostgreSQL-compatible DDL for `user_credentials` table
5. Add database migration tooling (Alembic recommended)
6. Update environment variable validation
7. Test local development (SQLite) still works
8. Test production deployment (PostgreSQL)
9. Update deployment docs with PostgreSQL setup instructions

**Validation**:
- Local dev with SQLite works
- Vercel deployment with PostgreSQL works
- User login/auth works in both environments
- Admin bootstrap works in both environments

### Phase 2: Enhanced Health Checks (Quick Win)
**Scope**: Better deployment verification

1. Add `/api/health/detailed` endpoint
2. Check database connectivity
3. Check graph initialization status
4. Check environment variables
5. Return structured health report
6. Update deployment checklist to use new endpoint

### Phase 3: Graph Persistence (Deferred)
**Scope**: Make graph data durable

1. Design PostgreSQL schema for assets/relationships
2. Add graph serialization logic
3. Add graph database repository layer
4. Implement load/save operations
5. Add cache invalidation strategy
6. Update graph lifecycle for database-backed initialization
7. Migration path for existing deployments

### Phase 4: Production Optimizations (Future)
- Connection pooling tuning
- Query optimization
- Caching strategy (Redis/Vercel KV if needed)
- Rate limiting refinement
- Monitoring and logging (Sentry, LogTail, etc.)
- Backup and disaster recovery procedures

## Deferred Decisions

**Explicitly out of scope for initial hosted deployment**:

1. **Alternative hosting platforms**: AWS, GCP, Azure deployment paths
2. **Self-hosted deployments**: Docker/Kubernetes production configurations
3. **Multi-region deployments**: Geographic distribution and replication
4. **Advanced caching**: Redis, Vercel KV, or edge caching
5. **Real-time features**: WebSocket support, live updates
6. **Advanced auth**: OAuth, SAML, multi-tenancy
7. **Graph scaling**: Sharding, read replicas, denormalization
8. **CI/CD beyond Vercel**: Custom deployment pipelines
9. **Monitoring/observability**: APM, distributed tracing
10. **Compliance**: SOC2, GDPR, data residency requirements

These are valid future considerations but should not block the initial hosted deployment.

## Risk Assessment

### High Risk (Must Address)
- ✅ **SQLite not durable on serverless**: Mitigated by PostgreSQL migration (Phase 1)
- ✅ **Graph lost on cold start**: Documented limitation; Phase 3 adds persistence
- ✅ **No migration tooling**: Phase 1 adds Alembic

### Medium Risk (Monitor)
- ⚠️ **Serverless cold starts**: Acceptable for initial deployment; optimize in Phase 4
- ⚠️ **Connection pool exhaustion**: Use connection pooling; monitor in production
- ⚠️ **Graph initialization latency**: Acceptable for read-heavy workload; cache if needed

### Low Risk (Acceptable)
- ✓ **Vercel vendor lock-in**: Minimal lock-in; can migrate to other hosts if needed
- ✓ **Cost at scale**: Free tier adequate for initial use; predictable scaling costs
- ✓ **Database provider choice**: Multiple PostgreSQL options available

## Success Criteria

A hosted deployment is successful when:

1. ✅ Backend deploys to Vercel and starts without errors
2. ✅ Frontend deploys to Vercel and loads in browser
3. ✅ PostgreSQL database is provisioned and connected
4. ✅ `/api/health` returns healthy status
5. ✅ User authentication works (login, JWT tokens)
6. ✅ All API endpoints return valid data
7. ✅ Frontend graph visualization renders
8. ✅ No CORS errors in browser console
9. ✅ Preview deployments work for PRs
10. ✅ Documentation guides a new user through deployment
11. ✅ Local development (SQLite) still works for contributors

## Follow-Up Issues to Create

After this PR is merged, create these implementation issues:

1. **Issue: Add PostgreSQL support to database layer**
   - Scope: Phase 1 implementation
   - Add PostgreSQL adapter, migration tooling, connection pooling
   - Maintain backward compatibility with SQLite for local dev

2. **Issue: Add detailed health check endpoint**
   - Scope: Phase 2 implementation
   - `/api/health/detailed` with database and graph status

3. **Issue: Design PostgreSQL schema for graph persistence**
   - Scope: Phase 3 planning
   - Schema design for assets, relationships, graph metadata
   - Migration strategy from in-memory to database-backed graph

4. **Issue: Update deployment documentation for PostgreSQL**
   - Scope: Documentation enhancement
   - PostgreSQL provider setup guides (Vercel Postgres, Neon, etc.)
   - Environment variable configuration
   - Deployment verification procedures

5. **Issue: Add Vercel deployment smoke test**
   - Scope: Testing/automation
   - Automated smoke test for Vercel deployments
   - Run after preview deployment completes
   - Verify health, auth, API endpoints

## References

- [ADR 0001: Production Architecture](./adr/0001-production-architecture.md)
- [DEPLOYMENT.md](../DEPLOYMENT.md)
- [VERCEL_DEPLOYMENT_CHECKLIST.md](../VERCEL_DEPLOYMENT_CHECKLIST.md)
- [Vercel Documentation](https://vercel.com/docs)
- [Vercel Postgres Documentation](https://vercel.com/docs/storage/vercel-postgres)
- [Neon Serverless Postgres](https://neon.tech/)

## Authors

- Claude (AI Agent)
- DashFin-FarDb Organization

---

**Last Updated**: 2026-04-30
**Next Review**: After Phase 1 implementation

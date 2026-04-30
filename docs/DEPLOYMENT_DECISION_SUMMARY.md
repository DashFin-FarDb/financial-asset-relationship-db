# Hosted Deployment Strategy - Decision Summary

**Issue**: #1095
**Date**: 2026-04-30
**Status**: Decision Made - Implementation Pending

This is a concise summary of the hosted deployment and durable persistence strategy decision.
For comprehensive details, see [HOSTED_DEPLOYMENT_STRATEGY.md](HOSTED_DEPLOYMENT_STRATEGY.md).

## Current State

**Verified Baseline (PR #1089)**:
- ✅ FastAPI backend + Next.js frontend runs locally
- ✅ All API endpoints functional (`/api/health`, `/api/assets`, `/api/metrics`, `/api/visualization`)
- ✅ Frontend graph visualization working
- ✅ Uses SQLite (`sqlite:dev.db`) for local development
- ⚠️ SQLite is **not durable** on Vercel/serverless (ephemeral filesystem)

**Current Architecture**:
- Backend: FastAPI (`api.main:app`) with SQLite auth database
- Frontend: Next.js (connects via `NEXT_PUBLIC_API_URL`)
- Graph: In-memory `AssetRelationshipGraph` (rebuilt on each cold start)
- Deployment: Configured for Vercel (`vercel.json` present)

## Recommended Hosted Architecture

**Deployment Platform**: Vercel (monorepo deployment - frontend + backend in one project)

**Database**: PostgreSQL (managed service)
- Recommended providers: Vercel Postgres, Neon, Supabase, Railway
- Durable persistence for user auth and (future) graph data
- Connection pooling for serverless environment

**Architecture Diagram**:
```
Vercel Project
├── Next.js Frontend (static + SSR)
├── FastAPI Backend (Python serverless functions)
└── PostgreSQL Database (managed, external)
    ├── user_credentials (auth)
    └── (future) assets, relationships (graph persistence)
```

## Recommended Durable Persistence Target

**PostgreSQL** via managed service

**Why PostgreSQL**:
- SQLite files are ephemeral on Vercel serverless
- PostgreSQL is industry-standard, ACID-compliant
- Excellent Python/FastAPI ecosystem support
- Multiple managed provider options
- Scales with application growth

**Provider Recommendation** (in order):
1. **Vercel Postgres** (easiest integration)
2. **Neon** (serverless PostgreSQL, generous free tier)
3. **Supabase** (PostgreSQL + additional features)

## Required Environment Variables

**Backend (Production)**:
```bash
DATABASE_URL=postgresql://user:password@host:5432/database  # PostgreSQL connection string
SECRET_KEY=<long-random-string>                              # JWT signing key
ADMIN_USERNAME=admin                                          # Bootstrap admin user
ADMIN_PASSWORD=<strong-password>                              # Bootstrap password
ENV=production                                                # Environment mode
ALLOWED_ORIGINS=https://your-app.vercel.app                   # CORS allowlist
```

**Frontend (Production)**:
```bash
NEXT_PUBLIC_API_URL=https://your-project.vercel.app  # API endpoint
```

**Local Development**:
```bash
DATABASE_URL=sqlite:dev.db                     # SQLite for local dev
SECRET_KEY=local-dev-secret                    # Local JWT secret
ADMIN_USERNAME=admin                           # Local admin
ADMIN_PASSWORD=admin                           # Local password
NEXT_PUBLIC_API_URL=http://localhost:8000      # Local API
```

## Documentation Updates Needed

**Files Updated in This PR**:
- ✅ `docs/HOSTED_DEPLOYMENT_STRATEGY.md` - Comprehensive strategy document (NEW)
- ✅ `docs/DEPLOYMENT_DECISION_SUMMARY.md` - This summary (NEW)
- ✅ `.env.example` - Added PostgreSQL examples
- ✅ `README.md` - Reference to strategy document
- ✅ `DEPLOYMENT.md` - PostgreSQL requirement clarified
- ✅ `VERCEL_DEPLOYMENT_CHECKLIST.md` - Current limitations noted

**Files Requiring Future Updates** (in implementation PRs):
- `api/database.py` - Add PostgreSQL adapter
- `src/config/settings.py` - PostgreSQL connection validation
- `api/graph_lifecycle.py` - Graph persistence/restoration (Phase 3)
- Docker files - Align with production architecture

## Implementation Follow-Up PRs

**Phase 1: PostgreSQL User Auth** (Immediate Next Step)
- Add PostgreSQL support to `api/database.py`
- Add connection pooling for serverless
- Add database migration tooling (Alembic)
- Maintain backward compatibility with SQLite for local dev
- Update deployment docs with PostgreSQL setup guide

**Phase 2: Enhanced Health Checks** (Quick Win)
- Add `/api/health/detailed` endpoint
- Check database connectivity, graph status, environment config
- Improve deployment verification

**Phase 3: Graph Persistence** (Deferred)
- Design PostgreSQL schema for assets/relationships
- Implement graph serialization/deserialization
- Add graph database repository
- Make graph data durable across restarts

**Phase 4: Production Optimizations** (Future)
- Connection pooling tuning
- Caching strategy
- Monitoring and logging
- Backup procedures

## Deferred Items

**Explicitly Out of Scope** (for initial hosted deployment):
- Alternative hosting platforms (AWS, GCP, Azure)
- Self-hosted Docker/Kubernetes deployments
- Multi-region deployments
- Advanced caching (Redis, Vercel KV)
- Real-time WebSocket features
- Advanced auth (OAuth, SAML)
- Graph scaling/sharding
- Compliance certifications

These are valid future considerations but should not block initial deployment.

## Success Criteria

Hosted deployment is successful when:

1. ✅ Backend deploys to Vercel without errors
2. ✅ Frontend deploys to Vercel and loads
3. ✅ PostgreSQL database connected
4. ✅ `/api/health` returns healthy
5. ✅ User authentication works
6. ✅ All API endpoints return valid data
7. ✅ Frontend visualization renders
8. ✅ No CORS errors
9. ✅ Preview deployments work
10. ✅ Documentation guides deployment
11. ✅ Local SQLite dev still works

## Next Actions

1. **Merge this PR** - Establishes deployment strategy
2. **Create Phase 1 implementation issue** - PostgreSQL database layer
3. **Create Phase 2 implementation issue** - Enhanced health checks
4. **Begin Phase 1 implementation** - PostgreSQL support

## References

- [Comprehensive Strategy Document](HOSTED_DEPLOYMENT_STRATEGY.md)
- [ADR 0001: Production Architecture](adr/0001-production-architecture.md)
- [DEPLOYMENT.md](../DEPLOYMENT.md)
- [VERCEL_DEPLOYMENT_CHECKLIST.md](../VERCEL_DEPLOYMENT_CHECKLIST.md)
- [Vercel Documentation](https://vercel.com/docs)

---

**Decision Made**: 2026-04-30
**Implementation**: Phased approach starting with PostgreSQL support
**Risk**: Low - Clear path, proven technology stack

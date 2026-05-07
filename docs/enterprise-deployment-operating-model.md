# Enterprise Deployment Operating Model

This document defines the operating model for the Financial Asset Relationship Database (FarDb) across environments. It outlines deployment ownership, required configuration, topology decisions, promotion and rollback boundaries, and operator responsibilities.

## Operating Topology

The current selected initial topology (as defined in ADR 0002) is:

- **Vercel monorepo** as the initial hosted deployment target for the Next.js frontend and FastAPI backend.
- **PostgreSQL** as the durable hosted persistence target. (The provider-level choice—such as Vercel Postgres, Neon, Supabase, Railway, or another managed PostgreSQL-compatible service—remains flexible unless decided by a later child issue).
- **SQLite** retained for local development and non-durable demo/preview use only.
- **Vercel environment variables** as the initial deployment secret source when using Vercel.

## Environment Boundaries

- **Local Environment**: Uses SQLite for rapid development and testing.
- **Preview Environment**:
  - May use an isolated non-production PostgreSQL instance when validating durable persistence behavior.
  - May use explicitly non-durable SQLite/demo storage when the preview is only validating frontend/API wiring.
  - **Important**: Non-durable preview environments must be clearly labeled as such and must not be treated as proof of production persistence.
- **Staging Environment**: Uses PostgreSQL. Acts as a pre-production gate to verify full persistence, migration, and integration behavior.
- **Production Environment**: Uses PostgreSQL. The authoritative source of truth.

## Deployment Ownership

- **Frontend**: The Next.js frontend is deployed and served as a Vercel application.
- **Backend**: The FastAPI backend is deployed as a serverless function within the same Vercel monorepo.

## Environment Variables

### Application Database

The application database stores user credentials and other API-level state.

- `DATABASE_URL`: Connection string for the application database.
  - Local/dev: `sqlite:dev.db`
  - Hosted/production: `postgresql://user:password@host:5432/database`

### Graph Persistence

The graph database stores durable assets, relationships, and evidence metadata.

- `ASSET_GRAPH_DATABASE_URL`: Connection string for graph persistence. This is explicitly distinguished from `DATABASE_URL` to allow independent scaling or separate databases.

### Other Required Settings

- `SECRET_KEY`: Long random string for JWT signing.
- `ADMIN_USERNAME` / `ADMIN_PASSWORD`: Used to bootstrap the initial user if the configured database has no users.

## Promotion Gates

To promote a release from preview to staging, and staging to production, the following criteria must be met:

1. Automated CI checks (tests, linting, type checks) must pass.
2. The `GET /api/health/detailed` endpoint must report a healthy state in the current environment.
3. Smoke tests verifying graph readiness and core API functionality must pass.

## Verification & Smoke Testing

Operators verify deployment readiness using the `GET /api/health/detailed` endpoint. This endpoint provides bounded, non-secret diagnostics.

Acceptance criteria for a healthy deployment:

* Returns `status: "healthy"`.
* Graph availability is confirmed with non-zero asset and relationship counts (if graph is seeded).
* Application database connection is reported as reachable.
## Rollback Process

- **Deployment Rollback**: Vercel allows instant rollbacks to a previous deployment. Document deployment rollback expectations, including Vercel deployment promotion/rollback boundaries.
- **Data Recovery**: Full backup/restore and data recovery runbooks are explicitly deferred to Stage 7. Until then, operators must exercise caution with database schema migrations and data deletions.

## Secret Handling

- **Production/Staging**: Secrets (`SECRET_KEY`, `ADMIN_PASSWORD`, PostgreSQL URLs) must be configured securely via the hosting platform's secret manager (e.g., Vercel Environment Variables). They must never be checked into version control.
- **Local Development**: Use a local `.env` file for development secrets. Ensure `.env` remains in `.gitignore`.

## Operator Responsibilities & Incident Response

In the event of degraded application state:

1. **Detect**: Check the `GET /api/health/detailed` endpoint. If it returns `status: "degraded"`, it will indicate which component (graph or database) is failing.
2. **Inspect**: Review the backend logs (via Vercel Functions logs) to identify the specific failure cause without exposing secrets to end-users.
3. **Mitigate**: If a recent deployment caused the degradation, use the hosting platform's rollback feature. If the database is unreachable, verify connection strings and database provider status.

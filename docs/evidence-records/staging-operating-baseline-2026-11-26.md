# Staging Deployment Operating Baseline Evidence Record (2026-11-26)

**Status:** Satisfied
**Issue:** [#1910](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1910)
**Baseline Spec:** [docs/staging-deployment-operating-baseline.md](../staging-deployment-operating-baseline.md)
**Verified `main` Commit:** `fe55f184096623f4527b5f92a3b1ed35eef1ade1` (PR #1963 merge)

## Vercel Project & Environment Mapping

- **Vercel Project (standing reference):** `mohavros-projects/financial-asset-relationship-db`
- **Routing (`vercel.json`):** `/api/*` and `/token` route to FastAPI (`api/main.py`); all other routes serve the Next.js frontend (`frontend/`). `app.py` (Gradio) is excluded.
- **Dated Staging Preview Snapshot (2026-11-26):** `https://financial-asset-relationship-f7edx0v0b-mohavros-projects.vercel.app` (ephemeral deployment snapshot used for this capture; not a permanent standing URL).
- **Preview Durability Label:** **`durable`** (backed by Supabase PostgreSQL durable persistence; not SQLite or in-memory sample data).
- **Standing Production Alias (deferred cutover):** `https://financial-asset-relationship-db-nine.vercel.app`

## Named Operator Ownership

| Role | Named Owner |
| --- | --- |
| Deploy owner | `mohavro` |
| Promotion owner | `mohavro` |
| Rollback owner | `mohavro` |
| Restore owner | `mohavro` |
| Persistence-verification owner | `mohavro` |

## Staging Database Provider & Redacted Boundary Record

- **Database Provider:** Supabase PostgreSQL (`combined` profile / `hosted-legacy-v1` lineage ratified under closed issues [#1907](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1907) and [#1908](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1908)).
- **App/Auth Boundary (`DATABASE_URL`):** Present in Vercel Preview, Vercel Production, and GitHub `staging` environment; uses restricted least-privilege auth runtime role (`fardb_login_auth` / `fardb_runtime_auth`).
- **Asset Graph Boundary (`ASSET_GRAPH_DATABASE_URL`):** Present in Vercel Preview, Vercel Production, and GitHub `staging` environment; uses restricted least-privilege graph runtime role (`fardb_login_graph` / `fardb_runtime_graph`). Approved shared-cluster `combined` topology with distinct least-privilege runtime roles per CQ-03D (#1907/#1908).
- **Coordination Boundary (`COORDINATION_DATABASE_URL`):** Present in Vercel Preview, Vercel Production, and GitHub `staging` environment; uses restricted least-privilege coordination runtime role (`fardb_login_coordination` / `fardb_runtime_coordination`).
- **Secret Management Posture:**
  - GCP Secret Manager (`gcaiv001-95668`) holds `fardb-production-secret-key`, `fardb-runtime-auth-password`, `fardb-runtime-graph-password`, and `fardb-runtime-coordination-password`.
  - `ADMIN_PASSWORD` removed from Vercel Preview runtime per the staging operating baseline.
  - No raw secrets, passwords, or connection strings are recorded.

## GitHub `staging` Environment Secrets (H-P0-04)

Verified present via `gh api repos/DashFin-FarDb/financial-asset-relationship-db/environments/staging/secrets`:

- `ASSET_GRAPH_DATABASE_URL`
- `COORDINATION_DATABASE_URL`
- `DATABASE_URL`
- `HOSTED_READINESS_BASE_URL`

## Hosted Durable Readiness Smoke Evidence

- **Command:** `python scripts/check_hosted_readiness.py https://financial-asset-relationship-f7edx0v0b-mohavros-projects.vercel.app --require-persistence --timeout 30`
- **Result:** **PASSED** (`Hosted readiness smoke check passed.`, exit code `0`)
- **Observed `/api/health/detailed`:**
  - `status`: `"healthy"`
  - `graph_persistence_configured`: `true`
  - `graph.available`: `true`
  - `graph.lifecycle_state`: `"READY"`
  - `graph.startup_source`: `"persisted"`
  - `graph.persistence_enabled`: `true`
  - `graph.persistence_loaded`: `true`
  - `graph.asset_count`: `13`
  - `graph.relationship_count`: `14`
  - `database.configured`: `true`
  - `database.type`: `"postgresql"`
  - `database.reachable`: `true`
- **Redacted `/api/assets?per_page=1` Evidence (2026-11-26T23:57Z):**
  - HTTP `200 OK`
  - `total`: `13`, `page`: `1`, `per_page`: `1`, `hasMore`: `true`
  - `items[0]`: `id: "AAPL"`, `symbol: "AAPL"`, `name: "Apple Inc."`, `asset_class: "Equity"`, `sector: "Technology"`, `currency: "USD"` (valuation fields present; zero credentials or raw DB details).

## Promotion Decision Rule

No item in the staging Promotion Decision Rule is blocking for this durable staging baseline (provider boundaries, H-P0-04 GitHub `staging` secrets, named operator ownership, durable `--require-persistence` readiness smoke, and `/api/assets?per_page=1` persisted data proof are all recorded above).

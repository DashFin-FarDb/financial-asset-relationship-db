# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Enterprise readiness hardenings `H-P1-04`, `H-P2-01`–`H-P2-05`, and `H-P3-01`–`H-P3-05`:
  - Distributed lock fencing tokens (`fencing_token` + `verify_fencing_token()`), live active-executor lock/heartbeat resolution, and unified stale-only orphan auto-recovery
  - Partial unique index `uq_rebuild_jobs_single_running` enforcing single running rebuild job (applied to hosted Supabase) and cross-boundary Graph vs. Coordination skew checker (`scripts/check_restore_boundary_skew.py`)
  - Production lockdown of `/docs`, `/redoc`, `/openapi.json`, `/api/metrics`, and `/api/slo/status` when `ENV=production`
  - Global `slowapi` rate limiting (`RATE_LIMIT_STORAGE_URI`, proxy-aware `get_client_ip`), `REBUILD_OPERATOR_USERNAMES` RBAC allowlist, and staging/production boot-admin upsert guard
  - Slim Vercel serverless `api/requirements.txt` and `psycopg2.pool.ThreadedConnectionPool` with `atexit` disposal
  - Separation-of-duties (`--enforce-sod`) and evidence-expiry (`--enforce-expiry`) checks in `scripts/verify_staging_promotion.py`
- Executed all 5 operational drills (`docs/testing/operational-drill-execution-records.md`), recorded PostgreSQL 18.6 `SCALE10K` (10,000 assets / 50,000 relationships) baseline, adopted `ADR 0012` Active-Passive multi-region strategy, and recorded SHA-bound operator sign-off
- Production container stack (`Dockerfile.api`, `Dockerfile.frontend`, `docker-compose.production.yml`) with strict `/api/ready` healthchecks and security/observability env passthroughs (PR #2009)
- JWT key rotation (`JWT_KEY_ID`, `JWT_PREVIOUS_SECRET_KEYS`), TTL-bounded `jti` revocation, and `POST /api/auth/logout` (PR #1993)
- Shared rate-limit store precedence (`RATE_LIMIT_STORAGE_URI` > `UPSTASH_REDIS_URL` > `REDIS_URL`) with fail-closed `REQUIRE_SHARED_RATE_LIMIT_STORE` guard (PR #1994)
- Full observability stack: auto-provisioned Grafana dashboards (`api-overview.json`, `rebuild-operations.json`, `slo-compliance.json`, `graph-postgres-bridge.json`), Prometheus/Alertmanager routing, Grafana datasource plugins (`vercel`, `netlify`, `sentry`), Graph↔DB boundary metrics, optional OTLP tracing export (`src/observability/tracing.py`), optional `LOG_FILE_PATH` JSON log output, strict `GET /api/ready` probe, and auth/rate-limit/idempotency/ingestion Prometheus metrics (PRs #1995, #2001–#2007)
- Full-stack Playwright E2E smoke suite (`npm run test:e2e`, PR #1996) and resilient data ingestion adapter (`src/data/ingestion_resilience.py`, PR #1997)
- Atomic monotonic fencing CAS (`renew_owned_lock`), `Idempotency-Key` support on `POST /api/graph/rebuild`, and chunked PostgreSQL bulk upsert fast path (PRs #1998–#2000)
- Application RBAC role hierarchy (`viewer`, `analyst`, `operator`, `admin`), reusable `require_roles()` dependency, JWT `roles` claim, `POST /api/assertions` proposer guard, and `auth_access_denied_total` metric (PR #2011)
- Cumulative `hardening_tier` (`none`/`P0`/`P1`/`P2`/`P3`) workflow gates in `.github/workflows/release-evidence-verify.yml` (PR #2010)
- Dependabot 0-alert remediation (`filelock==4.2.1` in `requirements-ci-security.txt`, `minimatch==11.0.9` in `frontend/package-lock.json`, PR #2008)

### Changed

- Centralized settings in `src/config/settings.py` via `pydantic-settings`
- Decoupled `RebuildExecutor` and `ReconciliationEngine`
- Parameterized developer scripts and docs, removing hardcoded connection strengths and ports
- Consolidated root testing entrypoint (`TESTING.md`), relocated root test scripts (`scripts/test_db_module.py`, `tests/integration/test_supabase.py`), and refreshed core developer documentation (`DATABASE.md`, `QUICK_START.md`, `DOCKER.md`, `DEPLOYMENT.md`, `ARCHITECTURE.md`, `README.md`, `AGENTS.md`, `VERCEL_DEPLOYMENT_CHECKLIST.md`)

### Removed

- Archived 118 historical root and `docs/` files locally with SHA-256 manifests and removed 3 zero-byte CI log artifacts from the repository
- Removed inappropriate CI/CD workflow files (`objective-c-xcode.yml`, `go.yml`, `dotnet-desktop.yml`) and consolidated legacy workflows into `ci.yml`

## [1.0.0] - 2024-10-30

### Added

- Initial release
- Financial Asset Relationship Database with 3D visualization
- Support for multiple asset classes (Equity, Bond, Commodity, Currency, Derivative)
- Automatic relationship discovery between assets
- Regulatory event tracking and impact modeling
- Interactive Gradio web interface
- 3D network visualization with Plotly
- Metrics and analytics dashboard
- Schema and business rules reporting
- Asset explorer with detailed information
- Real-time data fetching with yfinance
- Sample data generation
- Comprehensive documentation (README.md, AI_RULES.md)

### Asset Classes

- Equities with P/E ratios, dividend yields, EPS
- Fixed Income with yield, duration, credit ratings
- Commodities with futures and spot prices
- Currencies with exchange rates
- Regulatory events with impact scoring

### Relationship Types

- Sector affinity (same_sector)
- Corporate links (corporate_bond_to_equity)
- Commodity exposure
- Currency risk
- Income comparison (dividend vs yield)
- Event impact

### Visualizations

- 3D network graph with deterministic positioning
- Asset class color coding
- Relationship strength visualization
- Metrics dashboard
- Schema documentation

---

## Version History

### Version Numbering

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

### Unreleased Changes

Changes in the `[Unreleased]` section are features and fixes that have been committed but not yet released.

### Release Process

1. Update CHANGELOG.md
2. Update version in pyproject.toml
3. Commit changes
4. Tag release: `git tag -a v1.0.0 -m "Release v1.0.0"`
5. Push tags: `git push --tags`

---

[Unreleased]: https://github.com/mohavro/financial-asset-relationship-db/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/mohavro/financial-asset-relationship-db/releases/tag/v1.0.0

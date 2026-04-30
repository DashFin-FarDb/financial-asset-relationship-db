## Primary seam / decision

Add PostgreSQL database backend support to `api/database.py` while preserving SQLite as the local/development default. This implements Phase 1 from ADR 0002: Hosted Deployment and Durable Persistence.

## Why this seam now

ADR 0002 established the hosted deployment strategy requiring durable persistence. The current database layer only supports SQLite, which is ephemeral on serverless platforms. PostgreSQL support is the foundational requirement for hosted production deployments on Vercel with managed PostgreSQL (Vercel Postgres, Neon, Supabase, Railway).

This is Phase 1 of the implementation plan: PostgreSQL support for the API auth/user database.

## In scope

- [x] Database URL detection logic (PostgreSQL vs SQLite)
- [x] PostgreSQL connection creation using psycopg2-binary
- [x] Dual schema DDL support (SQLite AUTOINCREMENT vs PostgreSQL SERIAL)
- [x] PostgreSQL parameter binding style ($1, $2 vs ?)
- [x] RealDictCursor integration for PostgreSQL result sets
- [x] POSTGRES_URL fallback in settings for Vercel compatibility
- [x] 21 new unit tests with mock-based PostgreSQL coverage
- [x] Documentation updates (.env.example, DEPLOYMENT.md, VERCEL_DEPLOYMENT_CHECKLIST.md)
- [x] Backward compatibility verification for SQLite paths

## Out of scope

- ❌ Database migrations (Alembic) - explicitly deferred per ADR 0002
- ❌ Async database operations - using sync psycopg2-binary
- ❌ Connection pooling - deferred to Phase 4
- ❌ Graph persistence in PostgreSQL - deferred to Phase 3
- ❌ Live PostgreSQL integration tests - all tests use mocks
- ❌ SQLite → PostgreSQL data migration tools
- ❌ Multi-database support beyond SQLite and PostgreSQL
- ❌ Changes to auth logic, user model, or API endpoints

## Backward compatibility contract

All existing public interfaces preserved:

- `get_connection()` - returns connection for current database type
- `execute(query, params)` - executes SQL with appropriate parameter binding
- `fetch_one(query, params)` - returns single row as dict
- `fetch_value(query, params, default)` - returns single value with default
- `initialize_schema()` - creates user_credentials table
- Module-level constants: `DATABASE_URL`, `DATABASE_TYPE`, `DATABASE_PATH`

SQLite behavior unchanged:
- URL format: `sqlite:dev.db`, `sqlite:///:memory:`
- File path resolution for relative paths
- INTEGER PRIMARY KEY AUTOINCREMENT schema
- Question mark (?) parameter placeholders

New PostgreSQL behavior:
- URL format: `postgresql://...` or `postgres://...`
- psycopg2.connect() for connections
- SERIAL PRIMARY KEY schema
- Dollar sign ($1, $2, ...) parameter placeholders
- RealDictCursor for dict-like row results

## Behavior intentionally preserved

- Local development defaults to SQLite (`sqlite:dev.db`)
- Environment variable precedence: `DATABASE_URL` first, then `POSTGRES_URL` fallback
- Schema initialization creates `user_credentials` table on first access
- Connection is created per call (no pooling yet)
- Synchronous database operations (no async)
- Settings layer centralization for database configuration

## Known issues intentionally deferred

1. **No connection pooling** - Current implementation creates a new connection per call. This is acceptable for low-traffic deployments but should be addressed in Phase 4 with pgbouncer or connection pool libraries (issue reference: ADR 0002 Phase 4).

2. **No database migrations** - Schema changes must be applied manually. Alembic integration deferred per ADR 0002 Phase 1 scope decision.

3. **No async support** - Using sync psycopg2-binary. Async (asyncpg) could improve performance for high-concurrency scenarios but adds complexity (deferred to future optimization).

4. **Mock-only PostgreSQL tests** - No live PostgreSQL integration tests in CI. Added opt-in `test_postgres.py` for manual verification but requires `RUN_POSTGRES_TESTS=1` flag (documented in ADR 0002).

5. **No graph persistence** - Asset relationship graph remains in-memory. PostgreSQL schema for assets/relationships deferred to Phase 3.

## Files expected to change

### Core Implementation
- `api/database.py` - Database backend abstraction with PostgreSQL support
- `src/config/settings.py` - Add `postgres_url` field and fallback logic

### Tests
- `tests/unit/test_postgres_support.py` - New file with 21 PostgreSQL-specific tests
- `test_postgres.py` - Opt-in integration test for live PostgreSQL (root level)

### Documentation
- `.env.example` - PostgreSQL configuration examples and POSTGRES_URL fallback
- `DEPLOYMENT.md` - Database configuration section with PostgreSQL guidance
- `VERCEL_DEPLOYMENT_CHECKLIST.md` - PostgreSQL setup instructions

### Not Changed (Preserved)
- `api/auth.py` - Auth logic unchanged, still uses database.py public API
- `api/main.py` - No changes to endpoints or startup
- `requirements.txt` - psycopg2-binary already present (no new dependencies)
- All existing test files (1738 tests pass unchanged)

## Validation commands

```bash
# Verify psycopg2-binary is installed
pip list | grep psycopg2-binary

# Run new PostgreSQL unit tests
pytest tests/unit/test_postgres_support.py -v

# Verify all existing tests still pass
pytest tests/unit/ -v --tb=short

# Verify SQLite backward compatibility
pytest tests/unit/test_api_database.py -v

# Check that API still starts with SQLite
DATABASE_URL="sqlite:///:memory:" python -c "from api.main import app; print('API imports successfully')"

# Verify PostgreSQL URL detection (no actual connection)
python -c "from api.database import _is_postgres_url; assert _is_postgres_url('postgresql://localhost/test'); print('PostgreSQL URL detection works')"

# Optional: Run live PostgreSQL integration test (requires credentials)
# RUN_POSTGRES_TESTS=1 ASSET_GRAPH_DATABASE_URL="postgresql://user:pass@host/db" pytest test_postgres.py -v
```

## Merge criteria

- [x] PR implements one decision only (PostgreSQL support for auth database)
- [x] No unrelated cleanup has been folded in
- [x] Compatibility surface is preserved (all existing tests pass)
- [x] Production architecture assumptions remain accurate (FastAPI + Next.js)
- [x] Gradio/demo paths are not treated as production architecture
- [x] Runtime dependency source of truth remains `requirements.txt` (psycopg2-binary verified)
- [x] Any deferred issues are explicitly recorded (migrations, pooling, async, graph persistence)
- [x] All 21 new PostgreSQL tests pass
- [x] All 1738 existing unit tests pass
- [x] SQLite backward compatibility verified
- [x] Documentation updated to reflect PostgreSQL support
- [x] ADR 0002 Phase 1 requirements met

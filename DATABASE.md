# Database Integration

This project uses a dual-backend database architecture supporting **PostgreSQL** (recommended for hosted/production deployments, including Supabase PostgreSQL) and **SQLite** (preserved for local development and unit tests).

Runtime database settings are centralized in `src/config/settings.py`.

## Configuration Boundaries

The application separates database concerns into distinct environment variables:

```text
# Auth and API application database (required by api.main:app)
DATABASE_URL=sqlite:dev.db
# Production example (direct PostgreSQL / Supabase pooler):
# DATABASE_URL=postgresql://user:password@host:5432/database

# Durable graph-truth and governed relationship assertion store
ASSET_GRAPH_DATABASE_URL=sqlite:asset_graph.db
# Production example:
# ASSET_GRAPH_DATABASE_URL=postgresql://user:password@host:5432/database

# Distributed rebuild lock and coordination store (optional; defaults to ASSET_GRAPH_DATABASE_URL)
COORDINATION_DATABASE_URL=postgresql://user:password@host:5432/database
```

> **SQLite URL Gotcha:** `api/database.py` uses a custom URL-to-path resolver. Use `sqlite:dev.db` (repo-relative), `sqlite:///:memory:`, or an explicit writable absolute path (`sqlite:////abs/path/dev.db`). Avoid `sqlite:///./dev.db`, which resolves to `/dev.db`.

## Migration Authority

FastAPI startup **never** auto-creates tables. Schema initialization and upgrades are owned exclusively by the migration CLI:

```bash
python -m scripts.migrate_database
```

For full migration and ledger governance details, see [docs/runbooks/database-migration-authority.md](docs/runbooks/database-migration-authority.md) and [docs/adr/0007-database-authorization-boundary.md](docs/adr/0007-database-authorization-boundary.md).

## Programmatic Usage (SQLAlchemy 2.0)

Graph persistence uses SQLAlchemy 2.0 in `src/data/database.py` and `src/data/repository.py`:

```python
from sqlalchemy import text
from src.data.database import create_engine_from_url, create_session_factory, session_scope

engine = create_engine_from_url()
session_factory = create_session_factory(engine)

with session_scope(session_factory) as session:
    result = session.execute(text("SELECT 1")).scalar()
```

Auth/application SQLite & PostgreSQL connections are managed via `api/database.py` (with bounded `psycopg2.pool.ThreadedConnectionPool` pooling for PostgreSQL).

## Required Dependencies

Database dependencies are pinned in `requirements.txt` (and `api/requirements.txt` for Vercel):

- `sqlalchemy>=2.0.0,<2.1.0`
- `psycopg2-binary` (PostgreSQL driver)

## Managed Schema Tables

The migration ledgers manage the following core tables:

- **Auth ledger (`DATABASE_URL`):** `user_credentials`
- **Graph & GRAC v1 ledger (`ASSET_GRAPH_DATABASE_URL`):** `assets`, `asset_relationships`, `regulatory_events`, `regulatory_event_assets`, `rebuild_jobs`, `relationship_evidence`, `relationship_assertions`, `relationship_assertion_evidence`, `relationship_assertion_events`, `relationship_projection_snapshots`, `relationship_projection_edges`
- **Coordination ledger (`COORDINATION_DATABASE_URL`):** `distributed_locks`

## Smoke Testing

Verify local SQLAlchemy database connectivity with:

```bash
python scripts/test_db_module.py
```

For opt-in live Supabase connectivity testing, see [TESTING.md](TESTING.md).

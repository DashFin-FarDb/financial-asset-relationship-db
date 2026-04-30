# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## IMPORTANT: Production Architecture Declaration

**Production:** FastAPI backend (api/) + Next.js frontend (frontend/)
**Non-Production:** Gradio UI (app.py) for demos and internal testing

See `.github/AUTOMATION_SCOPE_POLICY.md` and `docs/adr/0001-production-architecture.md` for full policy details.

**All development work should prioritize the production architecture unless explicitly directed otherwise.**

## Mandatory branch/ref verification

Before reviewing, editing, or summarizing repository state, always verify:

- the current branch
- the branch, commit, or PR referenced in the request
- whether that branch has an open PR
- whether it differs from `main`

Do not assume work is merged or complete based on a clean working tree.

If branch/ref identity is unclear, stop and verify before proceeding.

## Quick orientation

This repo contains a Python "asset relationship graph" core, exposed via two UIs:

- **FastAPI + Next.js (PRODUCTION)**: FastAPI backend in `api/` (default `http://localhost:8000`) with Next.js frontend in `frontend/` (default `http://localhost:3000`).
- **Gradio UI (NON-PRODUCTION)**: `app.py` (default `http://localhost:7860`) calls the graph/visualization code directly. For demos and testing only.

## Common commands

### Python setup

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install dev tooling:

```pwsh
pip install -r requirements-dev.txt
```

(If you have GNU Make available, see “Makefile shortcuts” below.)

### Run the FastAPI backend (for the Next.js frontend - PRODUCTION)

Note: importing `api.main` imports `api.auth` and `api.database`, which **require env vars**.

Minimum env vars for startup (see `api/auth.py` and `api/database.py`):

- `DATABASE_URL` (SQLite URL; e.g. `sqlite:///./dev.db` or `sqlite:///:memory:`)
- `SECRET_KEY` (JWT signing key) — now centralized via `src/config/settings.py`
- Either pre-populated user credentials in the DB, or seed via:
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - optional: `ADMIN_EMAIL`, `ADMIN_FULL_NAME`, `ADMIN_DISABLED`

Auth settings (`SECRET_KEY`, `ADMIN_*`) are now centralized in `src/config/settings.py` (PR #1059).

Start the API:

```pwsh
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### Run the Next.js frontend (PRODUCTION)

```pwsh
cd frontend
npm install
npm run dev
```

Frontend env vars:

- `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000` in `frontend/app/lib/api.ts`; see `.env.example`)
- `NEXT_PUBLIC_MAX_NODES`, `NEXT_PUBLIC_MAX_EDGES` (optional limits; see `frontend/app/components/NetworkVisualization.tsx`)

### Run both API + frontend together (PRODUCTION)

- Windows: `run-dev.bat`
- macOS/Linux: `./run-dev.sh`

These scripts create/activate `.venv`, install Python deps, and start:

- FastAPI on `8000`
- Next.js on `3000`

They do **not** set `DATABASE_URL` / `SECRET_KEY` / admin credentials, so set those before running.

### Run the Gradio app (NON-PRODUCTION)

For demos and internal testing only. Prefer the FastAPI backend + Next.js frontend run flow above.

```pwsh
python app.py
```

### Tests

Python (pytest is configured in `pyproject.toml`):

```pwsh
pytest
```

Common single-target variants:

```pwsh
# single file
pytest tests/unit/test_api_main.py -v

# single class
pytest tests/unit/test_api_main.py::TestValidateOrigin -v

# name/substring match
pytest -k "test_assets" -v
```

Coverage:

```pwsh
pytest --cov=api --cov=src --cov-report=html
```

Frontend (Jest; see `frontend/package.json`):

```pwsh
cd frontend
npm test
```

Run a single test file:

```pwsh
cd frontend
npm test -- AssetList.test.tsx
```

Other useful frontend scripts:

```pwsh
cd frontend
npm run lint
npm run test:watch
npm run test:coverage
npm run build
```

### Lint / format / typecheck (Python)

Direct commands used by the `Makefile`:

```pwsh
flake8 src/ tests/
pylint src/
black src/ tests/ app.py
isort src/ tests/ app.py
mypy src/ --ignore-missing-imports
```

### Makefile shortcuts (if `make` is available)

```sh
make install-dev
make test
make test-fast
make lint
make format
make type-check
make check
```

### Docker (Gradio app - NON-PRODUCTION)

```sh
docker-compose up --build
```

Note: Docker configuration currently references Gradio. Aligning deployment artifacts with production architecture is deferred work per ADR 0001.

## High-level architecture

### Core domain model (Python)

- `src/models/financial_models.py`
  - Defines the canonical **domain dataclasses**: `Asset` and subclasses (`Equity`, `Bond`, `Commodity`, `Currency`), plus `RegulatoryEvent`.
  - Enums: `AssetClass`, `RegulatoryActivity`.
  - `__post_init__` performs lightweight validation (e.g., currency code format, impact score range).

### Relationship graph engine

- `src/logic/asset_graph.py`
  - Owns the in-memory state:
    - `assets: dict[str, Asset]`
    - `relationships: dict[str, list[tuple[target_id, rel_type, strength]]]` (outgoing adjacency lists)
    - `regulatory_events: list[RegulatoryEvent]`
  - `build_relationships()` clears and rebuilds relationships.
    - Adds **bidirectional** `same_sector` links.
    - Adds **directional** `corporate_link` edges from a `Bond` to its `issuer_id`.
    - Applies regulatory event impacts.
  - `calculate_metrics()` returns aggregate metrics and “top relationships” used by both UIs.

### Data sources / graph construction

- `src/data/sample_data.py`: `create_sample_database()` builds the canonical in-memory demo dataset.
- `src/data/real_data_fetcher.py`: `RealDataFetcher` can build a graph from Yahoo Finance (`yfinance`) and optionally cache to JSON.

FastAPI graph initialization in `api/main.py`:

- Default: sample data (`create_sample_database`).
- Real-data mode/caching is controlled by env vars:
  - `USE_REAL_DATA_FETCHER` (truthy string)
  - `GRAPH_CACHE_PATH`
  - `REAL_DATA_CACHE_PATH`

### Gradio UI (Non-Production)

- `app.py`
  - Builds/holds an `AssetRelationshipGraph` instance and renders tabs for visualization/metrics/schema/explorer.
  - Uses `src/visualizations/*` for Plotly figures and `src/reports/schema_report.py` for schema text.
  - **For demos and internal testing only. Not the production deployment path.**

### FastAPI backend

- `api/main.py`
  - REST endpoints used by the Next.js app:
    - `GET /api/assets`, `GET /api/assets/{asset_id}`, `GET /api/relationships`, `GET /api/metrics`, `GET /api/visualization`, etc.
  - Assembles the FastAPI application, and the active endpoint implementations currently live in this file.
  - CORS rules depend on `ENV` + `ALLOWED_ORIGINS` and include Vercel preview support.
  - Rate limiting via `slowapi`.

Configuration + persistence:

- `src/config/settings.py` — Centralized typed runtime configuration including:
  - Environment mode (`ENV`)
  - CORS configuration (`ALLOWED_ORIGINS`)
  - Auth settings (`SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_FULL_NAME`, `ADMIN_DISABLED`)
  - Graph data source settings (`GRAPH_CACHE_PATH`, `REAL_DATA_CACHE_PATH`, `USE_REAL_DATA_FETCHER`)
  - Database URLs (`DATABASE_URL`, `ASSET_GRAPH_DATABASE_URL`)
- `api/database.py` — SQLite connection management driven by `DATABASE_URL`.
- `api/auth.py` — JWT auth and user seeding; reads config from `src/config/settings.py` via `load_settings()`.

### Next.js frontend

- `frontend/app/page.tsx`: top-level tabbed UI (Visualization / Metrics / Assets) that loads data from the API.
- `frontend/app/lib/api.ts`: Axios client; base URL comes from `NEXT_PUBLIC_API_URL`.
- `frontend/app/components/*`: presentation and Plotly rendering (client-side only for Plotly).

## Repo-specific conventions to keep in mind

- **Production architecture:** FastAPI + Next.js is the declared production stack. Prioritize work on this stack. See `.github/AUTOMATION_SCOPE_POLICY.md`.
- **PR scope guardrails:** All PRs must include Primary Objective, In Scope, Out of Scope, Files Expected to Change, Validation Commands, and Merge Criteria.
- **Runtime configuration:** use `src/config/settings.py` and `load_settings()` or `get_settings()` for centralized settings. Auth settings (`SECRET_KEY`, `ADMIN_*`), CORS settings, and database URL resolution are centralized through the settings layer. Some legacy/runtime seams may still use direct `os.getenv()` access where migration has been intentionally deferred; do not assume full migration away from environment reads.
- **Pre-commit hooks:** Run `pre-commit run --files <files>` before committing. Key checks: black (120 char lines), flake8-docstrings (D101/D102/D103), ruff, mypy.
- **Plotting/visualization:** Standardized on **Plotly** (see `AI_RULES.md`).
- When changing relationship semantics or graph-derived metrics, expect to update:
  - the graph engine (`src/logic/asset_graph.py`)
  - schema/metrics reporting (`src/reports/schema_report.py`)
  - API response shapes and active endpoint behavior in `api/main.py`
  - frontend types/components (`frontend/app/types/*`, `frontend/app/components/*`)

## CI reference

CircleCI (`.circleci/config.yml`) runs:

- Python: flake8 (critical errors), pytest with coverage, safety + bandit
- Frontend: `npm run lint`, `npm run build`

## Cursor Cloud specific instructions

### Environment overview

- **Python 3.12** via system python; venv at `/workspace/.venv`
- **Node.js 20** installed via NodeSource apt repo
- **npm** is the frontend package manager (lockfile: `frontend/package-lock.json`)
- No Docker needed for local dev — SQLite is embedded

### Starting services

The FastAPI backend requires these env vars before startup: `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`. A minimal dev `.env` example:

```sh
export DATABASE_URL=sqlite:///./dev.db
export SECRET_KEY=dev-secret-key-for-local-development-only
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=AdminPass123!
export ENV=development
```

Then start services (see "Common commands" above for full details):

```sh
# Backend (port 8000)
source .venv/bin/activate
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (port 3000, in a separate terminal)
cd frontend && npm run dev
```

### Gotchas

- The `python3-venv` system package must be installed for `python3 -m venv` to produce a working virtualenv (with pip/activate). The update script handles this.
- The backend seeds the admin user on first startup when the DB is empty. If `dev.db` already exists with users, the `ADMIN_*` env vars are not re-applied.
- `pytest` needs `DATABASE_URL`, `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` set in the environment (use in-memory SQLite `sqlite:///./test.db` for tests).
- 4 pre-existing test failures exist on `main` (as of this writing): 2 in `test_schema_report_cli_integration.py`, 1 in `test_database.py`, 1 in `test_workflow_validator.py`.
- Frontend has ~65 pre-existing Jest test failures (480 of 545 pass). These are in the existing codebase, not caused by environment setup.
- The `DATABASE_URL` format the backend expects is `sqlite:///./dev.db` (3 slashes + relative path), not `sqlite:dev.db` as shown in `.env.example`.

# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## IMPORTANT: Production Architecture Declaration

**Production:** FastAPI backend (api/) + Next.js frontend (frontend/)
**Non-Production:** Gradio UI (app.py) for demos and internal testing

See `.github/AUTOMATION_SCOPE_POLICY.md` and `docs/adr/0001-production-architecture.md` for full policy details.

**All development work should prioritize the production architecture unless explicitly directed otherwise.**

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

(If you have GNU Make available, see “Makefile shortcuts” below.)

### Run the Gradio app
```pwsh
python app.py
```

### Run the FastAPI backend (for the Next.js frontend - PRODUCTION)
Note: importing `api.main` imports `api.auth` and `api.database`, which **require env vars**.

Minimum env vars (see `api/auth.py`, `api/database.py`, or use `src/config/settings.py`):
- `DATABASE_URL` (SQLite URL; e.g. `sqlite:///./dev.db` or `sqlite:///:memory:`)
- `SECRET_KEY` (JWT signing key)
- Either pre-populated user credentials in the DB, or seed via:
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`
  - optional: `ADMIN_EMAIL`, `ADMIN_FULL_NAME`, `ADMIN_DISABLED`

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

### Run the Gradio app (NON-PRODUCTION - demos/testing only)
```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
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
  - Assembles the FastAPI application with CORS, rate limiting, authentication, and routers.
  - CORS rules depend on `ENV` + `ALLOWED_ORIGINS` (via settings) and include Vercel preview support.
  - Rate limiting via `slowapi`.
- `api/routers/` — Modular REST API endpoints (assets.py, graph.py)
- `api/models.py` — Pydantic response models for API
- `api/cors_utils.py` — CORS origin validation
- `api/graph_lifecycle.py` — Graph singleton management and initialization logic

Configuration + persistence:
- `src/config/settings.py` — Centralized typed runtime configuration (replaces scattered os.getenv calls)
- `api/database.py` — SQLite connection management driven by `DATABASE_URL` (via settings).
- `api/auth.py` — JWT auth (`SECRET_KEY` required) and user seeding via `ADMIN_*` env vars.

### Next.js frontend
- `frontend/app/page.tsx`: top-level tabbed UI (Visualization / Metrics / Assets) that loads data from the API.
- `frontend/app/lib/api.ts`: Axios client; base URL comes from `NEXT_PUBLIC_API_URL`.
- `frontend/app/components/*`: presentation and Plotly rendering (client-side only for Plotly).

## Repo-specific conventions to keep in mind
- **Production architecture:** FastAPI + Next.js is the declared production stack. Prioritize work on this stack. See `.github/AUTOMATION_SCOPE_POLICY.md`.
- **PR scope guardrails:** All PRs must include Primary Objective, In Scope, Out of Scope, Files Expected to Change, Validation Commands, and Merge Criteria.
- **Runtime configuration:** Use `src/config/settings.py` and `get_settings()` instead of direct `os.getenv()` calls. Settings are cached; tests must call `get_settings.cache_clear()` when mutating env vars.
- **Plotting/visualization:** Standardized on **Plotly** (see `AI_RULES.md`).
- When changing relationship semantics or graph-derived metrics, expect to update:
  - the graph engine (`src/logic/asset_graph.py`)
  - schema/metrics reporting (`src/reports/schema_report.py`)
  - API response shapes (`api/models.py` and `api/routers/`)
  - frontend types/components (`frontend/app/types/*`, `frontend/app/components/*`)

## CI reference
CircleCI (`.circleci/config.yml`) runs:
- Python: flake8 (critical errors), pytest with coverage, safety + bandit
- Frontend: `npm run lint`, `npm run build`

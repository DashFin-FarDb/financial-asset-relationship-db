# Codebase Overview & Contributor Reference

This document summarizes the repository's architecture, conventions, and recurring patterns so new contributors and agents can navigate the project quickly. It consolidates guidance from existing documentation (README, AI rules, testing and deployment guides) and the current codebase.

## System Purpose & Entry Points
- **Financial Asset Relationship Database** provides interactive 3D views and analytics over interconnected assets spanning equities, fixed income, commodities, currencies, and regulatory events. The same core logic powers two UIs: the legacy **Gradio** app (`app.py`) and the **Next.js + FastAPI** stack (`frontend` + `api`).
- Quick development startup: run the backend and frontend explicitly (examples below). The Gradio legacy UI can be launched directly with `python app.py`.
  - FastAPI (backend): `uvicorn api.main:app --reload --port 8000`
  - Next.js (frontend): `npm run dev` (from the `frontend/` directory)
  - Legacy Gradio UI: `python app.py` (defaults to port 7860)
- The API exposes typical graph endpoints and metadata, including asset listings and visualization payloads. Notable endpoints include `/api/assets`, `/api/assets/{asset_id}`, `/api/assets/{asset_id}/relationships`, `/api/relationships`, `/api/metrics`, `/api/visualization`, and new convenience endpoints `/api/asset-classes` and `/api/sectors`.

## High-Level Architecture
- **Frontends**: Gradio pages (3D visualization, metrics, schema explorer, asset explorer) and Next.js React components. Plotly is the shared visualization layer across both UI experiences.
- **Backend API** (`api/main.py`): FastAPI app with JWT auth, CORS configuration for the web UI, and request rate limiting. Graph data is initialized once at startup using a thread-safe global accessor and optional factory hooks for tests.
- **Core Logic** (`src/logic/asset_graph.py`): Central graph object exposes relationship storage and 3D layout data consumed by visualizations.
- **Domain Models** (`src/models/financial_models.py`): Dataclasses and enums define asset classes, regulatory events, and validation rules.
- **Data Layer** (`src/data/`): Real data fetcher integrates Yahoo Finance when enabled; otherwise a sample database is used for offline exploration.
- **Visualization Layer** (`src/visualizations/`): Plotly-driven helpers for 3D graphs, metrics dashboards, 2D views, and formulaic visuals.

## Repository Layout
- **Root**: Developer documentation (README, architecture, deployment, security, testing), Makefile, Docker configs, and utility scripts.
- **`app.py`**: Gradio UI entry point with tabbed layouts that call graph, metrics, and schema helpers.
- **`api/`**: FastAPI application (lifespan-managed graph initialization, auth, rate limiting) and supporting auth/database helpers.
- **`src/`**: Python packages for analysis, data sourcing, models, reporting, visualizations, and core graph logic.
- **`frontend/`**: Next.js app (React 18, Tailwind CSS, Plotly.js, Axios) with Jest tests and TypeScript tooling.
- **`tests/`**: Pytest suite covering API behaviors, graph initialization, response models, and integration flows; frontend tests live under `frontend/__tests__`.

## Domain Model & Relationship Patterns
- **Domain Model** (authoritative definitions live in `src/models/financial_models.py`):
  - Assets are categorized by the `AssetClass` enum (e.g., equity, fixed income, commodity, currency, derivative).
  - The base `Asset` dataclass defines the required identity fields (see the dataclass for the exact names) and is validated according to the rules implemented in the model layer.
  - Specialized classes (e.g., Equity, Bond, Commodity, Currency) extend the base asset with type-specific fields.
  - Regulatory events include a scored impact field plus date/description fields (see the model for exact naming); constraints and validation behavior should be kept in sync with the model implementation and its tests.
- Relationship discovery emphasizes both **bidirectional** (e.g., same sector) and **directional** (e.g., corporate bond → equity) links with deterministic 3D layouts using fixed seeds so visual output remains stable.
- Visualization inputs are normalized: graph nodes/edges are colored by asset class, node sizes scale by importance, and metrics include relationship density and top relationships.
## Backend Service Conventions
- Graph lifecycle: global graph instance is initialized lazily and guarded by a threading lock; `set_graph_factory` enables test overrides. Real-data mode is toggled via environment flags (`USE_REAL_DATA_FETCHER`, cache path variables), falling back to sample data when disabled.
- Authentication: `/token` issues JWTs using username/password credentials; all protected routes depend on the authenticated user model. Access tokens expire after 30 minutes by default. JWT signing configuration (e.g., secret key and algorithm) is provided via environment variables/secret management and must not be committed to the repository.
- Rate limiting: SlowAPI applies declarative limits (e.g., `/token` is 5 requests/minute) and integrates with FastAPI exception handlers.
- CORS: Origins are configured for local dev and Vercel-hosted frontends; use an explicit per-environment allowlist (ideally configured via environment variables). Avoid permissive `*` origins—especially when cookies/authorization headers are involved—and review the allowlist when promoting to production.

## Data & Visualization Flow
1. **Data Ingestion**: Yahoo Finance (via `RealDataFetcher`) or static sample data create typed asset instances.
2. **Relationship Building**: Core logic links assets across sector affinity, corporate bond-equity ties, commodity exposure, currency risk, and regulatory event impact strength.
3. **Graph Construction**: Assets become nodes; relationships form weighted edges with deterministic spatial coordinates for reproducible 3D layouts.
4. **Delivery**: FastAPI serves JSON payloads for Next.js; Gradio directly renders Plotly figures; reports summarize schema and business rules.
## Coding Standards & Library Rules
- The backend is Python-first, using **dataclasses** and **enums** for data structures.
- Prefer **pandas** for tabular processing and **numpy** for numeric operations.
- **Plotly** is the only approved charting and visualization library; avoid alternatives.
- Web data acquisition standardizes on **yfinance**; do not introduce other finance APIs without approval.
- File system conventions: directories use lowercase names; files may be mixed-case. Favor small, focused modules (~100 lines) and avoid wrapping imports in try/except blocks.
- Prioritize readability, minimal complexity, and responsive UI designs. Provide user feedback through UI affordances (e.g., toasts) where applicable.

## Testing & Quality Checks
- **Backend**:
  - Run unit/integration tests with `pytest`.
  - Generate a coverage report with `pytest --cov=api --cov=src --cov-report=html`.
  - Key API tests live under `tests/` (commonly `tests/unit/`) and validate (examples):
    - CORS
    - Graph singleton behavior
    - Pydantic models
    - API endpoints
    - Error handling
- **Frontend**: From `frontend/`, run `npm test` (or `npm test -- --coverage`) after `npm install`. Jest setup lives in `jest.config.js` and `jest.setup.js`.
- **Makefile** shortcuts exist for installing dev dependencies, linting, and running checks; pre-commit hooks enforce formatting (black, isort) and linting (flake8, pylint) when enabled.

## Deployment Notes
- Local dev: run FastAPI via `uvicorn api.main:app --reload --port 8000` and Next.js via `npm run dev` in `frontend`; Gradio remains available via `python app.py`.
- Docker: use `docker-compose up --build` (or `make docker-compose-up`) for containerized runs.
- Vercel: Next.js deploys to edge; FastAPI backend can be hosted as serverless functions with HTTPS termination and environment-specific CORS settings.

## How to Extend the System
- **New asset class**: add enum value and dataclass fields in `financial_models.py`, propagate handling in graph logic, expose through API endpoints, and surface in frontend components.
- **New relationship rule**: implement detection in graph relationship builders, ensure metrics and visualizations account for the new edge type, and document it in reports/UX copy.
- **New visualization**: create Plotly-based helper, add API route or Gradio binding, and connect to Next.js pages/components.
- **New API endpoint**: add FastAPI route with pydantic schemas, integrate authentication/rate limiting, and update the frontend API client plus tests.

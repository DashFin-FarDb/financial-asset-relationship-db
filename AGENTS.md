# AGENTS.md

This file is hosted and maintained by Dosu (dosu.dev). It provides guidance to AI coding agents when working with code in this repository.

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

This repository contains a Python "asset relationship graph" core, exposed via two UIs:

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
make format-check
make type-check
make check
make pre-commit         # install pre-commit hooks
make pre-commit-run     # run pre-commit hooks on all files
make run                # runs `python app.py` (Gradio - non-production)
make clean              # remove caches, coverage, build artifacts
```

Docker targets (Gradio image - non-production): `make docker-build`, `make docker-run`,
`make docker-stop`, `make docker-clean`, `make docker-compose-up`, `make docker-compose-down`,
`make docker-compose-logs`, `make docker-shell`, `make docker-dev`.

Run `make help` for the full target list with descriptions.

### Utility scripts (in `scripts/`)

- `scripts/check_hosted_readiness.py` — Smoke-check a hosted deployment's
  liveness/readiness endpoints. Usage:

  ```pwsh
  python scripts/check_hosted_readiness.py <base_url> [--timeout SECONDS]
  ```

- `scripts/validate_manifest.py` — Validate `.elastic-copilot/memory/systemManifest.md`
  for duplicate level-2 headings (markdownlint MD024).
- `scripts/deduplicate_manifest.py` — Deduplicate level-2 sections in `.elastic-copilot/memory/systemManifest.md`.
  Note: the script currently contains a partial implementation; complete it before relying on this command.

### Docker (Gradio app - NON-PRODUCTION)

```sh
docker-compose up --build
```

Note: Docker configuration currently references Gradio. Aligning deployment artifacts with production architecture is deferred work per ADR 0001.

### Hosted readiness smoke check

`scripts/check_hosted_readiness.py` performs a bounded liveness/readiness probe against a hosted deployment. It is wired into the manual GitHub Actions workflow `.github/workflows/hosted-readiness.yml` (trigger via `workflow_dispatch`).

Inputs/env:

- `base_url` workflow input or `HOSTED_READINESS_BASE_URL` repository secret (the workflow skips when neither is set)
- `timeout` workflow input (seconds; defaults to `10`)

Run locally:

```pwsh
python scripts/check_hosted_readiness.py <base_url> --timeout 10
```

## High-level architecture

### Core domain model (Python)

- `src/models/financial_models.py`
  - Defines the canonical **domain dataclasses**: `Asset` and subclasses (`Equity`, `Bond`, `Commodity`, `Currency`), plus `RegulatoryEvent`.
  - Enums: `AssetClass`, `RegulatoryActivity`.
  - `__post_init__` performs lightweight validation (e.g., currency code format, impact score range).

### Reconciliation / rebuild control plane

- `src/logic/reconciliation_engine.py` — Purely functional engine that consumes
  Desired State + Observed State, computes drift, and generates execution-agnostic
  Reconciliation Plans (no side effects).
- `src/logic/rebuild_failure_detection.py` — Drift/inconsistency detection
  (orphaned-running, zombie executor, crash suspicion, stale ownership).
- `src/logic/rebuild_recovery.py` — Maps detected drift to deterministic recovery
  actions (RESUME, etc.).
- `src/logic/rebuild_drift_evaluator.py` — Evaluator adapter between drift
  detection and the reconciliation engine.
- `src/logic/recovery_gate.py` — Recovery gate hardening for rebuild flows.
- See `docs/reconciliation-discovery-map.md` for the mapping between the
  pre-existing implicit reconciliation primitives and the formal engine.

### Stage 5C Safety Constraints

When modifying or implementing rebuild jobs and processing loops, the following constraints must be strictly adhered to:

- **State Mutations:** Any state mutation on rebuild jobs must validate the current `execution_id` to ensure execution safety and avoid stale mutations.
- **Cancellation Check:** Any new or modified processing loop must periodically check the `cancel_event` (such as `threading.Event` or equivalent) and raise `RebuildCancelledError` if it is set.

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

## Repository-specific conventions to keep in mind

- **Production architecture:** FastAPI + Next.js is the declared production stack. Prioritize work on this stack. See `.github/AUTOMATION_SCOPE_POLICY.md`.
- **Enterprise Readiness:** The system is transitioning to an enterprise-grade posture. Refer to `docs/enterprise-readiness-index.md` for the audit, roadmap, and PR plan. Ensure work aligns with these plans, particularly the rule that **durable persistence is the gating dependency** for restart, promotion, and DR. SQLite compatibility must be preserved.
- **PR scope guardrails:** All PRs must include Primary Objective, In Scope, Out of Scope, Files Expected to Change, Validation Commands, and Merge Criteria.
- **High-risk work:** Database, auth, deployment, CI, security scanner config, and persistence changes require low-autonomy contracts. See "High-risk change control" in `.github/AI_AGENT_GUARDRAILS.md`.
- **Runtime configuration:** use `src/config/settings.py` and `load_settings()` or
  `get_settings()` for centralized settings. Auth settings (`SECRET_KEY`,
  `ADMIN_*`), CORS settings, and database URL resolution are centralized through
  the settings layer. Some legacy/runtime seams may still use direct
  `os.getenv()` access where migration has been intentionally deferred; do not
  assume full migration away from environment reads.
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

GitHub Actions (`.github/workflows/`) include, among others:

- `ci.yml` — primary CI pipeline
- `hosted-readiness.yml` — manual (`workflow_dispatch`) hosted deployment smoke check (see "Hosted readiness smoke check" above)
- A range of security/scanner workflows (CodeQL, Bandit, Bearer, Semgrep, Snyk, Trivy, etc.)

## Cursor Cloud specific instructions

Environment is Linux with Python 3.12 and Node 22. In Cursor Cloud, dependencies (Python `.venv` + `frontend/node_modules`) are refreshed automatically by the platform-managed startup/update process, so you normally only need to start services and run checks. Standard commands live in the "Common commands" section above and in `run-dev.sh`; the notes below only cover non-obvious cloud gotchas.

- **`python` is not on PATH — only `python3`.** `run-dev.sh` and the docs invoke bare `python`, which fails here. Activate the project venv first (`source .venv/bin/activate`, which provides `python`) or substitute `python3`.
- **SQLite `DATABASE_URL` gotcha (backend won't start otherwise):** this
  repository uses a **custom URL-to-path resolver** in `api/database.py`
  (`_resolve_file_path`), *not* SQLAlchemy's URL handling. Under that resolver,
  the SQLAlchemy-style `sqlite:///./dev.db` used in the "Common commands" section
  resolves to the absolute path `/dev.db` (unwritable ->
  `sqlite3.OperationalError: unable to open database file`); likewise
  `.env.example`'s `sqlite:///./asset_graph.db` resolves to `/asset_graph.db`.
  When starting the backend directly, prefer either an explicit writable absolute
  path (`DATABASE_URL=sqlite:////workspace/dev.db`), the rootless form
  `DATABASE_URL=sqlite:dev.db` (resolves relative to `$PWD`, i.e.
  `/workspace/dev.db` when run from the repository root, which is what
  `run-dev.sh` documents), or `DATABASE_URL=sqlite:///:memory:`.
- **Backend startup env vars:** importing `api.main` needs `DATABASE_URL` and `SECRET_KEY`; if the auth DB is empty (typical for new SQLite files), also set `ADMIN_USERNAME` + `ADMIN_PASSWORD` to seed the first user (otherwise pre-populate the DB). Example working start:
  `DATABASE_URL=sqlite:dev.db SECRET_KEY=$(openssl rand -hex 32) ADMIN_USERNAME=admin ADMIN_PASSWORD=$(openssl rand -base64 24) python3 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`
- **Frontend → backend wiring:** start the frontend with `NEXT_PUBLIC_API_URL=http://localhost:8000` (defaults to that anyway). Public dashboard routes (visualization/metrics/assets) need no login; only `/token`, `/api/users/me`, and rebuild-admin endpoints require JWT.
- **Backend serves sample data by default** (19 assets / 73 relationships); no external DB or `USE_REAL_DATA_FETCHER` needed for local E2E.
- **`python3-venv` system package** is required to create the venv and is installed during environment setup (not part of the update script).
- **Known pre-existing test failures (not environment issues):**
  `tests/unit/test_workflow_yaml_files.py` fails on `codeql.yml` (via
  `pytest.fail`) because `.github/workflows/codeql.yml` does not exist in the
  repository. The rest of the suite passes (~7777 passed).

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
- **High-risk work:** Database, auth, deployment, CI, security scanner config, and persistence changes require low-autonomy contracts. See "High-risk change control" in `.github/AI_AGENT_GUARDRAILS.md`.
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

GitHub Actions (`.github/workflows/`) include, among others:

- `ci.yml` — primary CI pipeline
- `hosted-readiness.yml` — manual (`workflow_dispatch`) hosted deployment smoke check (see "Hosted readiness smoke check" above)
- A range of security/scanner workflows (CodeQL, Bandit, Bearer, Semgrep, Snyk, Trivy, etc.)

<!-- snipara:workflow AGENTS.md:start -->
## Snipara Context Workflow

This workspace is bound to Snipara project `financial-asset-relationship-db` for Gemini. Agents should use Snipara automatically for project-specific context, decisions, and workflow state.

- Hosted MCP endpoint: `https://api.snipara.com/mcp/financial-asset-relationship-db`
- At the start of substantial work, validate the hosted MCP surface with a tool-oriented call, then use `snipara_recall` and a targeted `snipara_context_query` before falling back to local search.
- Do not treat empty MCP resources/templates as an outage. If the tool surface looks incomplete, call `snipara_help(list_all=true)` and compare exact tool names.
- Use `snipara_context_query` for docs, business context, architecture notes, runbooks, and source truth. Use `snipara_get_chunk` for exact cited sections when references are returned.
- For coding work, choose LITE or FULL before editing. Use FULL managed workflow for multi-file, risky, release/deploy, architectural, compaction-prone, or future-maintainer-sensitive work.
- When a visible multi-phase plan exists, keep the machine plan in JSON and run `snipara-companion workflow start --goal "<goal>" --plan-file <plan_json_file>`. Use `workflow phase-start` / `workflow phase-commit` per phase, and after `workflow resume` rerun `workflow phase-start` before editing again.
- Run `snipara_code_impact` before risky multi-file changes, PR reviews, routes, services, jobs, auth, billing, deployment, schema, migrations, or explicit "what is missing" assessments.
- Use local file reads, `rg`, git commands, and tests for exact edits and current working-tree state.
- Use Snipara Sandbox only when sandboxed execution, repeatable validation, or isolated transformations materially help. For runtime-bound phases, capture compact rehydratable state with `workflow runtime-checkpoint <phase_id> --summary "<state>" --rehydrate-file <state.json>`. Then `workflow resume` restores workflow/memory continuity plus the recorded Sandbox binding and prints a reattach or rehydrate plan. It does not snapshot or exactly restore a live Snipara Sandbox / REPL process.
- End substantial work with `snipara_end_of_task_commit` when available. For managed workflows, commit each phase with `snipara-companion workflow phase-commit` and close with `snipara-companion final-commit`.
- Store only durable decisions, learnings, preferences, and workflow context. Never store secrets, tokens, raw logs, one-off command output, or unreviewed guesses.
<!-- snipara:workflow AGENTS.md:end -->

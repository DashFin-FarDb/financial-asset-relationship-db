<!-- .github/copilot-instructions.md - guidance for AI coding agents -->

# Copilot instructions — DB1 Financial Asset Relationship App

## IMPORTANT: Production Architecture Declaration

**Production:** FastAPI backend + Next.js frontend
**Non-Production:** Gradio UI (`app.py`) for demos and internal testing

See [AUTOMATION_SCOPE_POLICY.md](AUTOMATION_SCOPE_POLICY.md) and [docs/adr/0001-production-architecture.md](../docs/adr/0001-production-architecture.md) for full policy details.

**All development work should prioritize the production architecture unless explicitly directed otherwise.**

Purpose

- Short, actionable guidance to help AI coding agents be productive in this repo.

## Mandatory branch/ref verification

Before reviewing, editing, or summarizing work, first verify:

- which branch you are on
- which branch, commit, or PR the user is referring to
- whether that branch has an open PR
- whether it differs from `main`

Do not infer merge status, PR status, or completion from local working-tree state alone.

If branch or ref identity is uncertain, stop and verify before proceeding.

Quick start (what to run)

**Production path (recommended for development):**

Note: importing `api.main` pulls in `api.auth` and `api.database`, which require environment variables.

Minimum env vars for startup (see `api/auth.py` and `api/database.py`):

- `DATABASE_URL`
- `SECRET_KEY`

Typical local steps (PowerShell):

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Ensure required env vars are set before starting the API
python -m uvicorn api.main:app --reload --port 8000
# In separate terminal:
cd frontend
npm install
npm run dev
```

**Non-production path (demos/testing only):**

- Entry point: `app.py` (Gradio UI)

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Key files & responsibilities

**Production stack:**

- `api/main.py` — FastAPI application entry point; active endpoint implementations currently live here
- `frontend/app/page.tsx` — Next.js main UI page
- `frontend/app/lib/api.ts` — API client for backend communication
- `frontend/app/components/` — React components for UI
- `src/config/settings.py` — Centralized typed runtime configuration (partial coverage)

**Core domain logic (shared by both UIs):**

- `src/logic/asset_graph.py` — Core graph model and algorithms
- `src/models/financial_models.py` — Domain dataclasses and enums
- `src/data/sample_data.py` — Canonical in-memory dataset
- `src/visualizations/` — Plotly figure generation

**Non-production (Gradio UI - demos/testing only):**

- `app.py` — Gradio interface wiring and UI
- `src/reports/schema_report.py` — schema and rules reporting

**Dependencies:**

- `requirements.txt` — Python dependencies
- `package.json` — Frontend dependencies

Project conventions and concrete patterns

- Domain model: use Python `@dataclass` objects in `financial_models.py`
- Relationship representation: `Dict[str, List[Tuple[target_id, rel_type, strength]]]`
- Regulatory event impact: -1 to +1 scale
- Visualization positions: deterministic via `np.random.seed(42)`

Integration & external deps

- Production UI: Next.js + React frontend with Plotly
- Non-production UI: Gradio
- Runtime configuration: use `load_settings()` or `get_settings()` from `src/config/settings.py` for centralized settings. Auth settings (`SECRET_KEY`, `ADMIN_*`) and CORS settings are centralized. Some legacy/runtime seams still use direct `os.getenv()` access where migration has been deferred; do not assume full migration away from environment reads.

Editing guidelines for AI agents

- Follow PR scope guardrails in `AUTOMATION_SCOPE_POLICY.md`
- Prioritize production architecture
- When changing API behavior: update `api/main.py` and corresponding frontend client/types
- When adding env vars: add to settings only if part of an intentional migration
- Keep changes minimal per PR

Examples

- Relationship: `AssetRelationshipGraph.add_relationship(...)`
- Deterministic layout: `np.random.seed(42)`

## PR Management Agent

Configured in `.github/copilot-pr-agent.md`

- Monitors PRs
- Implements targeted fixes
- Maintains quality standards

### Agent Triggers

- `@copilot fix this`
- `@copilot address review`
- `@copilot update tests`
- `@copilot check ci`

-- End of instructions

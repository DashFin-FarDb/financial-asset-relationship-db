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

- Entry point: FastAPI backend + Next.js frontend
- Typical local steps (PowerShell):

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --port 8000
# In separate terminal:
cd frontend
npm install
npm run dev
```

**Non-production path (demos/testing only):**

- Entry point: `app.py` (Gradio UI)
- Typical local steps (PowerShell):

```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Key files & responsibilities

**Production stack:**

- `api/main.py` — FastAPI application entry point with CORS, rate limiting, and routers
- `api/routers/` — REST API endpoint modules (assets, graph)
- `api/models.py` — Pydantic response models for API
- `api/cors_utils.py` — CORS origin validation
- `api/graph_lifecycle.py` — Graph singleton management
- `frontend/app/page.tsx` — Next.js main UI page
- `frontend/app/lib/api.ts` — API client for backend communication
- `frontend/app/components/` — React components for UI
- `src/config/settings.py` — Centralized typed runtime configuration

**Core domain logic (shared by both UIs):**

- `src/logic/asset_graph.py` — Core graph model and algorithms. Main API: `AssetRelationshipGraph.add_asset`, `add_relationship`, `add_regulatory_event`, `build_relationships`, `calculate_metrics`, `get_3d_visualization_data`.
- `src/models/financial_models.py` — Domain dataclasses (Asset, Equity, Bond, Commodity, Currency, RegulatoryEvent) and enums (AssetClass, RegulatoryActivity).
- `src/data/sample_data.py` — `create_sample_database()` provides a canonical in-memory dataset.
- `src/visualizations/` — Plotly figure generation

**Non-production (Gradio UI - demos/testing only):**

- `app.py` — Gradio interface wiring, event handlers, and UI tabs (3D graph, metrics, schema, explorer).
- `src/reports/schema_report.py` — derives human-readable schema & rules from `AssetRelationshipGraph.calculate_metrics()`.

**Dependencies:**

- `requirements.txt` — Python dependencies (FastAPI, Gradio, Plotly, NumPy, Pydantic)
- `package.json` — Frontend dependencies (Next.js, React, TypeScript)

Project conventions and concrete patterns

- Domain model: use Python `@dataclass` objects in `financial_models.py`. New asset types should extend `Asset` and follow the same fields.
- Relationship representation: `relationships: Dict[str, List[Tuple[target_id, rel_type, strength]]]` where `strength` is normalized to 0.0–1.0.
- Regulatory event impact: `RegulatoryEvent.impact_score` is on a -1 to +1 scale. Events add directional relations via `add_regulatory_event`.
- Relationship discovery: implement new relationship rules inside `_find_relationships` in `AssetRelationshipGraph`; return `(rel_type, strength, bidirectional)` tuples.
- Visualization positions: `get_3d_visualization_data` persists positions and seeds NumPy RNG with `42` for deterministic layouts — preserve this behavior when modifying visualization code.
- Directionality: some relations are bidirectional (e.g., `same_sector`, `income_comparison`) and others are directional (`corporate_bond_to_equity`). Follow existing naming when adding new types.

Integration & external deps

- **Production UI:** Next.js + React frontend with Plotly for visualizations. FastAPI backend with Pydantic validation.
- **Non-production UI:** Gradio for demos/testing.
- **Runtime configuration:** Use `src/config/settings.py` and `get_settings()` instead of direct `os.getenv()` calls.
- **Graph initialization:** Boots with in-memory sample dataset (`create_sample_database`) by default. Real data fetcher available via environment configuration.

Editing guidelines for AI agents (concrete steps)

- **ALL PRs must follow scope guardrails:** Include Primary Objective, In Scope, Out of Scope, Files Expected to Change, Validation Commands, and Merge Criteria. See [AUTOMATION_SCOPE_POLICY.md](AUTOMATION_SCOPE_POLICY.md).
- **Prioritize production architecture:** Changes to FastAPI + Next.js stack take precedence over Gradio UI changes.
- When changing relationship logic:

1.  Modify `_find_relationships` in `src/logic/asset_graph.py` and add unit tests mirroring sample assets in `src/data/sample_data.py`.
2.  Update API response models in `api/models.py` if metrics or data shapes change.
3.  Update frontend TypeScript types in `frontend/app/types/` if API responses change.
4.  If adding a new asset field, update the dataclass in `src/models/financial_models.py` and all sample data in `src/data/sample_data.py`.

- When adding environment variables:

1.  Add them to `src/config/settings.py` Settings model.
2.  Use `get_settings()` to access them, never direct `os.getenv()` calls.
3.  In tests that modify env vars, call `get_settings.cache_clear()` before reading settings.

- When changing API endpoints: Update both `api/routers/` modules and corresponding frontend API client calls in `frontend/app/lib/api.ts`.
- Keep changes minimal per PR: small, focused commits (one logical change per PR).

Examples to reference in code

- Add a relationship: see `AssetRelationshipGraph.add_relationship(source_id, target_id, rel_type, strength, bidirectional=False)`.
- Create deterministic positions: `np.random.seed(42)` in `get_3d_visualization_data`.
- Create sample DB: `from src.data.sample_data import create_sample_database` (used in `app.py` Gradio `State`).

## PR Management Agent

This repository includes an automated PR management agent configured in `.github/copilot-pr-agent.md`. The agent:

- **Monitors PRs**: Automatically detects review comments and feedback
- **Implements Changes**: Makes targeted fixes based on reviewer feedback
- **Manages Workflow**: Handles commits, testing, and re-review requests
- **Maintains Quality**: Ensures all changes meet code standards

### Agent Triggers

- `@copilot fix this` - Implement suggested fix
- `@copilot address review` - Handle all review comments
- `@copilot update tests` - Add/update test coverage
- `@copilot check ci` - Investigate CI failures

The agent configuration is in `.github/pr-agent-config.yml` and includes safety limits, quality standards, and automated workflows.
If anything here is unclear or you'd like me to merge content from a specific file (or prefer different run commands), tell me which parts to adjust and I will iterate.

-- End of instructions

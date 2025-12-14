<!-- .github/copilot-instructions.md - guidance for AI coding agents -->
# Copilot instructions — DB1 Financial Asset Relationship App

Purpose
- Short, actionable guidance to help AI coding agents be productive in this repo.

Quick start (what to run)
- Entry point: `app.py` (Gradio UI). Launch locally with a Python environment; Gradio opens a browser UI.
- Typical local steps (PowerShell):
```pwsh
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python app.py
```
- There is also a `package.json` — check `package.json` for node scripts before running `npm install` / `npm run <script>`.

Key files & responsibilities
- `app.py` — Gradio interface wiring, event handlers, and UI tabs (3D graph, metrics, schema, explorer).
- `src/logic/asset_graph.py` — Core graph model and algorithms. Main API: `AssetRelationshipGraph.add_asset`, `add_relationship`, `add_regulatory_event`, `build_relationships`, `calculate_metrics`, `get_3d_visualization_data`.
- `src/models/financial_models.py` — Domain dataclasses (Asset, Equity, Bond, Commodity, Currency, RegulatoryEvent) and enums (AssetClass, RegulatoryActivity).
- `src/data/sample_data.py` — `create_sample_database()` provides a canonical in-memory dataset used by the UI.
- `src/visualizations/graph_visuals.py` and `src/visualizations/metric_visuals.py` — produce Plotly figures and metric outputs consumed by Gradio.
- `src/reports/schema_report.py` — derives human-readable schema & rules from `AssetRelationshipGraph.calculate_metrics()`.
- `requirements.txt` — Python dependencies (Gradio, Plotly, NumPy).

Project conventions and concrete patterns
- Domain model: use Python `@dataclass` objects in `financial_models.py`. New asset types should extend `Asset` and follow the same fields.
- Relationship representation: `relationships: Dict[str, List[Tuple[target_id, rel_type, strength]]]` where `strength` is normalized to 0.0–1.0.
- Regulatory event impact: `RegulatoryEvent.impact_score` is on a -1 to +1 scale. Events add directional relations via `add_regulatory_event`.
- Relationship discovery: implement new relationship rules inside `_find_relationships` in `AssetRelationshipGraph`; return `(rel_type, strength, bidirectional)` tuples.
- Visualization positions: `get_3d_visualization_data` persists positions and seeds NumPy RNG with `42` for deterministic layouts — preserve this behavior when modifying visualization code.
- Directionality: some relations are bidirectional (e.g., `same_sector`, `income_comparison`) and others are directional (`corporate_bond_to_equity`). Follow existing naming when adding new types.

Integration & external deps
- UI: Gradio (see imports in `app.py`) and Plotly for visuals (`graph_visuals.py`). Expect these dependencies in the Python environment.
- The app currently boots with an in-memory sample dataset (`create_sample_database`) — for DB persistence, implement new storage layer.
- Node tooling: `package.json` present for optional scripts, but core app is Python-only.

Editing guidelines for AI agents (concrete steps)
- When changing relationship logic:
 1. Modify `_find_relationships` in `src/logic/asset_graph.py` and add unit tests mirroring sample assets in `src/data/sample_data.py`.
 2. Update `schema_report.py` if the set of relationship types or metrics changes so the report stays consistent.
 3. If adding a new asset field, update the dataclass in `src/models/financial_models.py` and all sample data in `src/data/sample_data.py`.
- When changing visualization output shapes, update `visualize_3d_graph` (Plotly traces) and the Gradio outputs in `app.py` to match the new return types.
- Keep changes minimal per PR: small, focused commits (one logical change per PR). Include a short note in PR description about any changes that touch visualization layout, relationship semantics, or persistence.

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

## Architectural Alignment

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

This PR contains both repository-state corrections and functional alignment/clarification of graph density and pagination contracts across the API and frontend components.

## Primary Objective

1. Remove the accidental gitlink at `financial-asset-relationship-db` to normalize the repository index layout.
2. Align and normalize network density semantics and API pagination contracts across the FastAPI backend and Next.js frontend.

## Scope

### In Scope

- **Repository Layout**: Remove the nested gitlink entry (`mode 160000`) for `financial-asset-relationship-db`.
- **API Contracts**:
  - Add a new `/api/graph/metrics` endpoint in `api/routers/metrics.py`.
  - Add `hasMore` field to asset pagination response payloads.
  - Normalize `network_density` field representation in `VisualizationDataResponse` and `MetricsResponse` (calculating it consistently via `collect_participating_asset_ids()`).
- **Frontend Components & Tests**:
  - Update `MetricsDashboard.tsx` to handle `network_density` formatted as a percentage.
  - Fix duplicate word/prefix typos (e.g., `network network_density` -> `network_density`) in frontend tests (`MetricsDashboard.test.tsx` and `test-utils.test.ts`).
- **Documentation**:
  - Update `docs/tech_spec.md` and `tech_spec.md` to remove duplicated fields and references.
  - Escape type hints like `[Dict[str, int]]` in Markdown files to fix undefined reference link warnings.

### Out of Scope

- Functional changes to authentication mechanisms or database schema migrations.
- Reworking core React state hooks or modifying Next.js routing patterns.

### Files Expected to Change

- `financial-asset-relationship-db` (gitlink entry removed)
- `api/app_factory.py`, `api/main.py`, `api/api_models.py`
- `api/routers/assets.py`, `api/routers/metrics.py`, `api/routers/visualization.py`
- `src/logic/asset_graph.py`, `src/reports/schema_report.py`, `src/reports/schema_report_generator.py`
- `frontend/app/lib/api.ts`, `frontend/app/lib/assetHelpers.ts`, `frontend/app/types/api.ts`
- `frontend/app/components/MetricsDashboard.tsx`
- `frontend/__tests__/` (various test files under the React test suites)
- `tests/` (unit and integration tests for backend endpoints and report generation)
- `docs/tech_spec.md`, `tech_spec.md`

## Validation Commands

```bash
# Verify no mode-160000 gitlinks remain
git ls-files --stage | awk '$1==160000 {print}'

# Run all backend Python tests
pytest

# Run all frontend Jest tests
cd frontend && npm test
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [x] All backend and frontend unit/integration tests pass cleanly
- [x] Changes align with production architecture (FastAPI + Next.js)

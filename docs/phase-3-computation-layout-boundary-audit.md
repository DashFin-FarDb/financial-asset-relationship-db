# Phase 3 Computation/Layout Boundary Audit

## Outcome

The computation boundary is mostly isolated, but not ideal.

The graph engine is the authoritative source for relationship construction and the richest network metric set. The production API then recomputes or derives a small set of endpoint-specific values, and the frontend performs one density formatting transform that conflicts with the backend contract.

Minimal follow-up PRs should address these boundary blurs:

1. Move API `asset_classes`, `avg_degree`, and `max_degree` computation behind the graph metric contract or document them as API-only presentation metrics.
2. Resolve density semantics so `network_density`/`relationship_density` are either both 0-100 percentages end-to-end or both 0-1 fractions end-to-end.
3. Tighten visualization and asset list contracts so layout fields, node sizing, frontend limits, and pagination assumptions are explicit.

## 1. Computation map

### Core graph engine

`src/logic/asset_graph.py` is the main computation source.

| Area | Evidence | Classification |
| --- | --- | --- |
| Relationship construction | `build_relationships()` clears relationships, adds bidirectional `same_sector` links at `0.7`, directional `corporate_link` links at `0.9`, then applies regulatory event impacts. | Source computation |
| Regulatory impacts | `_apply_event_impacts()` creates `event_impact` links with `abs(event.impact_score)`. | Source computation |
| Metrics contract | `calculate_metrics()` returns totals, average strength, `relationship_density`, distributions, top relationships, event counts, event norm, and quality score. | Source aggregation |
| Relationship summary | `_summarize_relationships()` counts relationships by type, computes average strength, and selects the top 10 by strength. | Aggregation and selection |
| Quality score | `_quality_metrics()` clamps average strength, normalizes event count, and combines fixed weights `0.7` and `0.3`. | Derived computation |
| Relationship density | `_relationship_density()` returns a 0-100 percentage of possible directed edges. | Derived computation |
| Asset class distribution | `_asset_class_distribution()` counts stored assets by `asset_class.value`. | Aggregation |

### Production API metrics

`api/routers/metrics.py` calls `g.calculate_metrics()`, then recomputes values at the API boundary:

- `asset_classes` is recalculated from `g.assets` even though the graph already returns `asset_class_distribution`.
- `avg_degree` and `max_degree` are calculated from outgoing adjacency lengths.
- `network_density` and `relationship_density` are both populated from the graph's `relationship_density`.

Classification: boundary-blurring aggregation. This is not presentation-only, because the router creates numeric metrics that are visible in the API contract.

### Production API visualization

`api/routers/visualization.py` computes layout-oriented values:

- `_calculate_node_degrees()` derives outgoing degree per source.
- `_compute_fibonacci_position()` computes node coordinates.
- `_build_visualization_nodes()` derives color and size, where `size = max(5, min(20, 5 + degree * 2))`.
- `_build_visualization_edges()` passes relationship strength through unchanged.

Classification: presentation/layout computation. This should remain outside financial metric computation, but the contract should say these fields are visualization encodings, not graph metrics.

### Relationship serialization

`api/routers/relationships.py` maps stored graph tuples to `RelationshipResponse` without recomputing strength, type, source, or target.

Classification: presentation serialization.

## 2. Presentation map

### FastAPI presentation layer

| Surface | Behavior | Classification |
| --- | --- | --- |
| `api/api_models.py` | Defines `RelationshipResponse`, `MetricsResponse`, and `VisualizationDataResponse`. Visualization nodes and edges are loose `dict[str, Any]`. | Contract |
| `api/routers/assets.py` | Filters assets by class/sector and serializes assets. It does not accept `page` or `per_page`. | Response shaping |
| `api/routers/relationships.py` | Serializes graph relationships as response models. | Display-only serialization |
| `api/routers/metrics.py` | Recomputes asset class counts and degree stats, aliases graph density into two fields. | Boundary-blurring computation |
| `api/routers/visualization.py` | Computes node layout, node size, node colors, and edge payloads. | Presentation/layout computation |

### Next.js presentation layer

| Surface | Behavior | Classification |
| --- | --- | --- |
| `frontend/app/components/MetricsDashboard.tsx` | Displays totals, degree values, asset class counts, and formats `network_density` as `(value * 100).toFixed(2)%`. | Display formatting with semantic drift |
| `frontend/app/components/NetworkVisualization.tsx` | Uses API-provided node coordinates, size, and color; maps edge strength into Plotly opacity and width; filters edges whose endpoint nodes are absent; enforces `MAX_NODES` and `MAX_EDGES`. | Display encoding and client render guard |
| `frontend/app/components/AssetList.tsx` | Formats prices and market cap; reads page/per-page UI state. | Display formatting plus contract drift |
| `frontend/app/lib/assetHelpers.ts` | Sends `page` and `per_page` to `api.getAssets()` and supports a paginated response shape, while the API returns a plain list. | Boundary-blurring client assumption |
| `frontend/app/types/api.ts` | Mirrors API response shapes in TypeScript; `relationship_density` is optional. | Client contract mirror |

## 3. Boundary classification

### Is computation isolated from presentation?

No, not completely.

The graph engine owns the core financial relationship and network metrics, but the API metrics router still computes public metric fields. The visualization router also computes layout encodings, which is acceptable if explicitly treated as presentation, but it is not strongly modeled in the API contract.

### Clear boundaries

- Relationship strengths and relationship types originate in `src/logic/asset_graph.py`.
- Rich network metrics originate in `AssetRelationshipGraph.calculate_metrics()`.
- Relationship endpoints pass graph relationship tuples through without altering them.
- Schema report generation collects graph metrics and renders markdown without recalculating them.

### Blurred or violating boundaries

1. `api/routers/metrics.py` recomputes `asset_classes`, `avg_degree`, and `max_degree`.
   - Risk: graph metrics and API metrics can drift because only part of the response is sourced from `calculate_metrics()`. For example, the metrics router's degree calculation is currently inconsistent with the visualization router's logic.
   - Minimal PR: either extend `calculate_metrics()` to include these fields or move them into a named API presentation section with tests that document the distinction.

2. Density semantics conflict across backend and frontend.
   - Graph docs and API tests treat density as 0-100.
   - Frontend component docs, mocks, and tests treat `network_density` as 0-1 and multiply by 100.
   - Minimal PR: choose one unit, update `MetricsResponse`, `frontend/app/types/api.ts`, `MetricsDashboard`, and tests together.

3. Visualization fields are loosely contracted.
   - Backend response model allows arbitrary node/edge dicts.
   - Frontend assumes strict node and edge fields.
   - Minimal PR: introduce explicit Pydantic node/edge models and align TypeScript types/tests.

4. Asset pagination assumptions are outside the API contract.
   - Frontend sends `page` and `per_page` and supports paginated responses.
   - Backend `GET /api/assets` only accepts `asset_class` and `sector` and returns a list.
   - Minimal PR: either add server pagination or remove pagination-shaped client assumptions.

## 4. Test coverage

### Covered

- API response models are covered in `tests/unit/test_api_main.py`.
- Metrics endpoint behavior is covered for populated, empty, one-asset, and multi-asset graphs.
- API tests assert `network_density` and `relationship_density` both exist and are equal.
- Integration tests compare API metrics asset counts and asset class counts against `/api/assets`.
- Relationship endpoint tests verify list shapes and strength bounds.
- Visualization endpoint tests verify node/edge structures, coordinate precision, and workflow consistency.
- Frontend component tests cover dashboard formatting and visualization render guards.
- Frontend API client tests cover metrics, relationships, and visualization calls with mocked payloads.

### Gaps

- `tests/unit/test_asset_graph.py` and `tests/unit/test_asset_graph_simplified.py` focus on initialization, relationship insertion, and legacy enhanced visualization; they do not directly test `build_relationships()` or `calculate_metrics()` as the core metric contract.
- `build_relationships()` coverage is mostly indirect through fixtures and formulaic analysis tests.
- There is no single contract test proving `GET /api/metrics` is a strict projection of `AssetRelationshipGraph.calculate_metrics()`.
- Frontend tests encode 0-1 density assumptions while backend tests encode 0-100 density assumptions.
- Visualization response models are loose on the backend, so frontend strictness is not protected by a shared or explicit backend schema.
- Relationship list endpoints are tested in the API client and backend, but the production home UI does not consume them directly.

## 5. Contract definition

### Current observed contract

Core graph contract:

- `relationships`: outgoing adjacency lists of `(target_id, relationship_type, strength)`.
- `build_relationships()`: owns `same_sector`, `corporate_link`, and `event_impact` creation.
- `calculate_metrics()`: owns total assets, total relationships, average relationship strength, relationship density as 0-100, relationship distribution, asset class distribution, top relationships, regulatory event count, regulatory event norm, and quality score.

API metrics contract:

- `GET /api/metrics` returns `total_assets`, `total_relationships`, `asset_classes`, `avg_degree`, `max_degree`, `network_density`, and `relationship_density`.
- `total_assets`, `total_relationships`, and density are sourced from `calculate_metrics()`.
- `asset_classes`, `avg_degree`, and `max_degree` are computed in the router.

API relationship contract:

- `GET /api/relationships` and `GET /api/assets/{asset_id}/relationships` expose graph relationships without changing relationship strength.

API visualization contract:

- `GET /api/visualization` exposes presentation nodes and edges.
- Nodes include graph identity fields plus layout/color/size encodings.
- Edges include graph relationship identity and strength.

Frontend contract:

- `MetricsDashboard` expects metric numbers and formats density as a fraction.
- `NetworkVisualization` expects explicit node/edge fields and treats strength as a visual opacity/width input.
- `AssetList` expects either a list or a paginated response, though the current backend list endpoint is not paginated.

## Final answer

The likely answer is:

Financial relationship computation is mostly isolated in `src/logic/asset_graph.py`, but production API metrics are not a pure presentation projection. The specific boundary violations or blurs are the metrics router's duplicate aggregations, density unit drift between backend and frontend, loose visualization response contracts, and asset pagination assumptions in the frontend.

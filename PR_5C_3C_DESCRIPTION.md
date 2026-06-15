# PR: Stage 5C.3C - Cancellation Integrity

## Architectural Alignment

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

This PR implements a two-stage, database-backed cancellation model (`CANCEL_REQUESTED` -> `CANCELLED`) for graph rebuilds. It leverages the existing production heartbeat and distributed locking architecture, extending it to propagate cancellation signals cooperatively. No changes contradict the defined production architecture.

## Primary Objective

Ensure that rebuild executions can be reliably and safely cancelled by operators, stopping heavy computation (fetching/processing) and preventing the commitment of partial or inconsistent graph states.

## Triage Data (Project Mandate)

- **Upstream Source**: Initiated by `cancel_rebuild_job` via the `POST /api/graph/rebuild/jobs/{job_id}/cancel` endpoint. The caller (operator) assumes that the request will lead to an eventually consistent termination of the background executor without data corruption.
- **Downstream Impact**: Propagates to the background heartbeat thread (`_heartbeat_keeper`), which sets a `cancel_event` shared with the `ReconciliationEngine` and `RealDataFetcher`. This causes immediate abortion of heavy computation, preventing downstream resource starvation.
- **Failure Mode**: If the database is unreachable, the API returns a 503/error and the job remains `RUNNING`. If the heartbeat thread fails to detect the signal, the job continues until completion or lock expiration. Rollback safety is guaranteed as the graph is written only _after_ checking signals.

## Scope

### In Scope

- **Schema Update**: Added `cancel_requested` status and `cancellation_requested_at` timestamp to `rebuild_jobs`.
- **Repository Methods**: Implemented atomic state transitions (`mark_rebuild_job_cancel_requested`, `mark_rebuild_job_cancelled`) and updated heartbeat detection.
- **Cooperative Cancellation**: Updated `ReconciliationEngine.run_rebuild` and `RealDataFetcher.fetch_raw_data_with_source` to check `cancel_event`.
- **API Endpoint**: Added `POST /api/graph/rebuild/jobs/{job_id}/cancel` with operator authorization.
- **Testing**: Added unit and integration tests (11 total) covering the full cancellation lifecycle.

### Out of Scope

- **Frontend UI**: UI controls for cancellation are not included in this PR.
- **Global IPC**: No new pub/sub or message broker was introduced; signal propagation is DB-driven via existing heartbeat cycles.
- **Automatic Recovery**: This PR handles cancellation only; automatic recovery from crashes is handled in previous 5C PRs.

### Files Expected to Change

- `src/data/db_models.py`: Added cancellation fields and updated status constraints.
- `src/data/migrations.py` & `migrations/004_...sql`: Migration for new schema.
- `src/data/repository.py`: Repository logic for state transitions and heartbeat error raising.
- `src/logic/reconciliation_engine.py`: Integrated cancellation checks into the rebuild loop.
- `src/data/real_data_fetcher.py`: Integrated cancellation checks into the fetch process.
- `api/routers/graph_admin.py`: API endpoint and background thread orchestration.
- `api/graph_lifecycle_providers.py`: Passing signals to the engine.
- `tests/*`: Comprehensive test suite.

## Validation Commands

```bash
pytest tests/unit/test_repository_cancellation.py tests/unit/test_reconciliation_engine_cancellation.py tests/integration/test_graph_rebuild_cancellation.py
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [x] Validation commands pass locally or in CI
- [x] Changes align with production architecture (FastAPI + Next.js)

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only (Cancellation Integrity)
- [x] I have explicitly listed what is out of scope
- [x] I have verified the branch and base branch
- [x] I have checked this PR against the production architecture

### Testing Best Practices

- [x] Tests verify observable behavior (DB state changes, API responses)
- [x] Tests use polling/wait events instead of fixed sleeps where possible
- [x] Tests properly clean up resources

AI-Generated: true

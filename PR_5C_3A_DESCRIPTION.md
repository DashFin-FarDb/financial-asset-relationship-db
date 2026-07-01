# Pull Request: Stage 5C.3A - Execution Identity & Idempotent Ownership

## Architectural Alignment

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

This PR adheres to the distributed coordination and domain persistence model by introducing an authoritative identity for every rebuild attempt.

## Primary Objective

Implement a persistent and authoritative execution identity for rebuild jobs to ensure that all state mutations are attributable to a specific execution attempt and to prevent stale or zombie executors from modifying the database.

## Scope

### In Scope

- **Schema Update**: Added `execution_id` (String(64)) to `RebuildJobORM`.
- **Repository Hardening**: Refactored `AssetGraphRepository` to require and validate `execution_id` for all state mutations (`RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`).
- **Identity Generation**: Unique `execution_id` (UUID) is now generated per attempt in `api/routers/graph_admin.py`.
- **Ownership Enforcement**: Heartbeat loop and pipeline transitions now verify identity, raising `ValueError` on mismatch to prevent duplicate writes.
- **Recovery Integration**: `RecoveryGate` now preserves the existing `execution_id` during orphaned job resets.
- **Full Test Coverage**: Updated and verified all repository and API unit tests.

### Out of Scope

- Persistent checkpointing of domain work (Deferred to Stage 5C.3B).
- Logic for resuming from a specific checkpoint (Deferred to Stage 5C.3B).
- Cancellation signal propagation (Deferred to Stage 5C.3C).

### Files Expected to Change

- `src/data/db_models.py`: Schema update.
- `src/data/repository.py`: Mutation logic and validation.
- `src/logic/recovery_gate.py`: Reset logic update.
- `api/routers/graph_admin.py`: Identity generation and propagation.
- `tests/unit/test_repository_rebuild_jobs.py`: Test alignment.
- `tests/unit/test_repository_distributed_lock.py`: Test alignment.
- `tests/unit/test_graph_admin_typed_lock_ttl.py`: Test alignment.
- `tests/unit/test_metrics.py`: Test alignment.

## Triage Data (Mandates)

- **Upstream Source**: Initiated by `_run_rebuild_in_executor` via the `/api/graph/rebuild` endpoint. The caller assumes that the `execution_id` is unique and will be used to guard all subsequent mutations.
- **Downstream Impact**: Propagates to `AssetGraphRepository` and the database `rebuild_jobs` table. Ensures that if multiple executors exist (e.g., due to a crash and restart), only the current owner of the `execution_id` can successfully commit changes, preventing data corruption from zombie processes.
- **Failure Mode**: If `execution_id` validation fails during a mutation, a `ValueError` is raised, causing the executor to stop or the heartbeat thread to signal lock loss. This fails closed, ensuring no unauthenticated writes occur.

## Validation Commands

```bash
pytest tests/unit/test_repository_rebuild_jobs.py
pytest tests/unit/test_metrics.py
pytest tests/unit/test_graph_admin_typed_lock_ttl.py
pytest tests/unit/test_repository_distributed_lock.py
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [x] Validation commands pass locally or in CI
- [x] Changes align with production architecture (FastAPI + Next.js)

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only (Execution Identity)
- [x] I have explicitly listed what is out of scope
- [x] I have verified the branch and referenced Issue #1248
- [x] I have checked this PR against the production architecture

### Testing Best Practices

- [x] Tests verify observable behavior (ValueError on mismatch)
- [x] Tests properly clean up resources

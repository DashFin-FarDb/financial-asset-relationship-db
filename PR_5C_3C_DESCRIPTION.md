# PR: Stage 5C.3C - Cancellation Integrity

## Triage Data

- **Upstream Source**: Initiated by `cancel_rebuild_job` via the `POST /api/graph/rebuild/jobs/{job_id}/cancel` endpoint. The caller (operator) assumes that the request will lead to an eventually consistent termination of the background executor without data corruption.
- **Downstream Impact**: Propagates to the background heartbeat thread (`_heartbeat_keeper`), which sets a `cancel_event` shared with the `ReconciliationEngine` and `RealDataFetcher`. This causes immediate abortion of heavy computation (fetching/processing), preventing downstream resource starvation and avoiding the commitment of partial, inconsistent graph states.
- **Failure Mode**: If the database is unreachable when requesting cancellation, the API returns a 503/error and the job remains `RUNNING`. If the heartbeat thread fails to detect the signal, the job will continue until completion or lock expiration. In all cases, the authoritative graph is only written *after* checking the cancellation signal, ensuring rollback safety.

## Objective

Ensure that rebuild executions can be reliably and safely cancelled using a two-stage, database-backed cancellation model (`CANCEL_REQUESTED` -> `CANCELLED`) that leverages the existing heartbeat mechanism for signal propagation.

## Changes

### Data Layer
- **Schema**: Added `cancel_requested` to `RebuildJobStatus` and `cancellation_requested_at` to `RebuildJobORM`.
- **Repository**: 
  - `mark_rebuild_job_cancel_requested`: Atomically transitions job to `CANCEL_REQUESTED`.
  - `mark_rebuild_job_cancelled`: Atomically transitions job to `CANCELLED` with identity validation.
  - `update_rebuild_heartbeat`: Raises `RebuildCancellationRequestedError` upon signal detection.
- **Migrations**: Added `004_add_cancellation_columns.sql` for schema compatibility.

### Orchestration & Logic
- **Heartbeat**: `_heartbeat_keeper` now monitors DB status during each refresh cycle. If `CANCEL_REQUESTED` is found, it stops lease renewal and signals a cooperative `cancel_event`.
- **Engine**: `ReconciliationEngine.run_rebuild` periodically checks the `cancel_event` and raises `RebuildCancelledError`.
- **Fetchers**: `RealDataFetcher.fetch_raw_data_with_source` integrated with the cancellation signal to abort multi-step fetching.
- **Pipeline**: `_run_rebuild_pipeline` catches `RebuildCancelledError` to perform clean exit and persist the terminal `CANCELLED` state.

### API Integration
- **Endpoint**: `POST /api/graph/rebuild/jobs/{job_id}/cancel` added with `get_current_rebuild_operator_user` dependency.

## Verification Results

- **Unit Tests**:
  - `tests/unit/test_repository_cancellation.py`: Verified all status transitions and identity enforcement.
  - `tests/unit/test_reconciliation_engine_cancellation.py`: Verified loop abortion and exception raising.
- **Integration Tests**:
  - `tests/integration/test_graph_rebuild_cancellation.py`: Verified endpoint wiring, authorization, and end-to-end heartbeat detection.
- **Regression**: Verified no impact on existing rebuild happy path or failure recovery.

AI-Generated: true

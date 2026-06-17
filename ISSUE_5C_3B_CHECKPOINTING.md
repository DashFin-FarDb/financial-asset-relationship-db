# Sub-Issue: Stage 5C.3B - Checkpointed Recovery Strategy

## Parent Roadmap

Related to Issue #1248: Stage 5C.3 - Executor Crash Recovery & Cancellation Integrity.

## Objective

Define and implement a checkpointing mechanism that allows the Reconciliation Engine to persist its progress, enabling the 'Resume' recovery path to skip already completed work. This builds upon the **Execution Identity** implemented in 5C.3A.

## Implementation Plan

### 1. Data Layer: Checkpoint Persistence

- **Schema Update**: Add a `checkpoint_data` column (JSON/String) to `RebuildJobORM` to store the high-water mark of execution.
- **Repository Update**: Implement `update_rebuild_checkpoint(job_id, execution_id, data)` with identity validation.

### 2. Logic Layer: Reconciliation Engine Integration

- **Checkpoint Callback**: Add an optional `on_checkpoint` callback to the `RebuildExecutor.run_rebuild` method.
- **Engine Instrumentation**: Modify the main processing loop in `ReconciliationEngine` to invoke the checkpoint callback at bounded intervals (e.g., every 50 assets processed).
- **Resume Initialization**: Update the engine to accept an initial `checkpoint_state` and use it to filter/skip already processed entities during reconstruction.

### 3. API Layer: Recovery Orchestration

- **Pipeline Update**: Modify `_run_rebuild_pipeline` to pass a database-persisting callback to the engine.
- **Resume Detection**: Update the start logic to check if a job being "resumed" (e.g., after an administrative reset or automatic recovery) has existing `checkpoint_data`.

### 4. Validation & Observability

- **Unit Tests**:
  - Verify `ReconciliationEngine` correctly skips work when initialized with a checkpoint.
  - Verify the repository correctly persists and validates checkpoint updates.
- **Integration Tests**:
  - Simulate a crash mid-rebuild.
  - Trigger a "Resume" and verify the resulting graph is identical to a full rebuild but processed fewer assets.
- **Metrics**: Add a `rebuild_checkpoints_total` counter.

## Success Criteria

- Progress is persisted at least every 50 assets.
- A resumed job correctly identifies its last checkpoint and avoids redundant computation.
- All checkpoint writes are guarded by the `execution_id` from Stage 5C.3A.

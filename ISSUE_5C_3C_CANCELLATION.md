# Issue: Stage 5C.3C - Cancellation Integrity

## Parent Roadmap

Related to Issue #1248: Stage 5C.3 - Executor Crash Recovery & Cancellation Integrity.

## Objective

Ensure that rebuild executions can be reliably and safely cancelled, including propagation of cancellation signals through the Reconciliation Engine and proper cleanup of persistent state.

## Requirements

### 1. Signal Propagation

- The `ReconciliationEngine` processing loop must periodically check for a cancellation signal (e.g., via a `threading.Event` or checking the database status).
- Sub-components (DataSource, Evaluators) must also respect this signal.

### 2. State Consistency

- When a cancellation is detected, the executor must transition the job to `CANCELLED` status.
- Partial graph data must NOT be published to the runtime.
- Distributed locks must be released immediately.

### 3. API Integration

- Implement `/api/graph/rebuild/{job_id}/cancel` endpoint.
- Ensure the heartbeat keeper stops immediately upon cancellation.

### 4. Validation

- Test that a cancelled rebuild stops all heavy computation within 5 seconds of the signal.
- Verify that a cancelled rebuild leaves the system in its prior good state (authoritative graph remains unchanged).

## Success Criteria

- Zero "zombie" rebuild threads after a cancellation request.
- Authoritative runtime state is never corrupted by a partial, cancelled run.

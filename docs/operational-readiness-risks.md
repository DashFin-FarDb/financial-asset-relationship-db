# Production Readiness & Recovery Risks

This document catalogs the outstanding technical debt, validation gaps, and operational risks associated with the Stage 5C Failure Management and Recovery architecture. These risks were identified following the completion of Stages 5C.1 and 5C.2.

## 1. Lack of Realistic Graph-Scale Validation
**Status:** High Risk | **Impact:** General Production Readiness
The system has not been tested against a production-scale graph (e.g., millions of nodes/edges). Recovery logic can be technically correct but fail under scale-related conditions:
- Long rebuild durations exceeding maximum lock TTLs.
- Heartbeat timing drift under heavy CPU/memory pressure.
- Database transaction contention during massive atomic swaps.
- OOM (Out of Memory) panics during computation.

## 2. Undefined Checkpoint/Restart Strategy
**Status:** Blocker for 5C.3 | **Impact:** Executor Recovery Design
Stage 5C.3 requires a defined checkpointing strategy to enable execution recovery. It is currently undefined whether a "checkpoint" means:
- Rebuild phase boundaries (extraction -> computation -> persistence).
- Persisted progress markers (batching).
- Idempotent replay from the start (monolithic transaction).

## 3. Insufficient Recovery-Path Testing Coverage
**Status:** Medium Risk | **Impact:** Reliability
While the implementation handles complex state transitions, the test suite must explicitly prove all edge cases, including:
- Heartbeat expiry while a rebuild is actively running.
- Executor crash immediately after lock acquisition.
- Executor crash immediately before/after completion but before state update.
- Startup reconciliation with missing/stale locks.
- Multiple concurrent recovery attempts simulating a split-brain environment.

## 4. Missing Formal State-Machine & Invariant Documentation
**Status:** Medium Risk | **Impact:** Maintainability & Governance
The distributed state machine is currently scattered across implementation files (`RebuildJobStatus`, `RecoveryAction`, `InconsistencyType`, `LockState`). A definitive architectural document must be created to describe:
- Every state and transition (allowed vs. forbidden).
- Terminal states and recovery actions.
- Formal invariants (e.g., "Only one active rebuild owner may exist", "Stale owner may never mutate state").

## 5. Observability Not Yet Validated Against Operational Scenarios
**Status:** Medium Risk | **Impact:** Operational Procedures
Metrics, logs, and events exist, but they have not been proven to answer real-world operational questions:
- How does an operator identify a stuck rebuild vs. a slow rebuild?
- How is ownership loss identified?
- How does an operator distinguish a recoverable failure from a terminal failure?

## 6. Failure Taxonomy Review Needed
**Status:** Low Risk | **Impact:** 5C.3 State Model Expansion
Before introducing `FAILED_RECOVERABLE` and `FAILED_TERMINAL` states in 5C.3, the existing failure categories must be reviewed to ensure they naturally support this distinction, ensuring classification is designed for recovery eligibility, not just diagnosis.

## 7. Missing Operational Procedures (Runbooks)
**Status:** Low Risk | **Impact:** Governance
With the system now capable of blocking execution (`RecoveryGate`), runbooks must be created defining:
- What an operator should do when execution is blocked.
- The approval workflow for manual recovery.
- Who can override the gate and what evidence is required.

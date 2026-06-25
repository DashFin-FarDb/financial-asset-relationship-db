# Production Readiness & Recovery Risks

For the broader enterprise-readiness audit and rollout plan, see [docs/enterprise-readiness-index.md](./enterprise-readiness-index.md).

This document catalogs the outstanding technical debt, validation gaps, and operational risks associated with the Stage 5C Failure Management and Recovery architecture. These risks were identified following the completion of Stages 5C.1 and 5C.2.

## 1. Lack of Realistic Graph-Scale Validation

**Status:** High Risk | **Impact:** General Production Readiness
The system has not been tested against a production-scale graph (e.g., millions of nodes/edges). Recovery logic can be technically correct but fail under scale-related conditions:

- Long rebuild durations exceeding maximum lock TTLs.
- Heartbeat timing drift under heavy CPU/memory pressure.
- Database transaction contention during massive atomic swaps.
- OOM (Out of Memory) panics during computation.

## 2. Insufficient Recovery-Path Testing Coverage

**Status:** Low Risk | **Impact:** Reliability
Unit and integration tests are now active for startup recovery and cancellation. While core recovery paths are verified, continuous monitoring of edge cases remains recommended, including:

- Heartbeat expiry while a rebuild is actively running.
- Executor crash immediately after lock acquisition.
- Executor crash immediately before/after completion but before state update.
- Multiple concurrent recovery attempts simulating a split-brain environment.

## 3. Formal State-Machine & Invariant Documentation

**Status:** Resolved | **Impact:** Maintainability & Governance
The formal state-machine documentation gap is resolved by the canonical [State Machine and Operating Authority](governance/state-machine-and-operating-authority.md), which now defines:

- Every governed rebuild/job and runtime lifecycle state and transition.
- Terminal states and recovery actions.
- Formal invariants such as single-writer ownership, stale-owner mutation blocking, lock-loss aborts, and bounded-health versus durable-truth interpretation.

Future PRs that alter governed rebuild, recovery, persistence, ownership, or exception behaviour must update that canonical spec or explicitly prove that the current interpretation remains unchanged.

## 4. Observability Not Yet Validated Against Operational Scenarios

**Status:** Medium Risk | **Impact:** Operational Procedures
Metrics, logs, and events exist, but they have not been proven to answer real-world operational questions:

- How can an operator identify a stuck rebuild vs. a slow rebuild?
- How can an operator identify ownership loss?
- How can an operator distinguish a recoverable failure from a terminal failure?

## 5. Missing Operational Procedures (Runbooks)

**Status:** Low Risk | **Impact:** Governance
With the system now capable of blocking execution (`RecoveryGate`), runbooks must be created defining:

- What an operator should do when execution is blocked.
- The approval workflow for manual recovery.
- Who can override the gate and what evidence is required.

---

## Resolved Risks History

### Risk: Formal State-Machine & Invariant Documentation (Previously Risk 3)

**Status:** Resolved
The canonical [State Machine and Operating Authority](governance/state-machine-and-operating-authority.md) now defines the current operational interpretation of rebuild/recovery state machines, invariants, operator ownership, exception authority, and evidence rules.

### Risk: Undefined Checkpoint/Restart Strategy (Previously Risk 2)

**Status:** Resolved
A checkpoint/restart strategy has been defined and implemented, defining execution boundaries and enabling recovery mechanisms to successfully resume from known good states.

### Risk: Failure Taxonomy Review Needed (Previously Risk 6)

**Status:** Resolved
The failure taxonomy has been reviewed and expanded, providing clean differentiation between recoverable and terminal failures to support automation and recovery gating.

## Coordination Seam / Decision

<!-- State the specific coordination plane or lock subsystem change this PR implements. -->
<!-- Example: Migrate DistributedLock.refresh to use CoordinationLockRepository.refresh_lock. -->

## Why this migration now

<!-- Explain how this change complies with the Coordination-Safe Repository Interface Specification (Version 1.0) -->
<!-- and why it is essential for multi-region or transactional reliability. -->

## Strict Architectural Checks

### Coordination-Plane Decoupling
- [ ] No SQLAlchemy ORM models, session boundaries, or active identity maps cross the boundary.
- [ ] Logic operates purely on fully materialized, frozen DTO primitives (`LockRecord`, `LockWriteResult`, `LockStateSnapshot`).
- [ ] Main application repositories (e.g. `AssetGraphRepository`) are structurally decoupled from all lock-handling methods.

### Monotonic Fencing & Atomic Return
- [ ] Fencing tokens originate strictly from the DB write response (no re-queries, cached session reads, or timestamp recomputation).
- [ ] Fencing tokens are guaranteed strictly monotonic (`token(n+1) > token(n)`) at the database layer.
- [ ] Write operations return `(fencing_token, updated_at)` from the *same* atomic DB transaction.

### Transaction & Routing Constraints
- [ ] Zero read-write coupling: no "read after write using the same session" pattern is present.
- [ ] Coordination writes execute strictly on the authoritative PRIMARY instance (no read-replicas).
- [ ] Write operations are performed in a single SQL statement or single transaction block.

## In Scope

<!-- List the exact responsibilities, DTO models, repository methods, or observability events being refactored. -->

-
-
-

## Out of Scope

<!-- Explicitly list surrounding concerns (e.g. rebuild job persistence, health endpoints, front-end visualizers) not changed in this PR. -->

-
-
-

## Observability & State Machine Verification

- [ ] Lock lifecycle state transitions (`INITIAL`, `ACQUIRED`, `REFRESHED`, `LOST`, `RELEASED`) are verified.
- [ ] Immutable `LockEvent` emission is covered in tests.
- [ ] Standardized metrics tracking (counters and latency histograms) is tested.
- [ ] If this PR changes lock ownership, fencing, heartbeat, stale-owner, or rebuild state-machine semantics, `docs/governance/state-machine-and-operating-authority.md` is updated or the PR proves the canonical interpretation is unchanged.

## Files Expected to Change

<!-- Enumerate the files that should change. Reviewers can use this to detect drift. -->

-
-
-

## Validation Commands

<!-- List the exact focused tests and style checks run to verify this coordination seam. -->

```bash
# Focused lock unit tests
pytest tests/unit/test_repository_distributed_lock.py -v

# Integration lock and recovery tests
pytest tests/integration/test_distributed_coordination.py -v
pytest tests/integration/test_recovery_gate_integration.py -v

# Formatting and linting checks
black --check <modified_files>
flake8 <modified_files>
```

## Merge Criteria

- [ ] Lock logic is 100% free of session-bound ORM leakage.
- [ ] All write results are fully materialized in a single round-trip.
- [ ] Fencing token monotonicity is verified and strictly enforced.
- [ ] Multi-region primary-only routing rules are strictly followed.
- [ ] Unit and integration tests pass perfectly.
- [ ] Canonical state-machine authority is updated when governed coordination behaviour changes.

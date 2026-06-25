# Validation Gap Audit

Status: Active
Issue: #1296
Scope: PR B — focused technical review of tests and CI

## Purpose

This document records whether the current test suites prove load-bearing behaviour or merely exercise successful shapes, types, and happy paths. It is intentionally evidence-oriented: each subsystem lists representative tests, the assertion depth currently present, the remaining validation gap, and the remediation phase that closes or tracks the gap.

The audit distinguishes three states:

- **Behaviourally proven**: tests assert exact state transitions, failure categories, serialized fields, or invariant outcomes. No remediation is required in this phase.
- **Partially proven**: tests exercise real code paths but leave important values or seams unasserted.
- **Shape-only / happy-path**: tests primarily check response status, field presence, broad ranges, or object types.

## Behaviourally proven areas

The following areas are already behaviourally proven and do not require remediation in this validation phase.

| Area | Representative tests | Why no remediation is required |
| --- | --- | --- |
| Auth audit events | `tests/unit/test_auth_router_audit_logging.py`, `tests/unit/test_auth_security_events.py` | Tests assert exact audit event names, bounded/sanitized metadata, success/failure branches, and security-event behaviour rather than only checking that logging occurred. |
| Lock-loss / stale-owner / RecoveryGate | `tests/unit/test_distributed_lock_runtime.py`, `tests/unit/test_rebuild_failure_detection.py`, `tests/unit/test_rebuild_recovery.py`, `tests/integration/test_lock_refresh_flow.py`, `tests/unit/test_recovery_gate*.py` | Tests assert lock refresh/loss outcomes, stale-owner classification, RecoveryGate reset/block decisions, failure categories, and lock reacquisition behaviour. |

## Per-area assessment

| Subsystem | Representative test files | Current assertion depth | Finding | Remediation phase |
| --- | --- | --- | --- | --- |
| Restart / reload | `tests/unit/test_graph_lifecycle_persistence.py`, `tests/integration/test_distributed_hosting_failure_modes.py` | Startup and reset tests prove persisted loading and fail-fast paths, but coverage is split across lifecycle and coordination seams. | Missing end-to-end restart-recovery pipeline test that executes startup, RecoveryGate, distributed lock acquisition, and durable graph load as one integrated sequence. | Phase 3 — end-to-end restart-recovery pipeline test. |
| Persistence round trip | `tests/unit/test_repository_graph_persistence.py`, `tests/unit/test_graph_lifecycle_persistence.py` | Existing tests prove graph IDs, relationship strengths, stale-row removal, event IDs, and subtype-specific fields. | Persistence fidelity is not uniformly asserted at the field level for base asset fields (`price`, `name`, `sector`, `currency`, `asset_class`) and regulatory-event fields (`impact_score`, `related_assets`, `date`, `description`). | Phase 3 — field-level persistence round-trip fidelity tests. |
| Lock-loss / stale-owner | `tests/unit/test_distributed_lock_runtime.py`, `tests/unit/test_rebuild_failure_detection.py`, `tests/integration/test_lock_refresh_flow.py`, `tests/integration/test_distributed_hosting_failure_modes.py` | Behavioural assertions cover lock-loss detection, stale heartbeat classification, fail-closed paths, and terminal job state. | Behaviourally proven. No remediation required. | None. |
| RecoveryGate decisions | `tests/unit/test_recovery_gate*.py`, `tests/unit/test_rebuild_recovery.py`, `tests/integration/test_distributed_hosting_failure_modes.py` | Tests assert exact reset/block outcomes, recovery failure categories, and lock reacquisition semantics. | Behaviourally proven. No remediation required. | None. |
| Graph smoke checks | `tests/unit/test_asset_graph.py`, `tests/unit/test_api_main.py`, visualization and metrics endpoint tests | Existing checks verify shapes, response success, and density bounded to `[0.0, 1.0]`. | Density formula only bounds-checked; formula, clamp behaviour, domain invariants, and endpoint density parity need exact behavioural assertions. | Phase 2 — density formula, domain invariant, and API parity tests. |
| Auth audit events | `tests/unit/test_auth_router_audit_logging.py`, `tests/unit/test_auth_security_events.py` | Tests assert event names, metadata normalization, bounded user fields, and failure/success paths. | Behaviourally proven. No remediation required. | None. |
| API pagination / density | `tests/unit/test_api_main.py`, `tests/integration/test_api_integration.py`, `tests/integration/test_graph_admin_router.py` | Pagination shape is checked and invalid boundaries are rejected; density is present and range-bounded. | `hasMore` value is never asserted for non-final/final pages; `per_page=1000` lacks explicit acceptance coverage; `RebuildJobListResponse` truncates at 100 without a `total`/`has_more` signal; density parity between `/api/visualization` and `/api/graph/metrics` needs exact value coverage. | Phase 2 for density parity; Phase 4 for pagination and rebuild job-list cap/count tests. |
| Frontend / backend type alignment | `api/api_models.py`, `frontend/app/types/api.ts`, `frontend/__tests__/integration/component-integration.test.tsx`, `frontend/__tests__/app/page.test.tsx`, `frontend/__tests__/lib/api.test.ts` | Type declarations exist on both sides, but tests have mostly exercised successful client calls and component rendering. | Load-bearing `hasMore` alias seam is not anchored by a backend serialization test; some frontend visualization mocks omit `network_density`, weakening fidelity to `VisualizationData`. | Phase 4 — backend alias serialization test, frontend mock conformance, and optional client contract assertion. |

## Remediation map

### Phase 2 — Graph density and smoke-test semantics

- Pin `calculate_graph_density()` with exact formula cases.
- Assert the `min(1.0, ...)` clamp for parallel relationship-type topologies.
- Assert domain invariants for duplicate asset replacement, relationship-strength validation, duplicate relationship deduplication, and degree metrics excluding zero-degree assets.
- Assert API density edge cases and parity between `/api/visualization` and `/api/graph/metrics`.

### Phase 3 — Persistence fidelity and restart recovery

- Extend persistence tests so a reconstructed graph that drops non-ID asset fields or regulatory-event fields fails.
- Add an integrated restart-recovery test covering startup load, RecoveryGate evaluation, distributed lock acquisition/reacquisition, and durable graph load from SQLite.

### Phase 4 — API pagination and frontend/backend seam

- Assert `hasMore == true` on a non-final page and `hasMore == false` on the last page in unit and integration API coverage.
- Assert `per_page=1000` is accepted.
- Assert rebuild job-list responses cap at 100 and report `count == len(jobs)`, while documenting that no truncation signal exists yet.
- Assert `AssetPageResponse` serializes with the JSON key `hasMore`.
- Restore frontend mock fidelity by ensuring visualization mocks include `network_density`.

## Audit conclusion

The strongest existing coverage is in auth audit logging, distributed lock handling, stale-owner detection, and RecoveryGate decisions. Those areas already assert exact outcomes and failure-state semantics.

The weakest areas are contract boundaries: graph density semantics, pagination values, persistence field fidelity, restart-recovery composition, and frontend/backend serialization seams. These are not broad feature gaps; they are validation gaps where the implementation can work while tests still fail to pin the intended contract. This PR closes the highest-leverage gaps by adding behavioural assertions without changing production behaviour.

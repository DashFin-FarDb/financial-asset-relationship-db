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
| Restart / reload | `tests/unit/test_graph_lifecycle_persistence.py`, `tests/integration/test_distributed_hosting_failure_modes.py`, `tests/integration/test_restart_recovery_clean_path.py` | Startup and reset tests prove persisted loading and fail-fast paths. This PR adds an integrated clean restart path covering startup load, RecoveryGate evaluation, distributed lock acquisition, and durable graph load from SQLite. | Partially covered. The clean restart/reload pipeline is now behaviourally covered. A strict stale-owner-reset end-to-end pipeline remains open if Phase 3 requires that exact integrated sequence; stale-owner reset behaviour itself is already proven by the existing lock/recovery suites. | Phase 3 — clean restart path closed in this PR; optional follow-up for strict stale-owner-reset end-to-end composition only. |
| Persistence round trip | `tests/unit/test_repository_graph_persistence.py`, `tests/unit/test_graph_lifecycle_persistence.py`, `tests/unit/test_repository_graph_persistence_fields.py`, `tests/unit/test_graph_lifecycle_persistence_fields.py` | Existing tests prove graph IDs, relationship strengths, stale-row removal, event IDs, and subtype-specific fields. This PR adds field-level equality for base asset fields and regulatory-event fields across repository and lifecycle persisted loads. | Covered. A reconstruction that drops `price`, `name`, `sector`, `currency`, `asset_class`, `impact_score`, `related_assets`, `date`, or `description` is now test-visible. | Phase 3 — closed in this PR. |
| Lock-loss / stale-owner | `tests/unit/test_distributed_lock_runtime.py`, `tests/unit/test_rebuild_failure_detection.py`, `tests/integration/test_lock_refresh_flow.py`, `tests/integration/test_distributed_hosting_failure_modes.py` | Behavioural assertions cover lock-loss detection, stale heartbeat classification, fail-closed paths, and terminal job state. | Behaviourally proven. No remediation required. | None. |
| RecoveryGate decisions | `tests/unit/test_recovery_gate*.py`, `tests/unit/test_rebuild_recovery.py`, `tests/integration/test_distributed_hosting_failure_modes.py` | Tests assert exact reset/block outcomes, recovery failure categories, and lock reacquisition semantics. | Behaviourally proven. No remediation required. | None. |
| Graph smoke checks | `tests/unit/test_asset_graph.py`, `tests/unit/test_asset_graph_density_and_invariants.py`, `tests/unit/test_api_density_contract.py`, visualization and metrics endpoint tests | Existing checks verify shapes, response success, and density bounds. This PR adds exact `calculate_graph_density()` formula cases, clamp coverage, domain invariants, API density edge cases, and `/api/visualization` versus `/api/graph/metrics` parity. | Covered. Density semantics and graph smoke invariants are now behaviourally asserted rather than only range-checked. | Phase 2 — closed in this PR. |
| Auth audit events | `tests/unit/test_auth_router_audit_logging.py`, `tests/unit/test_auth_security_events.py` | Tests assert event names, metadata normalization, bounded user fields, and failure/success paths. | Behaviourally proven. No remediation required. | None. |
| API pagination / density | `tests/unit/test_api_main.py`, `tests/unit/test_api_asset_pagination_values.py`, `tests/integration/test_api_pagination_contract.py`, `tests/unit/test_api_density_contract.py`, `tests/integration/test_rebuild_job_list_contract.py`, `tests/unit/test_rebuild_job_list_response_model.py` | Pagination shape and invalid boundaries were already tested. This PR adds exact `hasMore` true/false assertions, `per_page=1000` acceptance, rebuild job-list `count` / `total` / `has_more` assertions, status-filtered truncation assertions, and API density parity. | Covered. Pagination values, density parity, and rebuild job-list truncation semantics are now behaviourally asserted. `RebuildJobListResponse.total` reflects matching rows before pagination, and `has_more` signals whether another page exists after the current response. | Phase 2 density parity closed; Phase 4 pagination, cap/count, and rebuild job-list truncation closed. |
| Frontend / backend type alignment | `api/api_models.py`, `frontend/app/types/api.ts`, `tests/unit/test_asset_page_response_alias.py`, `frontend/__tests__/lib/api-contract-seams.test.ts` | Type declarations exist on both sides. This PR anchors backend `AssetPageResponse` serialization to the JSON key `hasMore` and adds a frontend contract test requiring `hasMore` and `VisualizationData.network_density`. | Partially covered. The load-bearing `hasMore` alias seam and frontend `network_density` type seam are now tested. Any remaining ad hoc component-local visualization mocks that are not explicitly typed as `VisualizationData` should be converted opportunistically, but the public contract seam is now covered. | Phase 4 — backend alias and frontend contract seam closed in this PR; optional mock cleanup remains. |

## Remediation map

### Phase 2 — Graph density and smoke-test semantics

Closed in this PR:

- Pin `calculate_graph_density()` with exact formula cases.
- Assert the `min(1.0, ...)` clamp for parallel relationship-type topologies.
- Assert domain invariants for duplicate asset replacement, relationship-strength validation, duplicate relationship deduplication, and degree metrics excluding zero-degree assets.
- Assert API density edge cases and parity between `/api/visualization` and `/api/graph/metrics`.

Remaining work: none identified for Phase 2 density semantics.

### Phase 3 — Persistence fidelity and restart recovery

Closed in this PR:

- Extend persistence tests so a reconstructed graph that drops non-ID asset fields or regulatory-event fields fails.
- Add an integrated clean restart-recovery test covering startup load, RecoveryGate evaluation, distributed lock acquisition, and durable graph load from SQLite.

Remaining work:

- Add a strict stale-owner-reset end-to-end restart pipeline only if the phase requires that exact composition test. Existing lock-loss, stale-owner, and RecoveryGate suites already prove the reset decision and mutation behaviour outside this integrated restart path.

### Phase 4 — API pagination and frontend/backend seam

Closed in this PR:

- Assert `hasMore == true` on a non-final page and `hasMore == false` on the last page in unit and integration API coverage.
- Assert `per_page=1000` is accepted.
- Assert rebuild job-list responses cap at 100 and report `count == len(jobs)`.
- Assert `AssetPageResponse` serializes with the JSON key `hasMore`.
- Anchor the frontend type seam for `hasMore` and `VisualizationData.network_density`.

Remaining work:

- `RebuildJobListResponse` now carries `total` and `has_more` truncation signals. `total` counts matching rows before pagination, including the active `status` filter, and `has_more` is derived from `offset`, returned count, and `total`.
- Opportunistically convert any remaining ad hoc frontend visualization mocks to typed `VisualizationData` fixtures when those tests are next edited.

## Audit conclusion

The strongest existing coverage is in auth audit logging, distributed lock handling, stale-owner detection, and RecoveryGate decisions. Those areas already assert exact outcomes and failure-state semantics.

This PR closes the highest-leverage validation gaps around graph density semantics, pagination values, rebuild job-list truncation, persistence field fidelity, clean restart-recovery composition, and frontend/backend serialization seams. The remaining open items are optional maturity work rather than untested happy paths: optionally adding a strict stale-owner-reset end-to-end restart pipeline and converting residual ad hoc frontend mocks to typed fixtures.

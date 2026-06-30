## Architectural Alignment

- Backend: FastAPI (production path)
- Frontend: Next.js (production path)
- Gradio: non-production (demo/testing only)

This PR resolves repository-wide scan findings across documentation/templates alignment, security/lock boundary verification, and test suite resource safety and contracts.

## Primary Objective

1. Align all evidence templates, roadmap, spec documents, and runbooks to consistent keys (standardizing top-level references to `graph_persistence_configured` while preserving the nested `graph.persistence_enabled` contract in `/api/health/detailed`) and non-configurable TTL rules.
2. Hard-boundary the lock-reset path and enforce the deterministic 30s lock acquisition timeout limit in the recovery gate.
3. Broaden audit log metadata sanitization to protect sensitive credentials and prevent identifier spoofing.
4. Eliminate resource leaks in DB test suites and add explicit edge-case assertions for API contracts.

## Scope

### In Scope

- **Documentation & Templates**: Align Average Degree definitions and legend statuses in specifications and roadmaps. Standardize top-level references to `graph_persistence_configured` in issue templates, while preserving the nested `graph.persistence_enabled` contract in `/api/health/detailed` as validated by `check_hosted_readiness.py`.
- **Security & Locks**:
  - Double-check lock state validity at the reset mutation boundary.
  - Implement a deterministic 30-second ceiling on lock reacquisition.
  - Redact client_secret/session_token/etc. in logging and secure canonical audit keys (`request_id`, etc.) from overrides.
  - Enforce ge/le validation limits in Pydantic pagination schema models.
  - Propagate `HTTPException` safely in metrics routes.
- **Test Hardening**:
  - Add edge case assertions for 10% and 30% density thresholds.
  - Assert deprecated density fields are absent from JSON payloads.
  - Query rebuild jobs route through `TestClient`.
  - Prevent DB session leaks with context managers and `try...finally` in persistence tests.

### Out of Scope

- Modifying database schemas or rewriting core React hooks.

### Files Expected to Change

- `docs/tech_spec.md`, `tech_spec.md`
- `docs/roadmap/enterprise-readiness-roadmap.md`
- `docs/runbooks/backup-restore-dr.md`
- `.github/ISSUE_TEMPLATE/*`
- `src/logic/recovery_gate.py`
- `src/data/distributed_lock.py`
- `api/auth.py`, `api/api_models.py`, `api/routers/metrics.py`
- `tests/unit/test_distributed_lock_runtime.py`
- `tests/*` (various unit and integration tests)

## Triage Data

- **Upstream Source**: FastAPI startup lifespan, Vercel deployments, and the Reconciliation Engine.
- **Downstream Impact**: Eliminates potential memory/engine leaks on test runs, guarantees robust lock expiry/rebuild safety, and ensures audit logs are tamper-proof.
- **Failure Mode**: Lock reacquisition timeout raises `LockAcquisitionTimeout` within 30s. Lock loss during reset raises `ExecutionBlockedError`, keeping the DB in a clean state.

## Validation Commands

```bash
# Run all backend Python tests
pytest

# Verify pre-commit hooks pass
pre-commit run --all-files
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective.
- [x] All backend unit/integration tests pass cleanly.
- [x] Code conforms to Stage 5C safety constraints.

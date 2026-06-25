# Enterprise Readiness PR Plan

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Date:** 2026-06-18
**Purpose:** Convert the readiness roadmap into a sequenced implementation plan with concrete PR boundaries

## Plan Principles

- One primary decision per PR.
- Preserve SQLite compatibility until a later explicit migration PR.
- Treat durable graph persistence as the gating dependency for restart, promotion, and DR work.
- Keep production architecture centered on FastAPI + Next.js.
- Verify each step with focused tests before widening scope.
- Keep governed rebuild/recovery/persistence behaviour aligned with `docs/governance/state-machine-and-operating-authority.md`.

## PR 1 — Durable Graph Persistence Schema and Repositories

**Primary objective:** Introduce the durable graph persistence boundary without wiring startup behavior yet.

**Scope**

- implement or extend persistence models for assets, relationships, and graph-build tracking;
- add repository abstractions for durable graph writes and reads;
- preserve SQLite compatibility;
- add tests for repository behavior and schema invariants.

**Out of scope**

- startup load/save integration;
- readiness gate changes;
- API shape changes;
- DR or restore runbooks.

**Files likely to change**

- `src/data/repository.py`
- `src/data/db_models.py`
- `src/data/migrations.py`
- `src/logic/asset_graph.py` or adjacent persistence helpers
- `tests/unit/*persistence*`
- `tests/integration/*persistence*`

**Validation**

- `pytest tests/unit -k persistence -v`
- `pytest tests/integration -k persistence -v`
- `python -m compileall src api`

## PR 2 — Startup Load / Save Integration

**Primary objective:** Make persisted graph truth participate in startup and rebuild lifecycle.

**Scope**

- load durable graph state during startup when present and valid;
- persist rebuilt graph state through the new repository boundary;
- record startup source / fallback behavior in observability;
- ensure restart semantics are visible and deterministic.

**Out of scope**

- promotion gate enforcement changes;
- contract cleanup;
- multi-region or distributed hosting policy;
- DR procedures.

**Files likely to change**

- `api/app_factory.py`
- `api/graph_lifecycle_providers.py`
- `api/main.py`
- `src/data/repository.py`
- `src/logic/rebuild_executor.py` or related lifecycle helpers
- `tests/unit/test_app_factory.py`
- `tests/integration/*startup*`

**Validation**

- `pytest tests/unit/test_app_factory.py -v`
- `pytest tests/integration -k startup -v`
- `pytest tests/integration -k persistence -v`

## PR 3 — Durable Promotion Gate Extension

**Primary objective:** Require durable graph evidence for staging/production promotion.

**Scope**

- extend hosted readiness checks to prove persisted graph load;
- add durable promotion criteria to deployment docs and smoke checks;
- ensure bounded health does not imply durable graph truth.

**Out of scope**

- graph schema changes;
- startup lifecycle changes;
- API contract refactors;
- restore tooling.

**Files likely to change**

- `docs/enterprise-deployment-operating-model.md`
- `docs/adr/0002-hosted-deployment-and-persistence.md`
- `scripts/check_hosted_readiness.py`
- `.github/workflows/hosted-readiness.yml`
- `README.md`

**Validation**

- `python scripts/check_hosted_readiness.py <base_url> --timeout 10`
- `pytest tests/unit -k readiness -v`

## PR 4 — API Contract Cleanup

**Primary objective:** Remove ambiguity from externally consumed API contracts.

**Scope**

- normalize density semantics end-to-end;
- formalize visualization payload types;
- decide pagination contract for assets and align frontend/backend behavior;
- update affected tests and types together.

**Out of scope**

- persistence behavior;
- startup lifecycle;
- deployment policy;
- security automation.

**Files likely to change**

- `api/api_models.py`
- `api/routers/metrics.py`
- `api/routers/visualization.py`
- `frontend/app/types/api.ts`
- `frontend/app/components/MetricsDashboard.tsx`
- `frontend/app/lib/assetHelpers.ts`
- `tests/unit/test_api_main.py`
- `frontend/__tests__/*`

**Validation**

- `pytest tests/unit/test_api_main.py -v`
- `cd frontend && npm test`
- `cd frontend && npm run lint`

## PR 5 — Recovery-Plane Completion

**Primary objective:** Finish the remaining control-plane integration around reconciliation and recovery.

**Scope**

- integrate reconciliation plan consumption into `RecoveryGate`;
- add or refine periodic reconciliation behavior if still warranted;
- tighten recovery-path tests and invariants.

**Out of scope**

- persistence schema changes;
- API contract changes;
- deployment promotion changes.

**Files likely to change**

- `src/logic/recovery_gate.py`
- `src/logic/reconciliation_engine.py`
- `src/logic/reconciliation_loop.py`
- `tests/unit/*recovery*`
- `tests/integration/*recovery*`

**Validation**

- `pytest tests/unit -k recovery -v`
- `pytest tests/integration -k recovery -v`

## PR 6 — Distributed Hosting Semantics Spec

**Primary objective:** Define and document multi-instance behavior for rebuild, restart, and lock ownership.

**Scope**

- specify single-writer / multi-reader assumptions;
- document split-brain handling and stale-owner mutation rules;
- define restart/redeploy interaction with in-flight rebuilds;
- map operational expectations into testable invariants.

**Out of scope**

- production code changes unless needed to align docs with behavior;
- persistence schema changes;
- frontend changes.

**Files likely to change**

- `docs/enterprise-deployment-operating-model.md`
- `docs/adr/*`
- `docs/testing/*`
- `docs/audits/*`

**Validation**

- ADR 0004 reviewed against ADR 0002 and ADR 0003
- enterprise operating model includes distributed hosting semantics
- testable invariants section maps directly to PR 7
- no production code changes included

## PR 7 — Failure-Mode and Scale Validation

**Primary objective:** Prove the system behaves correctly under restart, crash, and larger-graph conditions.

**Scope**

- add crash, lock-loss, fresh-owner, stale-owner, and restart-during-live-rebuild tests;
- add representative-scale persistence round-trip and rebuild persistence checks;
- record non-SLO baseline timings for persisted load and rebuild paths;
- document tested invariants and deferred validation work.

**Out of scope**

- architecture changes;
- persistence schema changes;
- frontend behavior changes;
- distributed schedulers, queues, or new rebuild endpoints;
- multi-region claims;
- DR/backup runbooks.

**Files likely to change**

- `tests/integration/test_distributed_hosting_failure_modes.py`
- `tests/integration/test_graph_persistence_scale_validation.py`
- `tests/helpers/graph_scale_factory.py`
- `docs/testing/failure-mode-and-scale-validation.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`
- `docs/roadmap/enterprise-readiness-pr-plan.md`
- `docs/audits/enterprise-readiness-audit.md`

**Validation**

- `pytest tests/integration/test_distributed_hosting_failure_modes.py -q`
- `pytest tests/integration/test_graph_persistence_scale_validation.py -q`
- `pytest tests/unit/test_recovery_gate.py -q`
- `pytest tests/integration/test_graph_rebuild_persistence.py -q`
- `pytest tests/integration/test_hosted_graph_startup_readiness.py -q`
- `python -m compileall src api tests`

## PR 8 — Security and Governance Hardening

**Primary objective:** Convert security and governance from broad coverage into enforceable operating policy.

**Scope**

- define release provenance and artifact-integrity expectations;
- formalize secret rotation / leak response expectations;
- add authorization-failure or sensitive-event audit logging where needed;
- clarify approval / exception workflows.

**Out of scope**

- graph persistence implementation;
- API contract cleanup;
- rebuild logic changes.

**Files likely to change**

- `SECURITY.md`
- `docs/GOVERNANCE.md`
- `api/auth.py`
- `api/routers/auth.py`
- `monitoring/alerts/loki-recording.yml`
- `.github/workflows/docker-publish.yml`
- `tests/unit/test_auth_security_events.py`
- `tests/unit/test_auth_router_audit_logging.py`
- `tests/unit/test_loki_recording_rules.py`
- `docs/audits/enterprise-readiness-audit.md`
- `docs/roadmap/enterprise-readiness-pr-board.md`
- `docs/roadmap/enterprise-readiness-pr-plan.md`

**Validation**

- `pytest tests/unit/test_auth_security_events.py -q`
- `pytest tests/unit/test_auth_router_audit_logging.py -q`
- `pytest tests/unit/test_loki_recording_rules.py -q`
- workflow YAML parse validation
- `python -m compileall api src tests`

## PR 9 — Backup, Restore, and DR Runbook

**Primary objective:** Close the remaining enterprise recovery gap.

**Scope**

- define backup schedule and retention;
- define restore procedure and verification;
- document RPO / RTO assumptions;
- define operator ownership and escalation.

**Out of scope**

- core product features;
- contract cleanup;
- observability refactors.

**Files likely to change**

- `docs/enterprise-deployment-operating-model.md`
- `docs/runbooks/*`
- `docs/audits/*`

**Validation**

- tabletop restore review
- documented restore rehearsal

## PR C — Governance and State-Machine Hardening

**Primary objective:** Establish one canonical current authority for rebuild/recovery/persistence state machines, invariants, operator ownership, exception paths, and PR scope triggers.

**Scope**

- create `docs/governance/state-machine-and-operating-authority.md`;
- cross-link the spec from release, deployment, governance, ADR, index, audit, roadmap, and validation docs;
- mark the formal state-machine documentation gap as resolved;
- add PR-template and scope-guardrail triggers requiring the canonical spec to be updated when governed behaviour changes.

**Out of scope**

- runtime behavior changes;
- backup schedule, retention, RPO/RTO, or restore-procedure changes already covered by PR 9;
- new lock algorithms, persistence schemas, hosted readiness logic, or rebuild endpoints.

**Files likely to change**

- `docs/governance/state-machine-and-operating-authority.md`
- `docs/release-checklist.md`
- `docs/enterprise-deployment-operating-model.md`
- `docs/GOVERNANCE.md`
- `docs/adr/*`
- `docs/audits/*`
- `docs/roadmap/*`
- `docs/PR_SCOPE_GUARDRAILS.md`
- `.github/pull_request_template.md`
- `.github/PULL_REQUEST_TEMPLATE/*`

**Validation**

- documentation-only review
- manual link verification
- verify no PR 9 DR procedure content is duplicated or contradicted

## Sequencing Notes

- PR 1 is the gating dependency for PR 2, PR 3, PR 7, and PR 9.
- PR 2 must land before any restart or promotion proof can be trusted.
- PR 4 should land before frontend/API assumptions diverge further.
- PR 8 can start earlier as documentation and workflow hardening, but enforcement should align with the release process.
- PR C is the current governance authority companion to PR 6/PR 8/PR 9 and must remain documentation-only unless a later PR explicitly changes runtime behaviour.

# Enterprise Release Checklist

**Date:** 2026-06-18
**Purpose:** Define exit criteria for promoting the FastAPI + Next.js production stack toward enterprise deployment

## Release Scope

This checklist applies to the production architecture only:

- FastAPI backend in `api/`
- Next.js frontend in `frontend/`

It does not apply to the Gradio demo path in `app.py`.

## Release Gates

Run **Release Evidence Verify** (`.github/workflows/release-evidence-verify.yml`) as the reproducible mechanism for
executing automated gate evidence and generating the release-evidence artifact + gate summary for the selected release
commit.

For the auditable evidence matrix, targeted validation commands, workflow evidence, and manual artifacts for these
gates, see the [Release Evidence Pack](release-evidence-pack.md).

### 1. Architecture Gate

**Exit criteria**

- Production scope remains FastAPI + Next.js only.
- No release artifact depends on the Gradio UI for production behavior.
- Any deployment documentation matches the declared production architecture.

### 2. Durable Persistence Gate

**Exit criteria**

- Durable graph persistence is implemented and exercised through repository abstractions.
- Startup can load persisted graph state when present.
- Persisted graph state can be written and read back without loss of required graph truth.
- SQLite compatibility remains intact for local development and tests.

### 3. Restart / Reload Gate

**Exit criteria**

- A backend restart after persistence does not silently fall back to an unverified graph state.
- Startup logs or observability clearly identify whether graph state came from persistence, cache, or rebuild.
- Restart / reload behavior is covered by automated tests.

### 4. Promotion Gate

**Exit criteria**

- Hosted readiness proves more than bounded health; it must prove durable graph evidence for staging and production.
- Promotion requires an explicit durable graph-persistence smoke procedure.
- A basic health check alone is not accepted as production proof.
- Staging promotion follows the [Staging Deployment Operating Baseline](staging-deployment-operating-baseline.md).

### 5. API Contract Gate

**Exit criteria**

- Density semantics are consistent across backend and frontend.
- Visualization payload types are explicit and testable.
- Asset listing behavior is either paginated everywhere or clearly non-paginated everywhere.

### 6. Recovery / Rebuild Gate

**Exit criteria**

- RecoveryGate behavior is fully aligned with the canonical state-machine and operating authority in [docs/governance/state-machine-and-operating-authority.md](governance/state-machine-and-operating-authority.md), or any intentional deferral is explicitly documented.
- Rebuild cancellation, lock-loss, and stale-owner paths are tested.
- No stale owner can mutate rebuild state after a restart or lock loss.

### 7. Security Gate

**Exit criteria**

- Destructive rebuild endpoints remain operator-protected.
- Security automation covers dependency, code, and workflow risk surfaces.
- Secret handling and release provenance requirements are documented and enforced.
- Authorization failures are audited or explicitly justified if not logged.

### 8. Governance Gate

**Exit criteria**

- State-machine and recovery invariants are documented in the current authoritative spec: [docs/governance/state-machine-and-operating-authority.md](governance/state-machine-and-operating-authority.md).
- Operator ownership for deploy, rollback, restore, and persistence verification is explicit.
- Exception handling and manual override paths are documented.
- PR scope guardrails are followed for release-bound changes.

### 9. Disaster Recovery Gate

**Exit criteria**

- Backup and restore procedure exists: satisfied by [docs/runbooks/backup-restore-dr.md](runbooks/backup-restore-dr.md).
- RPO and RTO are defined: satisfied by [ADR 0005](adr/0005-backup-restore-dr-strategy.md).
- Rollback is distinguished from data restore: satisfied by the [Enterprise Deployment Operating Model](enterprise-deployment-operating-model.md#disaster-recovery).
- Restore has been rehearsed at least once: manual operator verification required before final enterprise release sign-off.

## Release Exit Criteria Summary

A release may be treated as enterprise-ready only when all of the following are true:

- durable graph persistence is implemented and restart-tested;
- promotion requires durable graph evidence;
- core API contracts are explicit and stable;
- rebuild/recovery behavior is deterministic under failure;
- security and governance controls are enforceable;
- DR / restore is documented and rehearsed in practice.

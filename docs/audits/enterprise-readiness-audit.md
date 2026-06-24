# Enterprise Production and Deployment Readiness Audit

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Date:** 2026-06-24
**Scope:** Production architecture readiness for FastAPI backend + Next.js frontend
**Status:** Partial — durable core (PR 1–3) is implemented and enforced, with contract, validation, and governance hardening still in progress

## Executive Summary

The repository has made substantial progress toward enterprise readiness. Observability/SLOs are implemented, rebuild coordination is hardened, operator-only rebuild authorization exists, and the repo contains explicit production-architecture and hosted-deployment policy docs.

The remaining risk is concentrated in validation, contract, and governance layers:

- durable graph persistence (PR 1), startup load/save integration (PR 2), and durable promotion gate extension (PR 3) are implemented and enforced; broader validation evidence continues for failure-mode and operational scenarios;
- validation and contract hardening remain incomplete in a few user-facing surfaces;
- distributed hosting semantics need a stronger operating model;
- CI/CD and security automation require further hardening before this should be treated as enterprise-grade production.

## Post-Roadmap Reconciliation Status

Roadmap source-of-truth status (aligned with `docs/roadmap/enterprise-readiness-roadmap.md` and `docs/roadmap/enterprise-readiness-pr-board.md`):

| PR / Roadmap Item | Reconciled Status |
| --- | --- |
| PR 1 — Durable Graph Persistence Schema and Repositories | implemented and enforced |
| PR 2 — Startup Load / Save Integration | implemented and enforced |
| PR 3 — Durable Promotion Gate Extension | implemented and enforced |
| PR 4 — API Contract Cleanup | still missing |
| PR 5 — Recovery-Plane Completion | implemented but weakly validated |
| PR 6 — Distributed Hosting Semantics Spec | documented only |
| PR 7 — Failure-Mode and Scale Validation | implemented but weakly validated |
| PR 8 — Security and Governance Hardening | implemented but weakly validated |
| PR 9 — Backup, Restore, and DR Runbook | documented only |

## Readiness Matrix

| Area | Current State | Evidence | Risk | Next PR / Action |
| --- | --- | --- | --- | --- |
| Production architecture | Implemented as policy | `docs/adr/0001-production-architecture.md`, `README.md` | Low | Keep all new production work on FastAPI + Next.js |
| Observability & SLOs | Implemented | `docs/OBSERVABILITY_MASTER_SPEC.md`, `docs/OBSERVABILITY_README.md`, `api/metrics.py` | Low | Add operational drills to prove the alerts answer real incidents |
| Startup tracing / request correlation | Implemented | `api/app_factory.py`, `src/observability/*` | Low | Validate trace continuity across startup/rebuild/restart paths |
| Rebuild coordination | Implemented and hardened | `src/logic/rebuild_executor.py`, `src/logic/recovery_gate.py`, `src/logic/reconciliation_loop.py`, `docs/adr/0003-distributed-lock-refresh-and-heartbeat-strategy.md` | Medium | Prove restart, stale-owner, and lock-loss behavior in PR 7 |
| Operator rebuild authorization | Implemented; audit logging in progress | `api/auth.py`, `docs/audits/OPERATOR_REBUILD_AUTHORIZATION_AUDIT.md` | Low | Complete PR 8 sensitive auth-event audit logging |
| Hosted readiness smoke checks | Implemented with durable-persistence promotion checks | `.github/workflows/hosted-readiness.yml`, `scripts/check_hosted_readiness.py`, `docs/enterprise-deployment-operating-model.md` | Medium | Keep smoke assertions aligned with the durable promotion policy and expand evidence where needed |
| Durable graph persistence | Implemented and enforced | `api/graph_lifecycle_providers.py`, `api/graph_lifecycle.py`, `docs/adr/0002-hosted-deployment-and-persistence.md`, `docs/graph-persistence-design.md` | Medium | Expand failure-mode/load evidence and DR rehearsal coverage around the persisted graph path |
| Restart / reload semantics | Implemented; broader validation in progress | `api/app_factory.py`, `api/graph_lifecycle.py`, `docs/enterprise-deployment-operating-model.md`, `docs/testing/failure-mode-and-scale-validation.md` | Medium | Extend restart, redeploy, and stale-owner validation coverage under PR 7 follow-on work |
| Distributed hosting semantics | Documented; validation in progress | `docs/adr/0004-distributed-hosting-semantics.md`, `docs/enterprise-deployment-operating-model.md`, `docs/testing/distributed-hosting-invariants.md`, `docs/testing/failure-mode-and-scale-validation.md` | Medium | Complete PR 7 focused validation and keep broader production-scale testing out of scope |
| Validation / contracts | Partially hardened | `docs/phase-3-computation-layout-boundary-audit.md` | Medium | Remove density/pagination/schema ambiguity in API and frontend contracts |
| CI/CD | Mature baseline, but not enterprise-complete | `.github/workflows/ci.yml`, `.github/workflows/ci-gate-spec.yaml`, `.github/workflows/codeql.yml`, `.github/workflows/hosted-readiness.yml` | High | Tighten promotion gates, keep durable-storage and restart checks enforced and evidence-backed, enforce release discipline |
| Security automation | Broad coverage; provenance/SBOM hardening in progress | `.github/workflows/*`, `SECURITY.md`, `docs/ENV_ACCESS_AUDIT.md`, `docs/audits/OPERATOR_REBUILD_AUTHORIZATION_AUDIT.md` | High | Complete PR 8 SBOM workflow and auth-audit policy |
| Governance / operating model | Explicit governance policy in progress | `.github/PULL_REQUEST_TEMPLATE/*`, `docs/GOVERNANCE.md`, `docs/enterprise-deployment-operating-model.md` | Medium | Complete approval, exception, and release governance documentation |

## What Has Been Done

### 1. Production control plane is real

The repo now has several enterprise-grade control-plane components:

- production architecture is explicitly declared as FastAPI + Next.js;
- SLOs and observability are documented as implemented;
- startup tracing and structured observability events exist;
- rebuild execution is separated from reconciliation plan generation;
- distributed lock refresh and heartbeat logic are defined and tested;
- operator-only authorization protects destructive rebuild endpoints.

### 2. Deployment policy exists

The enterprise operating model clearly distinguishes:

- local development;
- preview deployments;
- staging;
- production.

It also defines a basic readiness gate versus a durable graph-persistence gate, which is the right direction for production promotion discipline.

### 3. Documentation is unusually strong

This repo already contains the right documents for a mature program:

- ADRs for architecture and hosted persistence;
- observability master/spec docs;
- persistence design docs;
- readiness risk audits;
- PR templates and scope guardrails;
- operator authorization audit/quick reference.

That means the missing work is not “figuring out the architecture.” It is executing the remaining implementation and enforcement work.

## What Is Planned

### 1. Durability validation and restore evidence

The clearest remaining work after the merged durability PRs is to prove and operationalize the persisted graph path already described in `docs/graph-persistence-design.md` and `docs/adr/0002-hosted-deployment-and-persistence.md`:

- restart/redeploy and stale-owner validation around persisted graph load/save behavior;
- durable promotion evidence that continues to verify persisted graph assertions, not just bounded health;
- restore rehearsal evidence against the implemented persistence path;
- continued SQLite compatibility for local development and PostgreSQL-backed hosted durability.

### 2. Recovery-plane validation

RecoveryGate is the plan-consumption boundary for rebuild recovery decisions,
and periodic reconciliation may consume RecoveryGate-approved plans. The
remaining work is validation, not semantic definition:

- restart and redeploy behavior under in-flight rebuilds;
- stale-owner recovery after lock expiry;
- lock-loss abort behavior before persistence or success marking;
- split-brain/manual-intervention paths.

### 3. Hosting and promotion hardening

`docs/enterprise-deployment-operating-model.md` already defines:

- deployment rollback boundaries;
- durable graph-persistence smoke procedure;
- operator ownership of rollback and persistence verification;
- Stage 7 backup/restore deferral.

That is a useful baseline, but it still needs broader validation-backed enforcement and release evidence.

## What Is Not Yet Planned, But Should Be

### 1. Formal state-machine governance

The repo should define one canonical state-machine/invariant document for rebuild coordination and recovery. It should state:

- allowed and forbidden transitions;
- terminal states;
- ownership rules;
- stale-write prevention rules;
- exact recovery authority and exception handling.

### 2. Disaster recovery and restore

The repo acknowledges restore as deferred, but enterprise readiness requires explicit planning for:

- RPO / RTO targets;
- backup schedule and retention;
- restore validation;
- schema rollback vs data restore;
- operator escalation path during failed restore.

### 3. Multi-instance and split-brain semantics

Distributed hosting semantics are documented through
`docs/adr/0004-distributed-hosting-semantics.md`. The system is specified as
single-writer / multi-reader: multiple backend instances may serve reads, but
only one rebuild writer may hold the `graph_rebuild` lock and persist graph
truth per graph persistence boundary.

Remaining proof work is deferred to PR 7 failure-mode and scale validation.
That PR should convert the invariants in
`docs/testing/distributed-hosting-invariants.md` into restart, stale-owner,
lock-loss, hosted-readiness, and concurrency tests.

### 4. Security and supply-chain automation

The repo has broad scanner coverage, but enterprise hardening should still add policy and enforcement for:

- dependency pin review;
- transitive vulnerability response;
- secret rotation and leak response;
- release provenance / artifact integrity;
- authorization-failure audit logging;
- periodic review of privileged endpoints.

### 5. API contract hardening

The phase-3 boundary audit shows user-facing contract drift that should be resolved:

- density unit semantics need to be explicit end-to-end;
- pagination expectations should be consistent;
- visualization payloads should be strongly modeled rather than `dict[str, Any]`;
- derived metrics should be consistently owned by either the graph engine or the API contract.

### 6. Load / scale validation

PR 7 adds representative-scale SQLite validation for deterministic 250/1,000 and 1,000/5,000 graph snapshots, plus
bounded startup-load and rebuild-persist timing tripwires. The repo still needs later production-scale evidence for:

- rebuild duration under stress;
- lock refresh timing under load;
- memory growth during large graph rebuilds;
- persistence load and startup replay cost beyond representative CI fixtures;
- CI coverage against larger production-like graph sizes.

## Risk Assessment

### High risk

- distributed hosting semantics are not yet fully specified in execution terms;
- CI/CD still relies on policy and workflows more than on broadly proven promotion evidence;
- security automation is broad but not yet enterprise-complete.

### Medium risk

- API contract drift around density, pagination, and visualization typing;
- recovery-plane integration still has deferred pieces;
- governance exists in docs, but not all of it is operationalized.

### Low risk

- observability and SLO instrumentation are solid;
- rebuild authorization is implemented and audited;
- production architecture is clearly declared;
- runtime settings centralization is in place for the main supported seams.

## Recommended Next PR Sequence

1. **API contract cleanup PR**
   - normalize density semantics;
   - formalize visualization models;
   - remove pagination ambiguity.
2. **Failure-mode and scale validation follow-up**
   - expand restart/reload, crash, and stale-owner validation around the implemented persistence path;
   - keep durable promotion evidence tied to persisted graph behavior.
3. **Security/governance hardening PRs**
   - add failure audit logging, restore policy, and supply-chain enforcement;
   - document operational ownership and escalation paths.
4. **Restore rehearsal and DR evidence follow-up**
   - execute and record restore rehearsal against the implemented persistence layer;
   - keep operator runbooks and release evidence aligned.

## Conclusion

The repo is beyond "prototype" stage and has several enterprise-grade control-plane capabilities already in place, including the implemented and enforced durability and promotion path (PR 1–3). The remaining gaps are contract hardening (PR 4), broader validation evidence around failure-mode, restart, and scale scenarios, and the governance and security automation maturity required to call this fully enterprise-production-ready.

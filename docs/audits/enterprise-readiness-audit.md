# Enterprise Production and Deployment Readiness Audit

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Date:** 2026-06-18
**Scope:** Production architecture readiness for FastAPI backend + Next.js frontend
**Status:** Partial — strong control-plane maturity, incomplete durability and promotion hardening

## Executive Summary

The repository has made substantial progress toward enterprise readiness. Observability/SLOs are implemented, rebuild coordination is hardened, operator-only rebuild authorization exists, and the repo contains explicit production-architecture and hosted-deployment policy docs.

The remaining risk is concentrated in the durability and promotion layers:

- durable graph persistence is designed but not fully operationalized;
- startup/load/restart semantics still need a complete implementation path;
- validation and contract hardening remain incomplete in a few user-facing surfaces;
- distributed hosting semantics need a stronger operating model;
- CI/CD and security automation require further hardening before this should be treated as enterprise-grade production.

## Readiness Matrix

| Area | Current State | Evidence | Risk | Next PR / Action |
| --- | --- | --- | --- | --- |
| Production architecture | Implemented as policy | `docs/adr/0001-production-architecture.md`, `README.md` | Low | Keep all new production work on FastAPI + Next.js |
| Observability & SLOs | Implemented | `docs/OBSERVABILITY_MASTER_SPEC.md`, `docs/OBSERVABILITY_README.md`, `api/metrics.py` | Low | Add operational drills to prove the alerts answer real incidents |
| Startup tracing / request correlation | Implemented | `api/app_factory.py`, `src/observability/*` | Low | Validate trace continuity across startup/rebuild/restart paths |
| Rebuild coordination | Implemented and hardened | `src/logic/rebuild_executor.py`, `src/logic/recovery_gate.py`, `src/logic/reconciliation_loop.py`, `docs/adr/0003-distributed-lock-refresh-and-heartbeat-strategy.md` | Medium | Prove restart, stale-owner, and lock-loss behavior in PR 7 |
| Operator rebuild authorization | Implemented | `api/auth.py`, `docs/audits/OPERATOR_REBUILD_AUTHORIZATION_AUDIT.md` | Low | Add failure auditing if operator denials matter operationally |
| Hosted readiness smoke checks | Implemented | `.github/workflows/hosted-readiness.yml`, `scripts/check_hosted_readiness.py` | Medium | Extend smoke checks to assert durable graph persistence, not just bounded health |
| Durable graph persistence | Designed, not fully implemented | `docs/adr/0002-hosted-deployment-and-persistence.md`, `docs/graph-persistence-design.md` | High | Implement schema/repository/save-load/startup integration PRs |
| Restart / reload semantics | Planned, not completed | `docs/graph-persistence-design.md`, `docs/enterprise-deployment-operating-model.md` | High | Add startup load-from-persistence and post-restart verification paths |
| Distributed hosting semantics | Documented | `docs/adr/0004-distributed-hosting-semantics.md`, `docs/enterprise-deployment-operating-model.md`, `docs/testing/distributed-hosting-invariants.md` | Medium | Prove semantics in PR 7 failure-mode and scale validation |
| Validation / contracts | Partially hardened | `docs/phase-3-computation-layout-boundary-audit.md` | Medium | Remove density/pagination/schema ambiguity in API and frontend contracts |
| CI/CD | Mature baseline, but not enterprise-complete | `.github/workflows/ci.yml`, `.github/workflows/ci-gate-spec.yaml`, `.github/workflows/codeql.yml`, `.github/workflows/hosted-readiness.yml` | High | Tighten promotion gates, add durable-storage and restart checks, enforce release discipline |
| Security automation | Broad coverage, still incomplete | `.github/workflows/*`, `docs/ENV_ACCESS_AUDIT.md`, `docs/audits/OPERATOR_REBUILD_AUTHORIZATION_AUDIT.md` | High | Add supply-chain, secret, dependency, and auth-audit automation policy |
| Governance / operating model | Good documentation, incomplete execution model | `.github/PULL_REQUEST_TEMPLATE/*`, `docs/enterprise-deployment-operating-model.md` | Medium | Create explicit approval/exception/runbook ownership and DR policy |

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

### 1. Durable graph persistence

The clearest planned work is in `docs/graph-persistence-design.md` and `docs/adr/0002-hosted-deployment-and-persistence.md`:

- normalized persistent graph storage;
- load/rebuild semantics from durable storage;
- atomic publish / latest-valid graph build records;
- SQLite compatibility for local development;
- PostgreSQL as the hosted durable target;
- repository boundaries for asset, relationship, regulatory-event, and graph-build state.

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

That is a useful baseline, but it still needs implementation-backed enforcement.

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

The repo still needs production-scale evidence for:

- rebuild duration under stress;
- lock refresh timing under load;
- memory growth during large graph rebuilds;
- persistence load and startup replay cost;
- CI coverage against representative graph sizes.

## Risk Assessment

### High risk

- durable graph persistence is not yet complete;
- restart/reload semantics are not yet proven end-to-end;
- distributed hosting semantics are not yet fully specified in execution terms;
- CI/CD still relies on policy and workflows more than on proven promotion gates;
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

1. **Graph persistence schema/repository PR**
   - implement durable graph storage primitives;
   - preserve SQLite compatibility;
   - add explicit persistence tests.
2. **Startup load/save integration PR**
   - wire persisted graph load into startup;
   - define fallback behavior when persistence is missing or invalid;
   - make restart semantics observable.
3. **Durable promotion gate PR**
   - extend readiness smoke checks to prove persisted graph load;
   - require restart/reload verification for staging/production promotion.
4. **API contract cleanup PR**
   - normalize density semantics;
   - formalize visualization models;
   - remove pagination ambiguity.
5. **Security/governance hardening PRs**
   - add failure audit logging, restore policy, and supply-chain enforcement;
   - document operational ownership and escalation paths.

## Conclusion

The repo is beyond “prototype” stage and has several enterprise-grade control-plane capabilities already in place. The remaining gap is not the existence of observability or rebuild coordination; it is the maturity of the persistence, restart, promotion, restore, and governance layers required to call this fully production-ready.

# Current state of FarDB

**Claim class:** CURRENT, with explicit limitations
**Evidence date:** 14 July 2026
**Repository baseline:** `main` at `2afe77212fba06b6556d38696a5323e55f04a35a`

## Executive statement

FarDB has progressed beyond an expendable graph demonstration into a financial relationship platform with durable
graph state, bounded production interfaces, controlled recovery and evidence-led release mechanisms.

The repository-level enterprise-readiness implementation is substantially complete. Final release status is
artefact-specific: the current enterprise-readiness index requires fresh target-environment, security, operator and
recovery evidence for the release under consideration. A prior RC1 evidence record reports a passed hosted
persistence check and restore rehearsal, but that record does not prove the later `2afe7721` baseline.

FarDB is not production-scale certified and has not yet demonstrated multi-domain reuse without core changes. Those
are central next proofs.

## Current production path

| Layer | Reviewed baseline | Qualification |
| --- | --- | --- |
| Product experience | Next.js | Declared production UI path. |
| Application and API | FastAPI | Declared production backend path. |
| Hosted persistence target | PostgreSQL | Durable hosted target. |
| Local compatibility | SQLite | Local development and test path retained. |
| Research and demo UI | Gradio | Non-production runtime surface; shared dependency manifests still install it. |
| Delivery gates | GitHub Actions and evidence workflows | Repository proof and hosted proof remain distinct. |

See [ADR 0001](../adr/0001-production-architecture.md),
[ADR 0002](../adr/0002-hosted-deployment-and-persistence.md) and the
[enterprise-readiness index](../enterprise-readiness-index.md).

## Implemented foundations

### Durable graph truth

- Graph state has a durable persistence path rather than being only a disposable visualisation cache.
- Readiness can distinguish ordinary service health from persisted startup evidence.
- Startup provenance identifies whether persisted state was loaded.
- Application/auth data, graph truth and coordination state have documented logical boundaries.

### Recovery control plane

- Database-backed recovery authority.
- Lease and lock ownership with heartbeat and freshness handling.
- Fencing against stale writers.
- RecoveryGate, reconciliation and fail-closed safety paths.

The [state-machine and operating authority](../governance/state-machine-and-operating-authority.md) is canonical for
these behaviours.

### Product and API boundaries

- Backend and frontend contracts cover graph density, pagination, truncation and visualisation seams.
- FastAPI and Next.js are deliberately the production stack.
- Gradio is isolated as a demo and internal-testing interface.

### Release and operational mechanisms

- Strict readiness and release-evidence definitions.
- Named operator sign-off requirements bound to objective artefacts.
- Backup, restore and disaster-recovery procedures.
- CI coverage for tests, builds, security and deployment checks.
- ADR, scope-control and additive architecture-memory disciplines.

## Evidence achieved for an identified earlier candidate

The [RC1 evidence record](../evidence-records/rc1-objective-2-follow-up.md) reports a staging hosted-readiness pass,
persisted startup, 19 assets, 73 relationships, clean release-scanner outcomes, named approval and a passed restore
rehearsal on 29 June 2026.

This is meaningful operational evidence for that identified candidate. It is not a capacity certificate, independent
assurance or proof for every later commit. The current
[enterprise-readiness index](../enterprise-readiness-index.md) correctly preserves fresh-evidence requirements for
subsequent release sign-off.

## What is not yet proven

### Capacity and operating envelope

- Million-node or million-edge behaviour.
- Representative dense-subgraph rendering and API behaviour.
- Memory and database pressure under sustained production-shaped load.
- Rebuild duration at an approved scale.
- Lock timing, contention and recovery under realistic concurrency.
- A measured cost and scaling curve.

### Repeatability for the current release

- Repeated promotion of the same immutable artefact through staging and production.
- Consistent rollback and restoration time across multiple drills.
- Production-shaped evidence tied to the exact current release identity.

### Product generality

- A second domain implemented without changes to the canonical core.
- A stable domain-adapter SDK and conformance contract.
- Mature multi-tenant and jurisdictional isolation.
- A market-validated vertical beyond the financial implementation.

### Proposed target capabilities

- A proposition/evidence/assertion/determination/projection semantic model.
- Immutable `ResearchRun` records and a proposed-assertion workflow.
- Protected identity separation from pseudonymous decision graphs.
- Offline-first operational workflows and federated cross-organisation verification.
- Domain packs for biomedical research, patents, workforce, public benefits and other selected areas.

## Accurate present positioning

> FarDB is a financial relationship platform with durable graph persistence, controlled recovery, bounded FastAPI
> and Next.js product interfaces, and evidence-led release mechanisms. Capacity certification and domain-neutral
> reuse remain the next major proofs.

FarDB should not currently be described as:

- a general-purpose graph database competitor;
- a production-scale certified platform;
- a clinically validated research system;
- an autonomous decision platform;
- a generally adopted industry standard;
- a complete multi-domain commercial suite.

## Immediate evidence priorities

1. Reconcile release claims against the exact artefact being promoted.
2. Establish a measured capacity and resilience envelope.
3. Ratify the governed relationship-assertion contract before multi-domain implementation.

Feature expansion that bypasses these proofs increases backtracking and claim risk.

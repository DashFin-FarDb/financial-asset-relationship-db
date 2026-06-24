# Enterprise Readiness Remediation Roadmap

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Date:** 2026-06-24
**Format:** Now / Next / Later
**Purpose:** Sequence the remaining work needed to make the production stack operationally enterprise-grade

Status legend: **implemented and enforced**, **implemented but weakly validated**, **documented only**, **superseded**, **still missing**.

## Summary

The repo is not starting from zero. Observability, rebuild coordination, operator authorization, and the durable persistence/startup/promotion path are in place. The remaining roadmap is about closing contract gaps and turning the already-implemented durability and recovery path into broadly validated, operationally governed behavior.

## Now

Work that should be treated as the current focus because it closes the remaining high-priority gaps after the durability path landed.

| Item | Status | Why now | Dependencies |
| --- | --- | --- | --- |
| Durable graph persistence schema/repositories | implemented and enforced | This is the base layer for hosted durability and restart semantics | Current ORM/schema contract, SQLite compatibility rules, persistence design doc |
| Startup graph load/save integration | implemented and enforced | Restart/reload behavior cannot be validated until persisted graph load is wired into startup | Persistence schema/repositories, graph lifecycle providers |
| Durable promotion gate extension | implemented and enforced | Basic readiness is not enough for staging/production promotion | Startup persistence integration, hosted readiness workflow |
| API contract cleanup for density, pagination, visualization models | still missing | Contract ambiguity will create production drift and testing gaps | Boundary audit decisions, frontend and API type updates |

## Next

Work that should follow immediately after the base durability path is in place.

| Item | Status | Why next | Dependencies |
| --- | --- | --- | --- |
| RecoveryGate / reconciliation plan integration | implemented but weakly validated | Completes the control-plane model already introduced in docs | Reconciliation engine, rebuild executor behavior |
| Distributed hosting semantics spec | documented only | Needed to make multi-instance behavior explicit and safe | Durable graph persistence, lock strategy, restart semantics |
| Restart/redeploy failure-mode tests | implemented but weakly validated | Production confidence depends on proving stale-owner and crash recovery behavior | Startup integration, distributed coordination logic |
| Load and scale validation baseline | implemented but weakly validated | Enterprise readiness requires evidence under representative graph size | Durable persistence implementation, representative dataset |
| Security automation hardening | implemented but weakly validated | Current scanning is broad but not yet a complete security governance model | Repo-wide policy decisions, release process definition |

## Later

Important follow-on work that should be planned once the durable core is stable.

| Item | Status | Why later | Dependencies |
| --- | --- | --- | --- |
| Backup / restore runbook and DR testing | documented only | Explicitly deferred in the current operating model, but required for enterprise recovery readiness | Stable persistence layer, operator ownership model |
| Multi-region / advanced hosting strategy | still missing | Too early until single-region durable behavior is proven | Disaster recovery, promotion gates, cost model |
| Formal rebuild / recovery state-machine governance | implemented but weakly validated | The repo has enough logic to justify a canonical invariant spec | Recovery behavior stabilisation, operational ownership |
| Supply-chain provenance and release integrity controls | implemented but weakly validated | Should be built against a stable release process, not ad hoc | CI/CD hardening, artifact build strategy |
| Continuous operational drills | still missing | Needs production-like telemetry and stable runbooks first | Observability layer, alert routing, runbooks |

## Key Dependencies

- The durable graph persistence and startup integration path is now the base dependency for restart/reload validation, promotion evidence, and realistic DR testing.
- Contract cleanup should happen before more API consumers accumulate assumptions around the current ambiguous payload shapes.
- Failure-mode and scale validation should exercise the merged durability path before operators treat the current guarantees as fully proven.
- Security automation should be tied to release and promotion policy, otherwise it will remain scanner noise instead of governance.

## Risks

- If failure-mode validation slips, the repo may retain durability features that are present but not convincingly proven under restart and crash conditions.
- If contract cleanup is deferred too long, frontend and backend assumptions will diverge further.
- If governance and security hardening lag the implemented durability path, promotion discipline may stay policy-heavy instead of evidence-backed.

## Proposed Delivery Order

1. API contract cleanup
2. Recovery-plane completion
3. Distributed hosting semantics
4. Failure-mode and scale validation
5. Security and governance hardening
6. DR / restore evidence and rehearsal

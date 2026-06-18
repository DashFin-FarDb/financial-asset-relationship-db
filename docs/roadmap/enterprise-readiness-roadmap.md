# Enterprise Readiness Remediation Roadmap

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Date:** 2026-06-18
**Format:** Now / Next / Later
**Purpose:** Sequence the remaining work needed to make the production stack operationally enterprise-grade

## Summary

The repo is not starting from zero. Observability, rebuild coordination, and operator authorization are in place. The remaining roadmap is about making persistence, restart, promotion, restore, and governance behavior deterministic and provable.

## Now

Work that should be treated as the current focus because it unblocks production durability and promotion.

| Item | Status | Why now | Dependencies |
| --- | --- | --- | --- |
| Durable graph persistence schema/repositories | Not started | This is the base layer for hosted durability and restart semantics | Current ORM/schema contract, SQLite compatibility rules, persistence design doc |
| Startup graph load/save integration | Not started | Restart/reload behavior cannot be validated until persisted graph load is wired into startup | Persistence schema/repositories, graph lifecycle providers |
| Durable promotion gate extension | Not started | Basic readiness is not enough for staging/production promotion | Startup persistence integration, hosted readiness workflow |
| API contract cleanup for density, pagination, visualization models | Not started | Contract ambiguity will create production drift and testing gaps | Boundary audit decisions, frontend and API type updates |

## Next

Work that should follow immediately after the base durability path is in place.

| Item | Status | Why next | Dependencies |
| --- | --- | --- | --- |
| RecoveryGate / reconciliation plan integration | In progress / partial | Completes the control-plane model already introduced in docs | Reconciliation engine, rebuild executor behavior |
| Distributed hosting semantics spec | Not started | Needed to make multi-instance behavior explicit and safe | Durable graph persistence, lock strategy, restart semantics |
| Restart/redeploy failure-mode tests | Not started | Production confidence depends on proving stale-owner and crash recovery behavior | Startup integration, distributed coordination logic |
| Load and scale validation baseline | Not started | Enterprise readiness requires evidence under representative graph size | Durable persistence implementation, representative dataset |
| Security automation hardening | Not started | Current scanning is broad but not yet a complete security governance model | Repo-wide policy decisions, release process definition |

## Later

Important follow-on work that should be planned once the durable core is stable.

| Item | Status | Why later | Dependencies |
| --- | --- | --- | --- |
| Backup / restore runbook and DR testing | Deferred | Explicitly deferred in the current operating model, but required for enterprise recovery readiness | Stable persistence layer, operator ownership model |
| Multi-region / advanced hosting strategy | Not started | Too early until single-region durable behavior is proven | Disaster recovery, promotion gates, cost model |
| Formal rebuild / recovery state-machine governance | Not started | The repo has enough logic to justify a canonical invariant spec | Recovery behavior stabilisation, operational ownership |
| Supply-chain provenance and release integrity controls | Not started | Should be built against a stable release process, not ad hoc | CI/CD hardening, artifact build strategy |
| Continuous operational drills | Not started | Needs production-like telemetry and stable runbooks first | Observability layer, alert routing, runbooks |

## Key Dependencies

- Durable graph persistence is the gating dependency for restart/reload semantics, promotion gates, and realistic DR testing.
- Startup integration is the gating dependency for proving the system can recover from restarts without losing graph truth.
- Contract cleanup should happen before more API consumers accumulate assumptions around the current ambiguous payload shapes.
- Security automation should be tied to release and promotion policy, otherwise it will remain scanner noise instead of governance.

## Risks

- If persistence work slips, the repo remains preview-capable but not production-durable.
- If restart semantics are not tested immediately after persistence implementation, the team may ship an apparently working but non-recoverable graph lifecycle.
- If contract cleanup is deferred too long, frontend and backend assumptions will diverge further.

## Proposed Delivery Order

1. Persistence schema/repository layer
2. Startup load/save integration
3. Promotion gate extension
4. API contract cleanup
5. Recovery-plane completion
6. Distributed hosting semantics
7. Failure-mode and scale validation
8. Security and governance hardening
9. DR / restore runbook

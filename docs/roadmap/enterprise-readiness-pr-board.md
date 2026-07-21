# Enterprise Readiness PR Board

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Date:** 2026-06-25
**Format:** Release evidence board
**Purpose:** Track enterprise-readiness PR outcomes and the remaining release-evidence gates after PR #1287-#1301

Status legend follows the [Release Evidence Pack](../release-evidence-pack.md): **Satisfied - automated**, **Satisfied - documented**, **Satisfied - manual evidence required**, **Partially satisfied**, and **Blocked**.

## Implemented / Evidence-Backed Baseline

These PRs are no longer open remediation items. They form the repository baseline for release-candidate evidence capture.

| PR   | Title                                             | Status                               | Exit Criteria / Remaining Release Evidence                                                                                                                                                                                                     | Dependencies                                                                                              |
| ---- | ------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| PR 1 | Durable Graph Persistence Schema and Repositories | Satisfied - automated                | Durable graph persistence models and repositories exist; SQLite compatibility retained; persistence tests pass                                                                                                                                 | None, but it remains the base dependency for persistence, restart, promotion, validation, and DR evidence |
| PR 2 | Startup Load / Save Integration                   | Satisfied - automated                | Startup can load persisted graph state; rebuild path persists graph truth; restart behavior is observable and tested                                                                                                                           | PR 1                                                                                                      |
| PR 3 | Durable Promotion Gate Extension                  | Satisfied - manual evidence required | Hosted readiness supports durable graph proof; staging/prod still require attached `--require-persistence` smoke output                                                                                                                        | PR 1, PR 2, hosted target environment                                                                     |
| PR 4 | API Contract Cleanup                              | Satisfied - automated                | Density, asset pagination, visualization seams, and `RebuildJobListResponse` truncation semantics are aligned                                                                                                                                  | None                                                                                                      |
| PR 5 | Recovery-Plane Completion                         | Satisfied - automated                | RecoveryGate/reconciliation behavior is implemented and covered by focused recovery and lock tests                                                                                                                                             | PR 1, reconciliation/recovery code                                                                        |
| PR 6 | Distributed Hosting Semantics Spec                | Satisfied - documented               | Single-writer, split-brain, restart, and lock-loss semantics are documented and consolidated through the canonical state-machine authority                                                                                                     | PR 1, PR 2                                                                                                |
| PR 7 | Failure-Mode and Scale Validation                 | Partially satisfied                  | Restart, crash, stale-owner, lock-loss, and representative-scale evidence exists where covered; strict stale-owner restart composition is now covered and production-scale validation remains future/optional unless release scope requires it | PR 1, PR 2, distributed coordination fixtures                                                             |
| PR 8 | Security and Governance Hardening                 | Satisfied - manual evidence required | Security/governance controls are documented and tested where covered; release still requires scanner summary, exception handling, and maintainer approval records                                                                              | Governance policy, security workflows, release evidence pack                                              |
| PR 9 | Backup, Restore, and DR Runbook                   | Satisfied - manual evidence required | Backup/restore strategy and runbook exist; release sign-off still requires actual restore rehearsal and post-restore smoke evidence                                                                                                            | Stable persistence layer, restore operator, scratch/staging restore target                                |
| PR C | Governance and State-Machine Hardening            | Satisfied - documented               | Canonical state-machine authority exists and must be updated when governed behavior changes                                                                                                                                                    | PR 6, PR 8, review discipline                                                                             |

## Remaining Dedicated Follow-ups

These are not stale roadmap items; they are bounded follow-up objectives.

| Follow-up                                  | Status                               | Exit Criteria                                                                                                                                                                                                          | Do not bundle with                  |
| ------------------------------------------ | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| RC1 release evidence capture               | Satisfied - manual evidence required | CI run, hosted durable smoke, redacted health/assets output, scanner summary, and operator sign-off are attached for the release commit                                                                                | API or runtime changes              |
| Staging deployment operating baseline      | Satisfied - manual evidence required | Target environment, database boundaries, Vercel config, and durable graph store evidence are recorded without secrets                                                                                                  | DR restore implementation           |
| `RebuildJobListResponse` truncation signal | Satisfied - automated                | Response exposes `total` and `hasMore`; tests cover default cap, explicit pagination, and status-filtered truncation semantics; no frontend consumer was found                                                         | Release evidence capture            |
| Strict stale-owner restart composition     | Satisfied - automated                | End-to-end restart pipeline proves stale-owner reset after lock expiry, restart load, and prevents stale owner mutation                                                                                                | Source-of-truth docs reconciliation |
| Production-scale validation                | Partially satisfied                  | Larger graph/load evidence is recorded outside normal CI or in a bounded scheduled workflow                                                                                                                            | Core release evidence PR            |
| Continuous operational drills              | Satisfied - documented               | The operational drill pack defines graph load failure, lock loss, stale owner, degraded DB, and failed durable smoke flows with evidence capture guidance; the execution-record register captures actual run artifacts | Initial staging proof               |
| Objective 8                                | Partially satisfied                  | Release and Deployment Automation Layer: GitHub Actions is the canonical PR gate; heavyweight jobs shifted; production containers split; staging verification automated                                                | Stable CI platform, Docker          |

## Hardening backlog (P0–P3)

Canon IDs and automation mapping live in
[Release Evidence Pack — Hardening backlog](../release-evidence-pack.md#hardening-backlog-p0p3).
Do not reopen closed PR1–9 rows; track hardening here and in the evidence pack only.

| ID                | Status                                      | Exit criteria (short)                                                                           | Do not bundle with                     |
| ----------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------- |
| H-P0-01           | Satisfied - documented                      | Runbook/ADR table placement matches code (`rebuild_jobs` on Asset Graph; locks on coordination) | Runtime rebuild changes                |
| H-P0-02           | Satisfied - documented                      | Post-restore cleanup is table-scoped; job-boundary `running=0` before restart                   | Schema migrations                      |
| H-P0-03           | Satisfied - automated                       | `release-evidence-verify` with `hardening_tier=P0` fails on SKIPPED hosted readiness            | Soft rehearsal (`hardening_tier=none`) |
| H-P0-04           | Partially satisfied                         | DB authorization checker wired; redacted PASS attached for target env                           | Publishing live role/topology details  |
| H-P0-05           | Satisfied - documented                      | ADR 0002 / `.env.example` match runtime Postgres + recommended SQLite URL forms                 | Hosted infra changes                   |
| H-P0-06           | Satisfied - manual evidence required        | Fresh SHA-bound RC companion (RC1 not reused as CURRENT)                                        | Bundling unrelated product work        |
| H-P1-01           | Satisfied - automated                       | `--require-persistence` auto-enables `--assets-smoke` in hosted readiness                       | Empty persisted graphs fail promotion  |
| H-P1-02           | Satisfied - automated                       | `production-promotion.yml` twin of staging (prod Environment + persistence/assets smoke)        | Mixing with Docker/compose P1 work     |
| H-P1-03           | Satisfied - automated                       | `post-recovery-readiness.yml` mandatory re-smoke + context-named artifacts                      | Reusing promotion artifact names       |
| H-P1-04 … H-P1-06 | Partially satisfied / Satisfied - automated | See evidence pack                                                                               | Mixing P1 Docker work with P0 docs     |
| H-P2-01 … H-P2-05 | Partially satisfied                         | See evidence pack                                                                               | P0 gate wiring                         |
| H-P3-01 … H-P3-05 | Partially satisfied                         | See evidence pack                                                                               | P0/P1 release gates                    |

## Board Notes

- PR 1 and PR 2 remain the foundation for promotion, failure-mode, and DR evidence.
- PR 3 is implemented, but staging/production promotion remains a manual-evidence gate until hosted output is attached.
- PR 4 is no longer “still missing”; the rebuild job-list truncation signal is now covered by the dedicated API contract follow-up.
- PR 6 and PR C are no longer missing specifications; they are documented authorities that require review enforcement when governed behavior changes.
- PR 8 and PR 9 are documentation/test/policy complete for their repository scope, but release sign-off still requires scanner/exception evidence and restore rehearsal evidence.
- Production-scale validation should remain separately tracked so it does not blur release evidence capture with new runtime scope.
- The operational drill pack is now the canonical documentation for representative incident drills; the execution-record register is the separate follow-up artifact for actual run evidence.

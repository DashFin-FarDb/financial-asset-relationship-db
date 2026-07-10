# Enterprise Readiness Index

**Date:** 2026-06-25
**Purpose:** Single entry point for enterprise-readiness audit, roadmap, PR plan, release criteria, and release evidence

## What To Read

| Document                                                      | Purpose                                                                                                                    |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `docs/audits/enterprise-readiness-audit.md`                   | Full audit of what is implemented, evidence-backed, manually gated, and still deferred                                     |
| `docs/roadmap/enterprise-readiness-roadmap.md`                | High-level release-execution roadmap after the PR #1287-#1301 reconciliation point                                         |
| `docs/roadmap/enterprise-readiness-pr-plan.md`                | PR-by-PR execution plan with validation commands                                                                           |
| `docs/roadmap/enterprise-readiness-pr-board.md`               | Operational PR board with status and exit criteria                                                                         |
| `docs/release-checklist.md`                                   | Release gates and enterprise exit criteria                                                                                 |
| `docs/release-evidence-pack.md`                               | Gate-by-gate release evidence matrix, targeted commands, manual artefacts, and blocker rules                               |
| `docs/operations/operational-evidence-capture-framework.md`   | Canonical evidence grammar for classifying, redacting, and reviewing operational proof artifacts                           |
| `docs/testing/operational-drill-and-scale-validation-pack.md` | Operational drill matrix and bounded scale-validation guidance for observability, SLO, dashboard, alert, and runbook proof |
| `docs/governance/state-machine-and-operating-authority.md`    | Current operational authority for rebuild/recovery state machines, invariants, ownership, and exception paths              |
| `docs/adr/0006-release-and-deployment-automation.md`          | Release and Deployment automation strategy, GitHub actions constraints                                                     |
| `docs/adr/0005-backup-restore-dr-strategy.md`                 | Backup, restore, DR strategy, data classification, RPO, and RTO                                                            |
| `docs/runbooks/backup-restore-dr.md`                         | Operator procedures for backup verification, restore execution, and post-restore checks                                    |
| `docs/compound/INDEX.md`                                      | Additive architecture-expert compounded memory index (provisional vs landed)                                              |

## Executive Summary

The repository has moved from enterprise-readiness remediation into release-evidence execution.
The merged PR #1287-#1301 sequence means the durable persistence path, startup/reload integration,
durable promotion checker, API contract cleanup, recovery/governance hardening, failure-mode
validation, security/governance documentation, DR documentation, and release evidence pack are now
part of the repository baseline.

The remaining work is no longer primarily architectural. It is concentrated in live release evidence and bounded follow-up hardening:

- hosted promotion evidence showing durable graph truth in the target environment (coordinated via
  `.github/workflows/release-evidence-verify.yml` and attached target-environment outputs);
- DR restore rehearsal evidence against the documented backup/restore process;
- release-commit security scanner review and named operator sign-off (captured/reviewed via
  `.github/workflows/release-evidence-verify.yml` plus scanner workflows);
- strict stale-owner restart composition testing;
- the operational evidence-capture framework and drill pack for classifying operational proof;
- the operational drill and scale-validation pack for observability and runbook proof;
- production-scale validation and evidence-capture discipline for operational drills that stays bounded outside normal CI.

The DR documentation gap is closed at the strategy and runbook level through [ADR 0005](adr/0005-backup-restore-dr-strategy.md) and the [backup/restore/DR runbook](runbooks/backup-restore-dr.md). Final enterprise release readiness still requires operators to rehearse restore at least once and record the evidence in the release process.

## Roadmap Status Snapshot

Status legend follows the [Release Evidence Pack](release-evidence-pack.md): **Satisfied - automated**, **Satisfied - documented**, **Satisfied - manual evidence required**, **Partially satisfied**, and **Blocked**.

| Status                               | Current items                                                                                                                                                                                                                                                                                       |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Satisfied - automated                | PR 1 durable graph persistence; PR 2 startup load/save integration; PR 4 core density, asset pagination, and frontend/backend contract seams; PR 5 RecoveryGate/reconciliation control-plane path; PR 7 CI-bounded failure-mode and representative-scale validation where covered                   |
| Satisfied - documented               | PR 6 distributed hosting semantics; PR C governance/state-machine authority; production architecture and deployment operating model                                                                                                                                                                 |
| Satisfied - manual evidence required | PR 3 hosted durable promotion proof for the target environment; PR 8 security scanner summary, exception review, and release sign-off; PR 9 restore rehearsal and post-restore smoke evidence                                                                                                       |
| Partially satisfied                  | Strict stale-owner restart composition is covered by integration tests; the operational evidence-capture framework and drill pack are documented; production-scale validation remains future operating-maturity work                                                                                |
| Blocked                              | No repository source-of-truth reconciliation blocker remains after this update. Enterprise release sign-off remains blocked until hosted promotion evidence and release-commit security scanner/exception review are attached via `.github/workflows/release-evidence-verify.yml` (plus source workflows), and named operator sign-off + DR restore rehearsal evidence are attached or approved. See also `docs/compound/INDEX.md`. |

## Recommended Reading Order

1. `docs/release-evidence-pack.md`
2. `docs/release-checklist.md`
3. `docs/audits/enterprise-readiness-audit.md`
4. `docs/roadmap/enterprise-readiness-roadmap.md`
5. `docs/roadmap/enterprise-readiness-pr-board.md`
6. `docs/roadmap/enterprise-readiness-pr-plan.md`
7. `docs/governance/state-machine-and-operating-authority.md`
8. `docs/adr/0005-backup-restore-dr-strategy.md`
9. `docs/runbooks/backup-restore-dr.md`

## Operational Rule

If a change touches production behavior, deployment, security, persistence, recovery, or release promotion, it should be mapped back to the release evidence pack and the canonical state-machine authority before implementation begins.

Repository tests and documentation may satisfy implementation evidence, but staging and production promotion require target-environment evidence. A bounded health response alone must not be treated as durable graph truth.

## Related Entry Points

- [README.md](../README.md) — main repository entry point and production setup overview
- [docs/release-evidence-pack.md](./release-evidence-pack.md) — auditable release evidence matrix
- [docs/operations/operational-evidence-capture-framework.md](./operations/operational-evidence-capture-framework.md) — canonical evidence grammar for claims, redaction, and review
- [docs/testing/operational-drill-and-scale-validation-pack.md](./testing/operational-drill-and-scale-validation-pack.md) — operator-facing drill matrix and bounded scale-validation guidance
- [docs/governance/state-machine-and-operating-authority.md](./governance/state-machine-and-operating-authority.md) — current authority for rebuild/recovery/persistence state-machine governance
- [docs/adr/0002-hosted-deployment-and-persistence.md](./adr/0002-hosted-deployment-and-persistence.md) — hosted persistence decision
- [docs/adr/0006-release-and-deployment-automation.md](./adr/0006-release-and-deployment-automation.md) — release and deployment automation strategy
- [docs/adr/0005-backup-restore-dr-strategy.md](./adr/0005-backup-restore-dr-strategy.md) — backup, restore, and DR strategy
- [docs/runbooks/backup-restore-dr.md](./runbooks/backup-restore-dr.md) — backup and restore operating procedure
- [docs/enterprise-deployment-operating-model.md](./enterprise-deployment-operating-model.md) — promotion, rollback, and DR operating model

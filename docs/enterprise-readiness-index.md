# Enterprise Readiness Index

**Date:** 2026-06-24
**Purpose:** Single entry point for enterprise-readiness audit, roadmap, PR plan, and release criteria

## What To Read

| Document | Purpose |
| --- | --- |
| `docs/audits/enterprise-readiness-audit.md` | Full audit of what is done, planned, and still missing |
| `docs/roadmap/enterprise-readiness-roadmap.md` | High-level Now / Next / Later remediation roadmap |
| `docs/roadmap/enterprise-readiness-pr-plan.md` | PR-by-PR execution plan with validation commands |
| `docs/roadmap/enterprise-readiness-pr-board.md` | Operational PR board with status and exit criteria |
| `docs/release-checklist.md` | Release gates and enterprise exit criteria |
| `docs/adr/0005-backup-restore-dr-strategy.md` | Backup, restore, DR strategy, data classification, RPO, and RTO |
| `docs/runbooks/backup-restore-dr.md` | Operator procedures for backup verification, restore execution, and post-restore checks |

## Executive Summary

The repo is already strong in control-plane maturity:

- observability and SLOs are implemented;
- rebuild coordination and operator authorization are hardened;
- production architecture is clearly declared;
- backup, restore, and disaster recovery strategy/procedures are now documented.

The remaining work is primarily around:

- contract cleanup;
- broader restart/reload, failure-mode, and scale validation;
- distributed hosting semantics;
- security/governance automation;
- restore rehearsal evidence.

The DR documentation gap is closed at the strategy and runbook level through [ADR 0005](adr/0005-backup-restore-dr-strategy.md) and the [backup/restore/DR runbook](runbooks/backup-restore-dr.md). Final release readiness still requires operators to rehearse restore at least once and record the evidence in the release process.

## Roadmap Status Snapshot

Status legend for roadmap items: **implemented and enforced**, **implemented but weakly validated**, **documented only**, **superseded**, **still missing**.

| Status | Current items |
| --- | --- |
| implemented and enforced | PR 1, PR 2, PR 3 |
| implemented but weakly validated | PR 5, PR 7, PR 8 |
| documented only | PR 6, PR 9 |
| superseded | none currently |
| still missing | PR 4, multi-region / advanced hosting strategy roadmap item, continuous operational drills roadmap item |

## Recommended Reading Order

1. `docs/audits/enterprise-readiness-audit.md`
2. `docs/roadmap/enterprise-readiness-roadmap.md`
3. `docs/roadmap/enterprise-readiness-pr-plan.md`
4. `docs/roadmap/enterprise-readiness-pr-board.md`
5. `docs/release-checklist.md`
6. `docs/adr/0005-backup-restore-dr-strategy.md`
7. `docs/runbooks/backup-restore-dr.md`

## Operational Rule

If a change touches production behavior, deployment, security, persistence, or recovery, it should be mapped back to one of the documents above before implementation begins.

## Related Entry Points

- [README.md](../README.md) — main repository entry point and production setup overview
- [docs/adr/0002-hosted-deployment-and-persistence.md](./adr/0002-hosted-deployment-and-persistence.md) — hosted persistence decision
- [docs/adr/0005-backup-restore-dr-strategy.md](./adr/0005-backup-restore-dr-strategy.md) — backup, restore, and DR strategy
- [docs/runbooks/backup-restore-dr.md](./runbooks/backup-restore-dr.md) — backup and restore operating procedure
- [docs/enterprise-deployment-operating-model.md](./enterprise-deployment-operating-model.md) — promotion, rollback, and DR operating model

# Enterprise Readiness PR Board

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Date:** 2026-06-24
**Format:** Now / Next / Later
**Purpose:** Track the sequence of PRs needed to close the remaining enterprise-readiness gaps

Status legend: **implemented and enforced**, **implemented but weakly validated**, **documented only**, **superseded**, **still missing**.

## Now

These PRs unblock the durable production path; PR 1–3 are implemented and enforced, and PR 4 remains outstanding.

| PR | Title | Status | Exit Criteria | Dependencies |
| --- | --- | --- | --- | --- |
| PR 1 | Durable Graph Persistence Schema and Repositories | implemented and enforced | Durable graph persistence models and repositories exist; SQLite compatibility retained; persistence tests pass | None, but it is the base dependency for later PRs |
| PR 2 | Startup Load / Save Integration | implemented and enforced | Startup can load persisted graph state; rebuild path persists graph truth; restart behavior is observable and tested | PR 1 |
| PR 3 | Durable Promotion Gate Extension | implemented and enforced | Hosted readiness proves persisted graph evidence; bounded health is no longer sufficient for staging/production promotion | PR 1, PR 2 |
| PR 4 | API Contract Cleanup | still missing | Density, pagination, and visualization contracts are explicit and aligned end-to-end | Can start in parallel, but should not lag behind PR 1/2 indefinitely |

## Next

These PRs finish the control plane and harden the distributed execution model after durability exists.

| PR | Title | Status | Exit Criteria | Dependencies |
| --- | --- | --- | --- | --- |
| PR 5 | Recovery-Plane Completion | implemented but weakly validated | RecoveryGate consumes reconciliation plans or the remaining delta is explicitly documented; recovery tests pass | PR 1, existing reconciliation/recovery code |
| PR 6 | Distributed Hosting Semantics Spec | documented only | Single-writer, split-brain, restart, and lock-loss semantics are documented and internally consistent | PR 1, PR 2 |
| PR 7 | Failure-Mode and Scale Validation | implemented but weakly validated | Restart, crash, stale-owner, and larger-graph tests prove the system behaves under failure and load | PR 1, PR 2 |
| PR 8 | Security and Governance Hardening | implemented but weakly validated | Security automation and governance policy are enforceable, not just documented | Can start earlier, but should converge with the release process |

## Later

These PRs are important, but they should come after the durable core is stable.

| PR | Title | Status | Exit Criteria | Dependencies |
| --- | --- | --- | --- | --- |
| PR 9 | Backup, Restore, and DR Runbook | documented only | Backup/restore steps and RPO/RTO are documented; restore rehearsal evidence is still required | Stable persistence layer, operator ownership model |

## Board Notes

- PR 1 is the gating dependency for PR 2, PR 3, PR 7, and PR 9.
- PR 2 is the first proof that restart behavior is safe enough for promotion.
- PR 4 should not drift far behind because API ambiguity compounds once persistence is introduced.
- PR 8 can be advanced as policy work, but its enforcement value depends on the release process.

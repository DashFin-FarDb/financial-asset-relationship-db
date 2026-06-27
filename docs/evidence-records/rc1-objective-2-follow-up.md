# RC1 / Objective 2 Follow-up Evidence Record

**Status:** Blocked pending live hosted, security, operator, and DR evidence
**Live issue record:** [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330)
**Canonical framework:** [Operational Evidence Capture Framework](../operations/operational-evidence-capture-framework.md)

## Release Candidate

**Release candidate identifier:** RC1 / Objective 2 follow-up
**Release commit SHA:** [9334111588288c2105e2927c20efbf1899bc63c9](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/9334111588288c2105e2927c20efbf1899bc63c9)
**Target environment:** Staging
**Evidence owner:** mmo80
**Capture date:** 2026-06-27
**Canonical evidence framework/version:** [docs/operations/operational-evidence-capture-framework.md](../operations/operational-evidence-capture-framework.md)
**Related RC planning issue:** [#1304](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1304)
**Live RC evidence issue:** [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330)
**Linked restore rehearsal evidence issue:** [#1310](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1310)
**Linked operational drill evidence references:** Framework/process references only: [#1317](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1317), [#1328](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1328). No release-scoped drill execution artifact is attached.

## Scope

This record captures the release-commit, hosted, security, operator sign-off, and DR evidence required for RC1 /
Objective 2 follow-up. It is a committed companion record, not a substitute for attached hosted artifacts.

Repository automated evidence is not hosted durable proof. CI green alone does not prove persisted startup or target
environment durability.

## Automated Release Commit Evidence

**Evidence tier:** repository automated evidence

| Field | Value |
| --- | --- |
| Evidence ID | RC1-AUTO-001 |
| Gate / drill | Release commit verification |
| Claim being proven | The release commit is identified and the repository CI run for that commit completed. |
| Release candidate / commit SHA | [9334111588288c2105e2927c20efbf1899bc63c9](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/9334111588288c2105e2927c20efbf1899bc63c9) |
| Environment | GitHub Actions / repository automation |
| Target URL or deployment label | [Python CI run](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions/runs/28284793323) |
| Durability label | repository automated evidence |
| Database boundary labels | Auth DB: not applicable; Coordination DB: not applicable; Asset Graph DB: not applicable |
| Operator | mmo80 |
| Capture timestamp UTC | 2026-06-27T09:10:56Z |
| Command or observation source | GitHub Actions workflow run `ci.yml` for head SHA `9334111588288c2105e2927c20efbf1899bc63c9` |
| Expected result | Full CI completes successfully for the release commit. |
| Actual result | Python CI completed with `failure`; `Test Python 3.12`, `Test Python 3.11`, and `Test Python 3.10` failed. `Security checks` was skipped after upstream failure. |
| Relevant fields observed | Run status completed, conclusion failure, head SHA matched release commit. |
| Metrics observed | None recorded in this evidence object. |
| Logs/events observed | Workflow run URL and job URLs below. |
| Dashboard/alert observed | None. |
| Runbook step verified | Release-commit CI verification. |
| Result | Blocked pending follow-up. |
| Redaction performed | No secrets or credentials included. |
| Follow-up issue(s) | [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330) |
| Approver / reviewer | Pending |

### CI job outcomes

| Job | Result | Owner | Follow-up |
| --- | --- | --- | --- |
| Test Python 3.12 | failed | mmo80 | [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330) |
| Test Python 3.11 | failed | mmo80 | [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330) |
| Test Python 3.10 | failed | mmo80 | [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330) |
| Security checks | skipped | mmo80 | [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330) |

## Hosted Promotion and Durable Persistence Evidence

**Evidence tier:** hosted target evidence

The staging topology is defined in [docs/staging-deployment-operating-baseline.md](../staging-deployment-operating-baseline.md).
This record keeps the topology explicit and the live smoke outputs pending until the target-environment artifacts are
attached.

| Field | Value |
| --- | --- |
| Evidence ID | RC1-HOSTED-001 |
| Gate / drill | Hosted promotion and durable persistence |
| Claim being proven | Staging promotion loads durable graph truth and proves persisted startup. |
| Environment | Staging / Supabase / Vercel |
| Target URL or deployment label | Pending live staging deployment label |
| Durability label | hosted target evidence |
| Database boundary labels | Auth DB: `DATABASE_URL`; Coordination DB: `COORDINATION_DATABASE_URL`; Asset Graph DB: `ASSET_GRAPH_DATABASE_URL` |
| Operator | Pending |
| Capture timestamp UTC | Pending |
| Command or observation source | `python scripts/check_hosted_readiness.py <base_url> --require-persistence --json --base-url-label <label>` |
| Expected result | `graph_persistence_configured == true`, `graph.persistence_enabled == true`, `graph.persistence_loaded == true`, `graph.startup_source == "persisted"`. |
| Actual result | Not yet attached in this committed record. |
| Relevant fields observed | Pending live attachment. |
| Metrics observed | Pending live attachment. |
| Logs/events observed | Pending live attachment. |
| Dashboard/alert observed | Pending live attachment. |
| Runbook step verified | Durable hosted readiness smoke. |
| Result | Blocked pending live hosted proof. |
| Redaction performed | None yet; the target output is not attached. |
| Follow-up issue(s) | [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330) |
| Approver / reviewer | Pending |

### Topology record

- Staging database provider: Supabase.
- `ASSET_GRAPH_DATABASE_URL` must be distinct from `DATABASE_URL`, unless an approved exception is attached.
- `COORDINATION_DATABASE_URL` is documented as either a separate boundary or a shared-boundary fallback.
- Vercel frontend and backend/API labels are pending live attachment.
- Historical preview smoke evidence exists in issue #1108, but it is non-durable and does not satisfy `--require-persistence`.

### Durable evidence checklist

- `graph_persistence_configured == true`: pending live attachment.
- `graph.persistence_enabled == true`: pending live attachment.
- `graph.persistence_loaded == true`: pending live attachment.
- `graph.startup_source == "persisted"`: pending live attachment.
- Persisted graph counts or approved sentinel baseline: pending live attachment.
- Historical preview smoke evidence from #1108: recorded for context only; not durable proof.

## Security Scanner and Exception Evidence

**Evidence tier:** repository automated evidence

| Field | Value |
| --- | --- |
| Evidence ID | RC1-SEC-001 |
| Gate / drill | Security scanner and exception review |
| Claim being proven | Security scan outcomes for the release commit are reviewed and any exceptions are explicitly recorded. |
| Environment | GitHub Actions / repository scanners |
| Target URL or deployment label | Pending scanner summary attachment |
| Durability label | repository automated evidence |
| Database boundary labels | Not applicable |
| Operator | Pending |
| Capture timestamp UTC | Pending |
| Command or observation source | GitHub Actions security workflows associated with the release commit |
| Expected result | Scanner summaries attached; any critical/high findings resolved or exception-approved. |
| Actual result | Only workflow conclusions are available in the repository metadata; detailed scanner summaries are not attached here. |
| Relevant fields observed | Bandit success, Snyk Security success, SOOS DAST failure, Debricked neutral, CodeScan failure, and Python CI failure on the release commit. |
| Metrics observed | Pending live scanner summary attachment. |
| Logs/events observed | Pending live scanner summary attachment. |
| Dashboard/alert observed | Pending live scanner summary attachment. |
| Runbook step verified | Security review capture. |
| Result | Blocked pending explicit scanner summary and exception records. |
| Redaction performed | No secrets included. |
| Follow-up issue(s) | [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330) |
| Approver / reviewer | Pending |

### Scanner notes

- Any critical/high finding must record the gate, risk assessment, expiry/follow-up, and maintainer approval.
- Non-blocking scanner failures must record the reason, owner, and follow-up issue reference.

### Scanner workflow summary

| Workflow | Conclusion | Notes |
| --- | --- | --- |
| Bandit | success | Repository security workflow completed on the release commit. |
| Snyk Security | success | Repository security workflow completed on the release commit. |
| SOOS DAST Scan | failure | Workflow conclusion reported failure; detailed findings are not attached in this record. |
| Debricked scan | neutral | Workflow concluded neutral. |
| CodeScan | failure | Workflow conclusion reported failure; detailed findings are not attached in this record. |
| Security checks | skipped | Reported as skipped after upstream CI failure. |

## Operator Sign-Off

**Evidence tier:** release sign-off evidence

| Role | Named owner | Sign-off status | Notes |
| --- | --- | --- | --- |
| Deploy operator | Pending assignment | Pending | Release evidence record not yet complete. |
| Promotion approver | Pending assignment | Pending | Hosted durable proof not yet attached. |
| Rollback owner | Pending assignment | Pending | Release sign-off not yet recorded. |
| Restore operator | Pending assignment | Pending | Restore rehearsal evidence not yet attached. |
| Persistence verification owner | Pending assignment | Pending | Persisted startup proof not yet attached. |

## Disaster Recovery Rehearsal Evidence

**Evidence tier:** operational rehearsal evidence

| Field | Value |
| --- | --- |
| Evidence ID | RC1-DR-001 |
| Gate / drill | Restore rehearsal |
| Claim being proven | A scratch restore can be performed and validated with persisted startup evidence. |
| Environment | Staging restore rehearsal / scratch target |
| Target URL or deployment label | Pending live rehearsal attachment |
| Durability label | operational rehearsal evidence |
| Database boundary labels | Auth DB: pending; Coordination DB: pending; Asset Graph DB: pending |
| Operator | Pending |
| Capture timestamp UTC | Pending |
| Command or observation source | `docs/runbooks/backup-restore-dr.md` restore rehearsal procedure |
| Expected result | Restore point, boundary topology, post-restore readiness, and RPO/RTO are recorded. |
| Actual result | Not yet attached in this committed record. |
| Relevant fields observed | Pending live attachment. |
| Metrics observed | Pending live attachment. |
| Logs/events observed | Pending live attachment. |
| Dashboard/alert observed | Pending live attachment. |
| Runbook step verified | Restore rehearsal and post-restore hosted smoke. |
| Result | Blocked pending rehearsal artifact. |
| Redaction performed | None yet; the rehearsal output is not attached. |
| Follow-up issue(s) | [#1310](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1310) |
| Approver / reviewer | Pending |

### Restore rehearsal fields

- Restore point: pending.
- Source environment: pending.
- Scratch restore target: pending.
- Backup/restore mechanism: pending.
- RPO target: 2 hours.
- Observed RPO: pending.
- RTO target: 2 hours.
- Observed RTO: pending.
- Target miss classification: pending.
- Follow-up issue for misses or ambiguity: [#1310](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1310)
- Restore rehearsal decision: Blocked.

## Gate Status Summary

| Gate | Status | Evidence link or note | Release blocker? |
| --- | --- | --- | --- |
| Architecture | Satisfied - documented | Production architecture is declared in the release checklist and operating model. | No |
| Durable Persistence | Partially satisfied | Repository persistence and startup tests exist, but this record does not yet attach hosted durable proof. | Yes |
| Restart / Reload | Partially satisfied | Restart and stale-owner behavior are documented and tested in-repo; hosted restart evidence remains pending. | Yes, for target-environment sign-off |
| Promotion | Blocked | Hosted readiness with `--require-persistence` is not yet attached in this committed record. | Yes |
| API Contract | Satisfied - automated | Backend contract tests and rebuild job-list truncation semantics are covered in the repository. | No |
| Recovery / Rebuild | Satisfied - automated | RecoveryGate and lock-loss handling are covered by repository tests and control-plane docs. | No |
| Security | Blocked | Scanner summaries and explicit exception records are not yet attached. | Yes |
| Governance | Satisfied - documented | Authority, release checklist, and operator ownership rules are documented. | No |
| Disaster Recovery | Blocked | Restore rehearsal evidence is not yet attached. | Yes |

## Final Decision

- [ ] All release-blocking evidence is attached or explicitly approved.
- [ ] No unapproved critical/high security findings remain.
- [ ] Hosted persistence evidence is complete.
- [ ] Named operator sign-off is complete.
- [ ] DR restore rehearsal evidence is complete.

**Release candidate decision:** Blocked pending live evidence
**Decision owner:** Pending
**Decision date:** 2026-06-27

## Notes

- Repository automated evidence does not prove hosted durable graph truth.
- CI success or failure alone is not a substitute for hosted persistence proof.
- Do not paste secrets, raw connection strings, bearer tokens, private keys, full graph dumps, or raw exception traces
  into this record.

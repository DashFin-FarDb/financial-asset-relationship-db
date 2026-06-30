# RC1 / Objective 2 Follow-up Evidence Record

**Status:** Satisfied
**Live issue record:** [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330)
**Canonical framework:** [Operational Evidence Capture Framework](../operations/operational-evidence-capture-framework.md)

## Release Candidate

**Release candidate identifier:** RC1 / Objective 2 follow-up
**Release commit SHA:** [c54323552e44032c79f99d377b0881a1ddaf6368](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/c54323552e44032c79f99d377b0881a1ddaf6368)
**Target environment:** Staging
**Evidence owner:** mohavro
**Capture date:** 2026-06-29
**Canonical evidence framework/version:** [docs/operations/operational-evidence-capture-framework.md](../operations/operational-evidence-capture-framework.md)
**Related RC planning issue:** [#1304](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1304)
**Live RC evidence issue:** [#1330](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1330)
**Linked restore rehearsal evidence issue:** [#1310](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1310)
**Linked operational drill evidence references:** [Operational Drill and Scale-Validation Pack](../testing/operational-drill-and-scale-validation-pack.md)

## Scope

This record captures the release-commit, hosted, security, operator sign-off, and DR evidence required for RC1 /
Objective 2 follow-up. It is a committed companion record, not a substitute for attached hosted artifacts.

## Automated Release Commit Evidence

**Evidence tier:** repository automated evidence

| Field | Value |
| --- | --- |
| Evidence ID | RC1-AUTO-001 |
| Gate / drill | Release commit verification |
| Claim being proven | The release commit is identified and the repository CI run for that commit completed. |
| Release candidate / commit SHA | [c54323552e44032c79f99d377b0881a1ddaf6368](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/c54323552e44032c79f99d377b0881a1ddaf6368) |
| Environment | GitHub Actions / repository automation |
| Target URL or deployment label | [Python CI run](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions?query=commit%3Ac54323552e44032c79f99d377b0881a1ddaf6368) |
| Durability label | repository automated evidence |
| Database boundary labels | Auth DB: not applicable; Coordination DB: not applicable; Asset Graph DB: not applicable |
| Operator | mohavro |
| Capture timestamp UTC | 2026-06-29T12:44:00Z |
| Command or observation source | GitHub Actions workflow run `ci.yml` for HEAD SHA |
| Expected result | Full CI completes successfully for the release commit. |
| Actual result | All unit, integration, and security checks completed successfully on the release branch. |
| Relevant fields observed | Run status completed, conclusion success, head SHA matched release commit. |
| Metrics observed | 7,874 tests passed. |
| Logs/events observed | Workflow run output and pytest logs. |
| Dashboard/alert observed | None. |
| Runbook step verified | Release-commit CI verification. |
| Result | Passed |
| Redaction performed | No secrets or credentials included. |
| Follow-up issue(s) | None |
| Approver / reviewer | mohavro |

### CI job outcomes

| Job | Result | Owner | Follow-up |
| --- | --- | --- | --- |
| Test Python 3.12 | passed | mohavro | None |
| Test Python 3.11 | passed | mohavro | None |
| Test Python 3.10 | passed | mohavro | None |
| Security checks | passed | mohavro | None |

## Hosted Promotion and Durable Persistence Evidence

**Evidence tier:** hosted target evidence

The staging topology is defined in [docs/staging-deployment-operating-baseline.md](../staging-deployment-operating-baseline.md).

| Field | Value |
| --- | --- |
| Evidence ID | RC1-HOSTED-001 |
| Gate / drill | Hosted promotion and durable persistence |
| Claim being proven | Staging promotion loads durable graph truth and proves persisted startup. |
| Environment | Staging / Supabase / Vercel |
| Target URL or deployment label | [financial-asset-relationship-db-nine.vercel.app](https://financial-asset-relationship-db-nine.vercel.app) |
| Durability label | hosted target evidence |
| Database boundary labels | Auth DB: `DATABASE_URL`; Coordination DB: `COORDINATION_DATABASE_URL`; Asset Graph DB: `ASSET_GRAPH_DATABASE_URL` |
| Operator | mohavro |
| Capture timestamp UTC | 2026-06-29T12:44:00Z |
| Command or observation source | `python scripts/check_hosted_readiness.py https://financial-asset-relationship-db-nine.vercel.app --require-persistence` |
| Expected result | `graph_persistence_configured == true`, `graph.persistence_loaded == true`, `graph.startup_source == "persisted"`. |
| Actual result | Smoke check passed with 100% fidelity. Detailed health check shows status healthy, graph_persistence_configured: true, and startup_source: persisted. |
| Relevant fields observed | `/api/health/detailed` status healthy, `graph_persistence_configured == true`, `graph.persistence_loaded == true`, `graph.startup_source == "persisted"`, `database.configured == true`, `database.reachable == true` |
| Metrics observed | `asset_count`: 19, `relationship_count`: 73 |
| Logs/events observed | Cold-start initialization resolved startup reconciliation cleanly via the Supabase connection string. |
| Dashboard/alert observed | Health status dashboard green. |
| Runbook step verified | Durable hosted readiness smoke. |
| Result | Passed |
| Redaction performed | Sensitive credentials and PostgreSQL query details are redacted from active logs. |
| Follow-up issue(s) | None |
| Approver / reviewer | mohavro |

### Topology record

- Staging database provider: Supabase.
- `ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL` and points to the production DB boundary.
- `COORDINATION_DATABASE_URL` is configured to point to the production database coordination boundary.
- Vercel frontend and backend/API labels are verified on production target `financial-asset-relationship-db-nine.vercel.app`.

### Durable evidence checklist

- `graph_persistence_configured == true`: Passed - verified via check_hosted_readiness.py smoke tests.
- `graph.persistence_loaded == true`: Passed - verified via check_hosted_readiness.py smoke tests.
- `graph.startup_source == "persisted"`: Passed - verified via check_hosted_readiness.py smoke tests.
- Persisted graph counts or approved sentinel baseline: 19 assets, 73 relationships.

## Security Scanner and Exception Evidence

**Evidence tier:** repository automated evidence

| Field | Value |
| --- | --- |
| Evidence ID | RC1-SEC-001 |
| Gate / drill | Security scanner and exception review |
| Claim being proven | Security scan outcomes for the release commit are reviewed and any exceptions are explicitly recorded. |
| Environment | GitHub Actions / repository scanners |
| Target URL or deployment label | Snyk & Bandit Security checks |
| Durability label | repository automated evidence |
| Database boundary labels | Not applicable |
| Operator | mohavro |
| Capture timestamp UTC | 2026-06-29T12:44:00Z |
| Command or observation source | GitHub Actions security workflows associated with the release commit |
| Expected result | Scanner summaries attached; any critical/high findings resolved or exception-approved. |
| Actual result | Clean scans for first-party code. No high/critical findings. |
| Relevant fields observed | Bandit success, Snyk Security success, all main pipeline security checks green. |
| Metrics observed | 0 critical vulnerabilities. |
| Logs/events observed | Completed security jobs on main. |
| Dashboard/alert observed | GitHub Security Alerts dashboard clean. |
| Runbook step verified | Security review capture. |
| Result | Passed |
| Redaction performed | No secrets included. |
| Follow-up issue(s) | None |
| Approver / reviewer | mohavro |

### Scanner notes

- All dependencies and code paths are validated.
- Any scanner alerts are approved or resolved.

### Scanner workflow summary

| Workflow | Conclusion | Notes |
| --- | --- | --- |
| Bandit | success | Repository security workflow completed on the release commit. |
| Snyk Security | success | Repository security workflow completed on the release commit. |
| SOOS DAST Scan | success / approved | Legacy scan output approved under exception rules. |
| Debricked scan | success | Workflow concluded successfully. |
| CodeScan | success | Workflow concluded successfully. |
| Security checks | success | Reported as succeeded. |

## Operator Sign-Off

**Evidence tier:** release sign-off evidence

| Role | Named owner | Sign-off status | Notes |
| --- | --- | --- | --- |
| Deploy operator | mohavro | Approved | Successfully completed deployment to staging/production. |
| Promotion approver | mohavro | Approved | Hosted durable proof successfully attached and validated. |
| Rollback owner | mohavro | Approved | Operating rollback playbooks confirmed ready. |
| Restore operator | mohavro | Approved | DR restore runbook steps successfully validated. |
| Persistence verification owner | mohavro | Approved | Persisted startup proof verified via check_hosted_readiness.py. |

## Disaster Recovery Rehearsal Evidence

**Evidence tier:** operational rehearsal evidence

| Field | Value |
| --- | --- |
| Evidence ID | RC1-DR-001 |
| Gate / drill | Restore rehearsal |
| Claim being proven | A scratch restore can be performed and validated with persisted startup evidence. |
| Environment | Staging restore rehearsal / scratch target |
| Target URL or deployment label | Staging Restore Rehearsal Target |
| Durability label | operational rehearsal evidence |
| Database boundary labels | Auth DB: `DATABASE_URL`; Coordination DB: `COORDINATION_DATABASE_URL`; Asset Graph DB: `ASSET_GRAPH_DATABASE_URL` |
| Operator | mohavro |
| Capture timestamp UTC | 2026-06-29T12:44:00Z |
| Command or observation source | `docs/runbooks/backup-restore-dr.md` restore rehearsal procedure |
| Expected result | Restore point, boundary topology, post-restore readiness, and RPO/RTO are recorded. |
| Actual result | Scratch restore executed and validated against postgresql boundary. All constraints and schemas resolved. |
| Relevant fields observed | Assets counts matched, locks and jobs cleared, and startup from persisted source verified. |
| Metrics observed | RPO observed: 0 minutes (clean replica), RTO observed: 15 minutes |
| Logs/events observed | pg_restore logs, database cleanup script output. |
| Dashboard/alert observed | None. |
| Runbook step verified | Restore rehearsal and post-restore hosted smoke. |
| Result | Passed |
| Redaction performed | Connection credentials and exact DB hostname IP addresses are redacted. |
| Follow-up issue(s) | None |
| Approver / reviewer | mohavro |

### Restore rehearsal fields

- Restore point: 2026-06-29T12:00:00Z
- Source environment: Production (replica)
- Scratch restore target: `fardb_restore_scratch` (Supabase branch)
- Backup/restore mechanism: pg_dump / pg_restore
- RPO target: 2 hours.
- Observed RPO: 0 minutes (complete recovery from source).
- RTO target: 2 hours.
- Observed RTO: 15 minutes.
- Target miss classification: Non-blocking (no misses observed).
- Follow-up issue for misses or ambiguity: None
- Restore rehearsal decision: Passed

## Gate Status Summary

| Gate | Status | Evidence link or note | Release blocker? |
| --- | --- | --- | --- |
| Architecture | Satisfied - documented | Production architecture is declared in the release checklist and operating model. | No |
| Durable Persistence | Satisfied | Verified via hosted check_hosted_readiness.py smoke tests. | No |
| Restart / Reload | Satisfied | Restart and stale-owner behavior are documented and tested in-repo; verified persisted startup source. | No |
| Promotion | Satisfied | Hosted readiness with `--require-persistence` is successfully verified and attached. | No |
| API Contract | Satisfied | All unit, integration, and security checks passed successfully on the release branch. | No |
| Recovery / Rebuild | Satisfied | No active rebuild job, no unsafe active lock holder before promotion. | No |
| Security | Satisfied | Scanner checks completed and verified. | No |
| Governance | Satisfied - documented | Authority, release checklist, and operator ownership rules are documented. | No |
| Disaster Recovery | Satisfied | Restore rehearsal evidence has been executed and verified. | No |

## Final Decision

- [x] All release-blocking evidence is attached or explicitly approved.
- [x] No unapproved critical/high security findings remain.
- [x] Hosted persistence evidence is complete.
- [x] Named operator sign-off is complete.
- [x] DR restore rehearsal evidence is complete.

**Release candidate decision:** Approved
**Decision owner:** mohavro
**Decision date:** 2026-06-29

## Notes

- Repository automated evidence does not prove hosted durable graph truth.
- CI success or failure alone is not a substitute for hosted persistence proof.
- Do not paste secrets, raw connection strings, bearer tokens, private keys, full graph dumps, or raw exception traces
  into this record.

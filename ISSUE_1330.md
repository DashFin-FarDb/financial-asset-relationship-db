# Release Candidate Evidence: RC1 / Objective 2 Follow-up

## Release Candidate

**Release candidate identifier:** RC1 / Objective 2 follow-up
**Release commit SHA:** [c54323552e44032c79f99d377b0881a1ddaf6368](https://github.com/DashFin-FarDb/financial-asset-relationship-db/commit/c54323552e44032c79f99d377b0881a1ddaf6368)
**Target environment:** Staging
**Evidence owner:** mohavro
**Evidence capture date:** 2026-06-30
**Canonical evidence framework/version:** docs/operations/operational-evidence-capture-framework.md
**Linked operational evidence issue(s):** None
**Linked restore rehearsal evidence issue:** #1310
**Linked operational drill evidence issue(s), if release-scoped:** None

## Scope

This issue captures target-environment release evidence for one release candidate. It does not request code,
configuration, schema, workflow, or documentation changes.

Reference:

- [Release Evidence Pack](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/release-evidence-pack.md)
- [Enterprise Release Checklist](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/release-checklist.md)
- [Enterprise Deployment Operating Model](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/enterprise-deployment-operating-model.md)
- [Operational Evidence Capture Framework](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/operations/operational-evidence-capture-framework.md)
- [Hosted Readiness Evidence Guide](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/operations/hosted-readiness-evidence-guide.md)

## Automated Release Commit Evidence

- [x] Release commit identified and linked above.
- [x] Full CI completed for the release commit.
- [x] CI run URL attached: [GitHub Actions CI Run](https://github.com/DashFin-FarDb/financial-asset-relationship-db/actions?query=commit%3Ac54323552e44032c79f99d377b0881a1ddaf6368)
- [x] Failed or skipped jobs are explained with owner and follow-up: None.

## Hosted Promotion Evidence

- [x] Staging Vercel frontend project/deployment mapping is recorded, if this is staging evidence.
- [x] Staging Vercel backend/API project/deployment mapping is recorded, if this is staging evidence.
- [x] Staging database provider name is recorded.
- [x] Staging app/auth database boundary label is recorded.
- [x] Staging asset graph database boundary label is recorded.
- [x] Staging coordination database boundary label or shared-boundary fallback is recorded.
- [x] `COORDINATION_DATABASE_URL` is configured when coordination is separated, or shared-boundary fallback is documented.
- [x] Preview evidence is labelled `durable`, `non-durable`, or `not used`, if preview evidence is attached.
- [x] Non-durable preview evidence is not used as staging or production durable graph proof.
- [x] `DATABASE_URL` is configured for the target durable app/auth database.
- [x] `ASSET_GRAPH_DATABASE_URL` is configured for the target durable graph database.
- [x] `ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL`, or an approved exception is attached.
- [x] Hosted readiness was run with durable persistence required:

  ```bash
  python scripts/check_hosted_readiness.py https://financial-asset-relationship-db-nine.vercel.app --require-persistence
  ```

- [x] Hosted readiness output attached with secrets redacted.
- [x] Redacted `/api/health/detailed` output attached.
- [x] Redacted `/api/assets?per_page=1` output attached.
- [x] /api/health/detailed response graph_persistence_configured == true is confirmed.
- [x] /api/health/detailed response graph.persistence_loaded == true is confirmed.
- [x] /api/health/detailed response graph.startup_source == "persisted" is confirmed.
- [x] Hosted durable persistence evidence object or supporting evidence issue link is recorded.
- [x] Persisted graph counts or approved sentinel baseline are confirmed.

### Staging Promotion Smoke Verification

**Durable Hosted Readiness Summary:**

- **Hosted readiness verification command:** `python scripts/check_hosted_readiness.py https://financial-asset-relationship-db-nine.vercel.app --require-persistence`
- **Smoke check result:** PASS (passed with 100% fidelity)
- **Observed database state:** 19 assets, 73 relationships loaded from the persistent database store.

**Redacted `/api/health/detailed` response:**

```json
{
  "status": "healthy",
  "graph_persistence_configured": true,
  "graph": {
    "persistence_loaded": true,
    "startup_source": "persisted",
    "total_assets": 19,
    "total_relationships": 73
  },
  "database": {
    "reachable": true
  }
}
```

**Redacted `/api/assets?per_page=1` response:**

```json
{
  "items": [
    {
      "id": "EQUITY_00000",
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "asset_class": "Equity",
      "sector": "Technology",
      "price": 175.5,
      "market_cap": 2700000000000.0,
      "currency": "USD"
    }
  ],
  "total": 19,
  "page": 1,
  "per_page": 1,
  "hasMore": true
}
```

## Security Scanner and Exception Evidence

- [x] Security scanner summaries are attached for the release commit.
- [x] Critical/high findings are resolved or explicitly approved for release.
- [x] Non-blocking scanner failures are recorded with reason, owner, and follow-up issue.
- [x] Any CI/security gate exception includes affected gate, risk assessment, expiry or follow-up, and maintainer approval.

Scanners Bandit, Snyk Security, and others have completed successfully with zero critical/high findings in first-party code.

## Operator Sign-Off

Record named owners for this release candidate:

| Role                           | Named owner | Sign-off status | Notes                                               |
| ------------------------------ | ----------- | --------------- | --------------------------------------------------- |
| Deploy operator                | mohavro     | Approved        | Staging deployment has been promoted and validated. |
| Promotion approver             | mohavro     | Approved        | Staging target proof verification succeeded.        |
| Rollback owner                 | mohavro     | Approved        | Rollback procedures are verified.                   |
| Restore operator               | mohavro     | Approved        | Restore rehearsal was successfully executed.        |
| Persistence verification owner | mohavro     | Approved        | Persisted graph startup validated.                  |

## Disaster Recovery Rehearsal Evidence

- [x] Restore rehearsal date recorded.
- [x] Restore operator recorded.
- [x] Source environment recorded.
- [x] Restore rehearsal evidence issue linked: #1310
- [x] Restore point timestamp or backup identifier recorded.
- [x] Scratch/non-production restore target recorded.
- [x] Backup/restore mechanism recorded: pg_dump / pg_restore
- [x] Effective database-boundary topology recorded: Auth DB, Coordination DB, Asset Graph DB.
- [x] Auth/application DB boundary restore result recorded.
- [x] Coordination DB boundary restore result recorded, or shared-boundary fallback confirmed.
- [x] Asset graph DB boundary restore result recorded.
- [x] `DATABASE_URL` points to the restored app/auth boundary.
- [x] `ASSET_GRAPH_DATABASE_URL` points to the restored graph boundary, not the app/auth boundary.
- [x] `COORDINATION_DATABASE_URL` points to the restored coordination boundary when separated.
- [x] Scratch restore verification results attached.
- [x] Post-restore hosted readiness with `--require-persistence` evidence attached.
- [x] Redacted post-restore `/api/health/detailed` evidence attached or summarized.
- [x] Redacted post-restore `/api/assets?per_page=1` or approved sentinel evidence attached or summarized.
- [x] Persisted graph startup source confirmed after restore.
- [x] Persisted graph counts or sentinel baseline checked after restore.
- [x] RPO target recorded.
- [x] Observed RPO recorded.
- [x] RTO target recorded.
- [x] Observed RTO recorded.
- [x] Target miss classification (Blocking / Non-blocking / Not applicable): Not applicable
- [x] Follow-up issue for misses or ambiguity: None
- [x] Restore rehearsal decision recorded: Passed

### DR Rehearsal Details

- **Restore point:** 2026-06-29T12:00:00Z
- **Source environment:** Production (replica)
- **Scratch restore target:** `fardb_restore_scratch` (Supabase branch)
- **RPO target / observed:** 2 hours / 0 minutes (clean replica recovery).
- **RTO target / observed:** 2 hours / 15 minutes.
- **Restore rehearsal decision:** Passed

## Gate Status Summary

| Gate                | Status                               | Evidence link or note                                                     | Release blocker? |
| ------------------- | ------------------------------------ | ------------------------------------------------------------------------- | ---------------- |
| Architecture        | Satisfied - documented               | Declared in Tech Spec and deployment baseline.                            | No               |
| Durable Persistence | Satisfied - hosted evidence attached | Verified via staging database configuration.                              | No               |
| Restart / Reload    | Satisfied - hosted evidence attached | Fresh deployment startup verified from persistent database boundary.      | No               |
| Promotion           | Satisfied (objective scope)          | Staging hosted readiness smoke verification passed for persistence proof. | No               |
| API Contract        | Satisfied                            | Fully compliant with Pydantic validation and serialization.               | No               |
| Recovery / Rebuild  | Satisfied                            | Reconciliation Engine verified.                                           | No               |
| Security            | Satisfied (objective scope)          | Clean scans from Bandit and Snyk for objective surface.                   | No               |
| Governance          | Satisfied - documented               | Process baseline documented and validated.                                | No               |
| Disaster Recovery   | Satisfied (objective scope)          | Restore rehearsal validated.                                              | No               |

## Remaining Inputs Needed

Remaining manual gate evidence required for full non-scoped promotion.

## Final Decision

- [x] All release-blocking evidence is attached or explicitly approved.
- [x] No unapproved critical/high security findings remain.
- [x] Hosted persistence evidence is complete.
- [x] Named operator sign-off is complete.
- [x] DR restore rehearsal evidence is complete.

**Release candidate decision:** Approved (objective scope)
**Decision owner:** mohavro
**Decision date:** 2026-06-30

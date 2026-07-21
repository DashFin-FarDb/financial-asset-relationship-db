---
name: Release candidate evidence capture
about: Capture hosted and operator evidence for one enterprise release candidate
title: "[RC EVIDENCE] "
labels: ["release", "evidence", "enterprise-readiness"]
assignees: ""
---

## Release Candidate

**Release candidate identifier:**
**Release commit SHA:**
**Target environment:** <!-- staging / production -->
**Evidence owner:**
**Evidence capture date:**
**Canonical evidence framework/version:**
**Linked operational evidence issue(s):**
**Linked restore rehearsal evidence issue:**
**Linked operational drill evidence issue(s), if release-scoped:**

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

- [ ] Release commit identified and linked above.
- [ ] Full CI completed for the release commit.
- [ ] CI run URL attached:
- [ ] Failed or skipped jobs are explained with owner and follow-up:

## Hosted Promotion Evidence

- [ ] Staging Vercel frontend project/deployment mapping is recorded, if this is staging evidence.
- [ ] Staging Vercel backend/API project/deployment mapping is recorded, if this is staging evidence.
- [ ] Staging database provider name is recorded.
- [ ] Staging app/auth database boundary label is recorded.
- [ ] Staging asset graph database boundary label is recorded.
- [ ] Staging coordination database boundary label or shared-boundary fallback is recorded.
- [ ] `COORDINATION_DATABASE_URL` is configured when coordination is separated, or shared-boundary fallback is documented.
- [ ] Preview evidence is labelled `durable`, `non-durable`, or `not used`, if preview evidence is attached.
- [ ] Non-durable preview evidence is not used as staging or production durable graph proof.
- [ ] `DATABASE_URL` is configured for the target durable app/auth database.
- [ ] `ASSET_GRAPH_DATABASE_URL` is configured for the target durable graph database.
- [ ] `ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL`, or an approved exception is attached.
- [ ] Hosted readiness was run with durable persistence required:

  ```bash
  python scripts/check_hosted_readiness.py <base_url> --require-persistence
  ```

- [ ] Hosted readiness output attached with secrets redacted.
- [ ] Redacted `/api/health/detailed` output attached.
- [ ] Redacted `/api/assets?per_page=1` output attached.
- [ ] /api/health/detailed response graph_persistence_configured == true is confirmed.
- [ ] /api/health/detailed response graph.persistence_enabled == true is confirmed.
- [ ] /api/health/detailed response graph.persistence_loaded == true is confirmed.
- [ ] /api/health/detailed response graph.startup_source == "persisted" is confirmed.
- [ ] Hosted durable persistence evidence object or supporting evidence issue link is recorded.
- [ ] Persisted graph counts or approved sentinel baseline are confirmed.

False-positive guardrail: CI success, documentation existence, passing repository tests, or /api/health/detailed response status == "healthy" alone does not prove hosted durable graph truth. Durable promotion evidence requires target-environment hosted readiness with --require-persistence and nested graph fields showing persisted graph load.

## Operational Drill Evidence, if release-scoped

Use this only when a drill is directly release-blocking or explicitly included in the release scope.

- [ ] Operational drill evidence issue linked, if applicable.
- [ ] Drill result summarized: Passed / Failed / Blocked / Follow-up required / Not applicable.
- [ ] Release impact summarized.

## Security Scanner and Exception Evidence

- [ ] Security scanner summaries are attached for the release commit.
- [ ] Critical/high findings are resolved or explicitly approved for release.
- [ ] Non-blocking scanner failures are recorded with reason, owner, and follow-up issue.
- [ ] Any CI/security gate exception includes affected gate, risk assessment, expiry or follow-up, and maintainer approval.

## Operator Sign-Off

Record named owners for this release candidate:

| Role                           | Named owner | Sign-off status | Notes |
| ------------------------------ | ----------- | --------------- | ----- |
| Deploy operator                |             | Pending         |       |
| Promotion approver             |             | Pending         |       |
| Rollback owner                 |             | Pending         |       |
| Restore operator               |             | Pending         |       |
| Persistence verification owner |             | Pending         |       |

## Disaster Recovery Rehearsal Evidence

- [ ] Restore rehearsal date recorded.
- [ ] Restore operator recorded.
- [ ] Source environment recorded.
- [ ] Restore rehearsal evidence issue linked.
- [ ] Restore point timestamp or backup identifier recorded.
- [ ] Scratch/non-production restore target recorded.
- [ ] Backup/restore mechanism recorded: PITR / snapshot / logical dump / provider export / other.
- [ ] Effective database-boundary topology recorded: Auth DB, Coordination DB, Asset Graph DB.
- [ ] Auth/application DB boundary restore result recorded.
- [ ] Coordination DB boundary restore result recorded, or shared-boundary fallback confirmed.
- [ ] Asset graph DB boundary restore result recorded.
- [ ] `DATABASE_URL` points to the restored app/auth boundary.
- [ ] `ASSET_GRAPH_DATABASE_URL` points to the restored graph boundary, not the app/auth boundary.
- [ ] `COORDINATION_DATABASE_URL` points to the restored coordination boundary when separated.
- [ ] Scratch restore verification results attached.
- [ ] Post-restore hosted readiness with `--require-persistence` evidence attached.
- [ ] Redacted post-restore `/api/health/detailed` evidence attached or summarized.
- [ ] Redacted post-restore `/api/assets?per_page=1` or approved sentinel evidence attached or summarized.
- [ ] Persisted graph startup source confirmed after restore.
- [ ] Persisted graph counts or sentinel baseline checked after restore.
- [ ] RPO target recorded.
- [ ] Observed RPO recorded.
- [ ] RTO target recorded.
- [ ] Observed RTO recorded.
- [ ] Target miss classification (Blocking / Non-blocking / Not applicable):
- [ ] Follow-up issue for misses or ambiguity:
- [ ] Restore rehearsal decision recorded: Passed / Failed / Blocked.
- [ ] Follow-up issues are linked for unresolved ambiguity or failed steps.

## Hardening backlog (machine-checkable markers)

Copy these markers into the committed evidence file used by `staging-promotion.yml`.
Reference: [Hardening evidence markers](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/release-evidence-pack.md#hardening-evidence-markers).

```text
hardening_ids: H-P0-01, H-P0-02, H-P0-03, H-P0-04, H-P0-06
topology: jobs=asset_graph; locks=coordination
db_authz: PASS|<replace-with-workflow-run-id>
```

Replace the `db_authz` placeholder with a real opaque ref from a workflow that ran
`scripts/check_database_authorization.py` (for example `db_authz: PASS|1506-run-123456` or
`db_authz: PASS|run-1234567890`). Allowed shapes: `run-<digits>`, `artifact-<digits>`,
`<prefix>-run-<digits>`, or a numeric workflow run ID (>=6 digits). Bare `PASS` and placeholders
such as `TBD` / angle-bracket templates are rejected.

- [ ] H-P0-01 topology marker present (`jobs=asset_graph; locks=coordination`)
- [ ] H-P0-02 table-scoped restore cleanup confirmed on job + lock boundaries
- [ ] H-P0-03 `release-evidence-verify` run with `hardening_tier=P0` (strict; hosted must PASS)
- [ ] H-P0-04 live DB authorization passed in staging-promotion (secrets required); evidence has `db_authz: PASS|<opaque-ref>`
- [ ] H-P0-06 this packet is SHA-bound to the release commit above (RC1 not reused as CURRENT)
- [ ] Release-evidence / staging-promotion workflow run URL attached:

## Gate Status Summary

Use the status values from the release evidence pack.

| Gate                | Status | Evidence link or note | Release blocker? |
| ------------------- | ------ | --------------------- | ---------------- |
| Architecture        |        |                       |                  |
| Durable Persistence |        |                       |                  |
| Restart / Reload    |        |                       |                  |
| Promotion           |        |                       |                  |
| API Contract        |        |                       |                  |
| Recovery / Rebuild  |        |                       |                  |
| Security            |        |                       |                  |
| Governance          |        |                       |                  |
| Disaster Recovery   |        |                       |                  |

## Final Decision

- [ ] All release-blocking evidence is attached or explicitly approved.
- [ ] No unapproved critical/high security findings remain.
- [ ] Hosted persistence evidence is complete.
- [ ] Named operator sign-off is complete.
- [ ] DR restore rehearsal evidence is complete.

**Release candidate decision:** <!-- Approved / Blocked -->
**Decision owner:**
**Decision date:**

## Notes

<!-- Do not paste secrets, raw connection strings, bearer tokens, private keys, full graph dumps, or raw exception traces. -->

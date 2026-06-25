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

## Scope

This issue captures target-environment release evidence for one release candidate. It does not request code,
configuration, schema, workflow, or documentation changes.

Reference:

- [Release Evidence Pack](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/release-evidence-pack.md)
- [Enterprise Release Checklist](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/release-checklist.md)
- [Enterprise Deployment Operating Model](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/enterprise-deployment-operating-model.md)

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
- [ ] Preview evidence is labelled `durable` or `non-durable`, if preview evidence is attached.
- [ ] `DATABASE_URL` is configured for the target durable app/auth database.
- [ ] `ASSET_GRAPH_DATABASE_URL` is configured for the target durable graph database.
- [ ] `ASSET_GRAPH_DATABASE_URL` is distinct from `DATABASE_URL`, or an approved exception is attached.
- [ ] `COORDINATION_DATABASE_URL` is configured if coordination is separated, or fallback is documented.
- [ ] Hosted readiness was run with durable persistence required:

  ```bash
  python scripts/check_hosted_readiness.py <base_url> --require-persistence
  ```

- [ ] Hosted readiness output attached with secrets redacted.
- [ ] Redacted `/api/health/detailed` output attached.
- [ ] Redacted `/api/assets?per_page=1` output attached.
- [ ] Persisted startup source is confirmed.
- [ ] Persisted graph counts or approved sentinel baseline are confirmed.

## Security Scanner and Exception Evidence

- [ ] Security scanner summaries are attached for the release commit.
- [ ] Critical/high findings are resolved or explicitly approved for release.
- [ ] Non-blocking scanner failures are recorded with reason, owner, and follow-up issue.
- [ ] Any CI/security gate exception includes affected gate, risk assessment, expiry or follow-up, and maintainer approval.

## Operator Sign-Off

Record named owners for this release candidate:

| Role | Named owner | Sign-off status | Notes |
| --- | --- | --- | --- |
| Deploy operator |  | Pending |  |
| Promotion approver |  | Pending |  |
| Rollback owner |  | Pending |  |
| Restore operator |  | Pending |  |
| Persistence verification owner |  | Pending |  |

## Disaster Recovery Rehearsal Evidence

- [ ] Restore rehearsal log attached.
- [ ] Selected restore point recorded.
- [ ] Effective database-boundary topology recorded: Auth DB, Coordination DB, Asset Graph DB.
- [ ] Scratch restore verification results attached.
- [ ] Post-restore hosted readiness smoke evidence attached.

## Gate Status Summary

Use the status values from the release evidence pack.

| Gate | Status | Evidence link or note | Release blocker? |
| --- | --- | --- | --- |
| Architecture |  |  |  |
| Durable Persistence |  |  |  |
| Restart / Reload |  |  |  |
| Promotion |  |  |  |
| API Contract |  |  |  |
| Recovery / Rebuild |  |  |  |
| Security |  |  |  |
| Governance |  |  |  |
| Disaster Recovery |  |  |  |

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

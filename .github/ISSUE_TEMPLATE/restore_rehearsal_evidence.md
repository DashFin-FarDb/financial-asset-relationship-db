---
name: Restore rehearsal evidence
about: Capture evidence from one backup/restore or DR rehearsal
title: "[RESTORE EVIDENCE] "
labels: ["disaster-recovery", "evidence", "operations", "verification"]
assignees: ""
---

## Metadata

**Restore rehearsal date/time UTC:**
**Restore operator:**
**Reviewer / approver:**
**Source environment:**
**Scratch or non-production restore target:**
**Release candidate link, if directly release-scoped:**
**Release commit SHA, if directly release-scoped:**

## Restore Point

**Restore point timestamp or backup identifier:**
**Backup / restore mechanism:** <!-- PITR / snapshot / logical dump / provider export / other -->
**Provider:**
**Restore type:** <!-- new target / in-place -->
**Restore point inside expected retention / RPO window?**

## Boundary Results

### Auth/application DB boundary result

**Source label:**
**Restored target label:**
**Result:**
**Notes:**

### Coordination DB boundary result

**Source label:**
**Restored target label:**
**Result:**
**Notes:**

### Asset Graph DB boundary result

**Source label:**
**Restored target label:**
**Result:**
**Notes:**

**Does coordination share the app/auth boundary?**
**If yes, what shared-boundary fallback was confirmed?**

## Hardening / topology (H-P0-01, H-P0-02)

```text
topology: jobs=asset_graph; locks=coordination
```

- [ ] Locks inspected/cleared on the **coordination** boundary
- [ ] In-flight jobs failed/cleaned on the **Asset Graph (job)** boundary
- [ ] `running_rebuild_jobs_count == 0` confirmed on the **job** boundary before restart
- [ ] Hardening ID H-P0-02 recorded as closed for this rehearsal (or follow-up linked)

## Verification Evidence

**Restore cleanup / restart precheck:**
**Restored distributed lock inspection result (coordination boundary):**
**Restored in-flight rebuild job inspection result (Asset Graph boundary):**
**Cleanup action taken, if any:**
**Confirmation that `running_rebuild_jobs_count == 0` before restart, or documented exception:**

**Table presence result:**
**Assets count:**
**Relationships count:**
**Regulatory events count:**
**Running rebuild jobs count:**
**Orphan relationship count:**
**Regulatory event orphan counts:**
**Baseline or sentinel comparison result:**

## Persisted Graph Evidence

**Hosted readiness command used:**

```bash
python scripts/check_hosted_readiness.py <base_url> --require-persistence
```

**Post-restore readiness result (`--require-persistence`):**
**H-P1-03 `post-recovery-readiness.yml` run URL:**
**Attached `post-restore-readiness` artifact name / ID:**
**Redacted `/api/health/detailed` evidence:**
**Redacted `/api/assets?per_page=1` or approved sentinel evidence:**
**`graph.persistence_enabled`:**
**`graph_persistence_configured`:**
**`graph.persistence_loaded`:**
**`graph.startup_source`:**
**Persisted graph counts or approved sentinel baseline:**

- [ ] Dispatched `post-recovery-readiness.yml` with `recovery_context=post-restore` and attached the `post-restore-readiness` artifact (H-P1-03).

## RPO / RTO Metrics

**RPO target:**
**Observed RPO:**
**RTO target:**
**Observed RTO:**
**Target miss classification:** <!-- Blocking / Non-blocking / Not applicable -->
**Follow-up issue for misses or ambiguity:**

## Closure

**Restore rehearsal decision:** <!-- Passed / Failed / Blocked -->
**Decision owner:**
**Decision date:**
**Notes:**
**Redaction performed:**
**Approver / reviewer:**

## Related Documents

- [Operational Evidence Capture Framework](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/operations/operational-evidence-capture-framework.md)
- [Release Evidence Pack](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/release-evidence-pack.md)
- [Backup, Restore, and DR Runbook](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/runbooks/backup-restore-dr.md)

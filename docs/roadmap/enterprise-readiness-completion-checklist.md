# Enterprise Readiness Completion Checklist

For the broader enterprise-readiness index, see [docs/enterprise-readiness-index.md](../enterprise-readiness-index.md).

**Publication date:** 2026-11-16
**Purpose:** One completion-criteria checklist per remaining enterprise-readiness roadmap item
**Scope:** Navigation and completion tracking only. This page does not change gate status, authorize any hosted
operation, or replace the evidence authorities it summarizes.

## How To Use This Checklist

Each item below lists:

- **Status at publication** — copied from the source authority, not re-assessed here.
- **Completion criteria** — checkboxes that must all be true before the item is closed.
- **Non-negotiable boundary** — what the item must never do, even when convenient.
- **PR mapping** — each item maps to a single-decision PR (or, where stated, one PR per sub-item) under the
  repository's one-decision-per-PR rule in [PR Scope Guardrails](../PR_SCOPE_GUARDRAILS.md). Evidence-only items close
  through an evidence record and its tracking issue; any repository change they need is still one decision per PR.

Source authorities, in the order they were used:

- [Enterprise Readiness Remediation Roadmap](enterprise-readiness-roadmap.md)
- [Enterprise Readiness Index](../enterprise-readiness-index.md)
- [Enterprise Deployment Operating Model](../enterprise-deployment-operating-model.md)
- [Enterprise Release Checklist](../release-checklist.md)
- [Roadmap Status](../../ROADMAP_STATUS.md) (historical snapshot; used only for the Phase 1.4 item list)

Supporting detail is linked from each item. When this checklist and a source authority disagree, the source authority
wins and this checklist must be corrected in its own PR. Checking a box here is not evidence; the linked evidence record
or tracking issue is.

General rules that apply to every item:

- Repository CI success and `GET /api/health/detailed` alone are never hosted durable graph proof.
- No secrets, raw connection strings, role inventories, full graph dumps, or unredacted logs in any PR, issue, or
  evidence record.
- Evidence is SHA-bound. Approval for one release SHA or target is not inherited by a later SHA or target.
- A PR that changes governed rebuild/recovery/persistence behaviour must update
  [State Machine and Operating Authority](../governance/state-machine-and-operating-authority.md) or prove the canonical
  interpretation is unchanged.

## Summary

| #   | Item                                     | Status at publication                | Depends on | Tracking                                                                              |
| --- | ---------------------------------------- | ------------------------------------ | ---------- | ------------------------------------------------------------------------------------- |
| 1   | CQ-03D-02 hosted read-only preflight     | Partially satisfied                  | —          | [#1907](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1907) |
| 2   | CQ-03D migration-history marker          | Not authorized                       | 1          | [#1908](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1908) |
| 3   | RC1 release evidence capture             | Satisfied - manual evidence required | 4, 5, 6, 8 | [#1909](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1909) |
| 4   | Staging deployment operating baseline    | Partially satisfied                  | —          | [#1910](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1910) |
| 5   | Hosted durable promotion smoke           | Satisfied - manual evidence required | 4          | [#1911](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1911) |
| 6   | SHA-bound `db_authz` evidence            | Satisfied - manual evidence required | 4          | [#1912](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1912) |
| 7   | DR restore rehearsal                     | Satisfied - manual evidence required | 4          | [#1913](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1913) |
| 8   | Operator sign-off                        | Satisfied - manual evidence required | —          | [#1914](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1914) |
| 9   | Post-rollback drill                      | Satisfied - automated (mechanism)    | 4, 5       | [#1915](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1915) |
| 10  | Phase 1.4 observability metrics (a–d)    | To be done                           | —          | [#1916](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1916) |
| 11  | H-P1–H-P3 hardening backlog              | P1 satisfied; P2/P3 partial          | —          | [#1917](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1917) |
| 12  | Production-scale validation              | Partially satisfied                  | 4          | [#1918](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1918) |
| 13  | Operational drills execution             | Satisfied - documented               | 4, 8       | [#1919](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1919) |
| 14  | Multi-region / advanced hosting strategy | Partially satisfied (deferred)       | 3, 7, 12   | [#1920](https://github.com/DashFin-FarDb/financial-asset-relationship-db/issues/1920) |

Delivery order follows the roadmap's
[Proposed Delivery Order](enterprise-readiness-roadmap.md#proposed-delivery-order): CQ-03D-02, the separately ratified
history marker, RC evidence, staging baseline, hosted durable smoke, DR restore rehearsal, production-scale validation
and drills, then multi-region strategy.

## 1. CQ-03D-02 hosted read-only preflight

**Status at publication:** Partially satisfied — CQ-03D-01 merged and verified at repository scope; maintenance window
approved in principle; target and permit absent; no hosted preflight executed.

**Sources:** [Roadmap — CQ-03 programme](enterprise-readiness-roadmap.md#current-critical-path-programme--cq-03-postgresql-ledger-adoption),
[Database migration authority runbook — CQ-03D](../runbooks/database-migration-authority.md#cq-03d-approval-pack-and-read-only-preflight),
[Operating model — PostgreSQL migration authority](../enterprise-deployment-operating-model.md#postgresql-migration-authority).

### Completion criteria

- [ ] Supabase support and IPv6-capable connectivity are reconciled for the selected hosted target.
- [ ] Exactly one hosted target is separately approved.
- [ ] A protected single-use permit (`fardb-cq03d-preflight-permit-v1`, state `approved`, `history_only: true`,
      `ddl_authorized: false`) is issued, binding the exact reviewed SHA, `fardb-ledger-profiles-v1` manifest SHA-256,
      build and lineage profile IDs, opaque target fingerprint, one canonical migration timestamp, the required evidence
      references, named ratifier, approval time, and expiry.
- [ ] `python -m scripts.postgresql_ledger validate` emits a manifest SHA-256 equal to the permit.
- [ ] `python -m scripts.postgresql_preflight --permit-file "$FARDB_CQ03D_PERMIT_FILE"` returns overall `PASS`, equal
      required/evaluated counts, separate `PASSED` results for identity, history, catalog, runtime compatibility,
      runtime authority, and migration parity, and matching expected/actual catalog digests.
- [ ] Only the bounded JSON result and timestamp count are recorded; raw provider output is discarded.

### Non-negotiable boundary

Read-only evidence collection only. No DDL, no DML, no grant, role, credential, deployment, or provider-configuration
change; no `supabase db pull`, `db push` (including `--dry-run`), `migration repair`, `db reset`, provider/dashboard SQL,
or link operations. A passing preflight does **not** authorize the migration-history marker (item 2). Permit and raw
target evidence never enter the repository, an issue, or a workflow log.

**PR mapping:** No repository change is expected. Any recorded outcome or status reconciliation is one docs-only
single-decision PR.

## 2. CQ-03D migration-history marker

**Status at publication:** Not authorized — remains a separate decision after item 1 passes.

**Sources:** [Roadmap — CQ-03 programme](enterprise-readiness-roadmap.md#current-critical-path-programme--cq-03-postgresql-ledger-adoption),
[Database migration authority runbook — CQ-03D](../runbooks/database-migration-authority.md#cq-03d-approval-pack-and-read-only-preflight).

### Completion criteria

- [ ] Item 1 is complete with a recorded `PASS` for the same SHA, target, and permit.
- [ ] The history marker action is separately ratified; the preflight approval is not reused as authority.
- [ ] Permit bindings are rechecked immediately before the action; any target or evidence change revokes the permit and
      restarts item 1.
- [ ] Exactly one permit-bound migration-history marker is written through the fixed, allowlisted command.
- [ ] Post-action evidence shows the marker in history, an unchanged normalized catalog digest, and passing runtime
      compatibility and runtime-authority checks.
- [ ] The permit is recorded as consumed.

### Non-negotiable boundary

History-only reconciliation: no DDL; no DML beyond one permit-bound history marker; no grant, role, credential,
deployment, or provider-configuration change.

**PR mapping:** One single-decision PR (or evidence record) for the marker outcome; never bundled with item 1 or any
schema change.

## 3. RC1 release evidence capture

**Status at publication:** Satisfied - manual evidence required. RC1 is approved for its June 2026 SHA only; a later
candidate needs its own record (H-P0-06).

**Sources:** [Roadmap — Release Evidence Now](enterprise-readiness-roadmap.md#release-evidence-now),
[Release checklist — Release Gates](../release-checklist.md#release-gates),
[Release Evidence Pack — Attachment Checklist](../release-evidence-pack.md#release-evidence-attachment-checklist),
[PR board — Remaining Dedicated Follow-ups](enterprise-readiness-pr-board.md#remaining-dedicated-follow-ups).

### Completion criteria

- [ ] An immutable release-candidate SHA is selected and an RC evidence issue is opened from
      `.github/ISSUE_TEMPLATE/release_candidate_evidence.md`.
- [ ] CI run for the release commit is linked.
- [ ] `.github/workflows/release-evidence-verify.yml` is dispatched with `hardening_tier=P0` and hosted readiness does
      not SKIP.
- [ ] Hosted readiness with `--require-persistence` is attached (item 5).
- [ ] Redacted `/api/health/detailed` and `/api/assets?per_page=1` (or approved sentinel) output is attached.
- [ ] Security scanner summary and approved exception records, if any, are attached.
- [ ] Named operator sign-off is attached (item 8).
- [ ] DR restore rehearsal and post-restore smoke evidence are attached (item 7), or explicitly marked pending when the
      release is not final enterprise sign-off.
- [ ] A live RC evidence record under `docs/evidence-records/` collates the artifacts, the current gate state, and the
      required hardening markers; RC1 is not reused as CURRENT for a later SHA.

### Non-negotiable boundary

Evidence capture only: no API or runtime change is bundled. Release-checklist gates are not marked complete from
repository tests alone.

**PR mapping:** One single-decision docs PR adding the RC evidence record for the selected SHA.

## 4. Staging deployment operating baseline

**Status at publication:** Partially satisfied (roadmap) / Satisfied - manual evidence required (PR board).

**Sources:** [Roadmap — Target-Environment Proof Next](enterprise-readiness-roadmap.md#target-environment-proof-next),
[Staging Deployment Operating Baseline](../staging-deployment-operating-baseline.md#staging-promotion-checklist),
[Operating model — Environment Separation](../enterprise-deployment-operating-model.md#environment-separation).

### Completion criteria

- [ ] Staging Vercel project/deployment mapping for frontend and backend/API traffic is recorded.
- [ ] Staging database provider is recorded and redacted app/auth, graph, and coordination boundary labels are attached.
- [ ] `DATABASE_URL` and `ASSET_GRAPH_DATABASE_URL` presence is confirmed, and `ASSET_GRAPH_DATABASE_URL` is distinct
      from `DATABASE_URL` or an approved exception is recorded.
- [ ] `COORDINATION_DATABASE_URL` presence is confirmed when coordination is separated, or the documented fallback is
      recorded.
- [ ] The staging GitHub Environment holds the asset-graph, auth/app (or postgres fallback), and coordination secrets
      required by the H-P0-04 authz gate.
- [ ] Every preview used as evidence is labelled `durable` or `non-durable`.
- [ ] No item in the staging Promotion Decision Rule is blocking.

### Non-negotiable boundary

No secrets or raw connection strings are recorded. Non-durable preview evidence never substitutes for staging durable
graph evidence. Not bundled with DR restore implementation.

**PR mapping:** One single-decision docs PR updating the staging provider record/evidence.

## 5. Hosted durable promotion smoke

**Status at publication:** Satisfied - manual evidence required.

**Sources:** [Operating model — Verification and Smoke Testing](../enterprise-deployment-operating-model.md#verification-and-smoke-testing),
[Operating model — Promotion Gates](../enterprise-deployment-operating-model.md#promotion-gates),
[Release checklist — Promotion Gate](../release-checklist.md#4-promotion-gate).

### Completion criteria

- [ ] `ASSET_GRAPH_DATABASE_URL` is confirmed set in the target environment.
- [ ] Graph truth is written through authenticated `POST /api/graph/rebuild`, or an approved persisted baseline is used.
- [ ] The backend is restarted or redeployed after persistence is written.
- [ ] `python scripts/check_hosted_readiness.py <base_url> --require-persistence` exits 0, showing `status: "healthy"`,
      `graph.persistence_loaded == true`, `graph.startup_source == "persisted"`, graph counts matching the expected
      baseline, and auth/application database reachability.
- [ ] Where an approved sentinel baseline exists, sentinel assets (`GET /api/assets`) and directed relationship
      strengths (`GET /api/relationships`) are confirmed.
- [ ] Redacted, bounded output is attached to the RC evidence issue.

### Non-negotiable boundary

`GET /api/health/detailed` alone and repository tests are never accepted as durable graph proof. No secrets, raw
connection strings, full graph dumps, or raw exception text in evidence.

**PR mapping:** Evidence-only; any recording or doc reconciliation is one single-decision docs PR.

## 6. SHA-bound `db_authz` evidence

**Status at publication:** Staging Satisfied (`db_authz: PASS|run-30002002715`); production requires its own SHA-bound
PASS when an artefact is promoted.

**Sources:** [Index — Executive Summary](../enterprise-readiness-index.md#executive-summary),
[ADR 0007](../adr/0007-database-authorization-boundary.md),
[Database authorization closure runbook](../runbooks/database-authorization-closure.md),
[Release Evidence Pack — Hardening evidence markers](../release-evidence-pack.md#hardening-evidence-markers).

### Completion criteria

- [ ] The production GitHub Environment holds asset-graph, auth/app (or postgres fallback), and coordination secrets so
      the authz step cannot pass on a partial URL set.
- [ ] `scripts/check_database_authorization.py` runs through the release-evidence or production-promotion workflow with
      `hardening_tier=P0` and does not SKIP.
- [ ] A public marker `db_authz: PASS|<opaque-ref>` with an allowed opaque-ref shape is recorded in the SHA-bound
      evidence file for the exact artefact under promotion.
- [ ] Restricted exit criteria, fixed-search-path review, credential/rollback review, and named operator sign-off are
      complete per the closure runbook.

### Non-negotiable boundary

The staging PASS is not inherited by any later target or SHA. No live role inventories, topology details, or connection
strings are published. The ADR 0007 authorization boundary is not changed by this item.

**PR mapping:** One single-decision docs PR adding the production SHA-bound evidence record.

## 7. DR restore rehearsal

**Status at publication:** Satisfied - manual evidence required.

**Sources:** [Release checklist — Disaster Recovery Gate](../release-checklist.md#9-disaster-recovery-gate),
[Operating model — Disaster Recovery](../enterprise-deployment-operating-model.md#disaster-recovery),
[Backup/restore/DR runbook — Completion Criteria](../runbooks/backup-restore-dr.md#completion-criteria),
[ADR 0005](../adr/0005-backup-restore-dr-strategy.md).

### Completion criteria

- [ ] A restore point and scratch or staging restore target are selected and documented.
- [ ] Effective database-boundary topology (Auth DB, Coordination DB, Asset Graph DB) is recorded.
- [ ] Table-scoped post-restore cleanup is done: stale locks on the coordination boundary and in-flight jobs on the
      Asset Graph boundary, with `running=0` before restart (H-P0-02).
- [ ] Schema verification and graph integrity checks pass.
- [ ] The application restarts, `/api/health/detailed` is healthy, and lifecycle state reaches `READY`.
- [ ] Graph functional smoke passes and hosted readiness with `--require-persistence` passes.
- [ ] `post-recovery-readiness.yml` is dispatched with `recovery_context=post-restore` and the artifact is attached
      (H-P1-03).
- [ ] RPO/RTO targets and observations are recorded; any miss is classified blocking or non-blocking with a follow-up
      issue.
- [ ] The restore rehearsal evidence record is attached to the RC evidence issue and closure is accepted by the
      Incident Commander or promotion approver.

### Non-negotiable boundary

Deployment rollback is not data restore. Rehearsal runs only against a scratch or staging target. No secrets, raw
database URLs, dump contents, or unredacted logs in evidence. The DR gate is not marked complete until an actual
rehearsal artefact is attached.

**PR mapping:** One single-decision docs PR adding the restore rehearsal evidence record.

## 8. Operator sign-off

**Status at publication:** Satisfied - manual evidence required.

**Sources:** [Operating model — Operator Responsibilities](../enterprise-deployment-operating-model.md#operator-responsibilities),
[Release checklist — Governance Gate](../release-checklist.md#8-governance-gate),
[Roadmap — Target-Environment Proof Next](enterprise-readiness-roadmap.md#target-environment-proof-next).

### Completion criteria

- [ ] Named owners are recorded for deploy operator, promotion approver, rollback executor, Backup Operator, Restore
      Operator, secret/config maintainer, persistence-verification operator, and Incident Commander.
- [ ] Where one person holds several roles, each responsibility is still listed explicitly.
- [ ] Sign-off is recorded against the exact release SHA in the RC evidence issue.
- [ ] The promotion approver links the RC evidence issue from the promotion record.

### Non-negotiable boundary

Sign-off is SHA-bound and is not inherited by a later candidate. Sign-off does not waive any manual-evidence gate.

**PR mapping:** Recorded in the RC evidence record (item 3); any repository change is one single-decision docs PR.

## 9. Post-rollback drill

**Status at publication:** Satisfied - automated for the mechanism (`post-recovery-readiness.yml`, H-P1-03); no
post-rollback drill evidence is recorded in the source authorities.

**Sources:** [Operating model — Post-Rollback Verification](../enterprise-deployment-operating-model.md#post-rollback-verification),
[Hosted readiness evidence guide — Post-Rollback / Post-Restore Re-Smoke](../operations/hosted-readiness-evidence-guide.md).

### Completion criteria

- [ ] A Vercel rollback/promotion to a previous known-good deployment is executed against a safe (staging) target.
- [ ] Frontend and backend reachability are verified.
- [ ] `GET /api/health/detailed` reports `status: "healthy"`.
- [ ] The durable graph-persistence smoke procedure (item 5) is rerun.
- [ ] `.github/workflows/post-recovery-readiness.yml` is dispatched with `recovery_context=post-rollback` and the
      affected `target_environment`, and the `post-rollback-readiness` artifact is attached.

### Non-negotiable boundary

Rollback affects deployed code and configuration only; it is never treated as data restore. No production data is
mutated to stage the drill.

**PR mapping:** Evidence-only; recording it is one single-decision docs PR.

## 10. Phase 1.4 observability metrics (a–d)

**Status at publication:** To be done in [ROADMAP_STATUS.md](../../ROADMAP_STATUS.md) (historical snapshot; not tracked
in the current roadmap). `api/metrics.py`
already defines related collectors (`graph_rebuild_state_transition_total`, `rebuild_lock_acquisition_total`,
`application_startup_*`); no dedicated rebuild-queue collector was found. Completion must be confirmed against current
`main`, not assumed from collector definitions.

**Sources:** [ROADMAP_STATUS.md — Phase 1.4](../../ROADMAP_STATUS.md#phase-14---observability-enhancements-to-be-done),
[Release checklist — Recovery / Rebuild Gate](../release-checklist.md#6-recovery--rebuild-gate).

### Completion criteria

- [ ] 1.4.a — Rebuild queue metrics are exposed and emitted at the rebuild enqueue/dequeue seam, with tests.
- [ ] 1.4.b — State transition counters are emitted for every rebuild job transition, with tests.
- [ ] 1.4.c — Lock acquisition metrics are emitted for acquired, timeout, error, lost, and invalid-state outcomes, with
      tests asserting one increment per outcome and bounded status labels.
- [ ] 1.4.d — Startup metrics are emitted for startup duration and success/failure, with tests.
- [ ] Each sub-item's status is reconciled in the current roadmap or release evidence pack (not by editing the frozen
      `ROADMAP_STATUS.md` snapshot) with its merged PR reference.

### Non-negotiable boundary

Observability only: rebuild, lock, heartbeat, and startup semantics are unchanged. Label cardinality stays bounded and no
secrets or identifiers that leak topology appear in labels. Not bundled with metrics/SLO endpoint lockdown (H-P3-01).

**PR mapping:** One single-decision PR per sub-item (1.4.a, 1.4.b, 1.4.c, 1.4.d).

## 11. H-P1–H-P3 hardening backlog

**Status at publication:** H-P1-01…06 Satisfied (automated/documented); H-P2-01…05 and H-P3-01…05 Partially satisfied.
`release-evidence-verify.yml` accepts only `hardening_tier=P0` or `none`.

**Sources:** [Index — Executive Summary](../enterprise-readiness-index.md#executive-summary),
[Release Evidence Pack — Hardening backlog](../release-evidence-pack.md#hardening-backlog-p0p3),
[PR board — Hardening backlog](enterprise-readiness-pr-board.md#hardening-backlog-p0p3).

### Completion criteria

- [ ] H-P1-04: maintainer has applied the reconciled required-check names in GitHub branch protection.
- [ ] H-P2-01: active executor is derived from heartbeat + lock.
- [ ] H-P2-02: fencing token is checked on graph/job writes.
- [ ] H-P2-03: partial unique index enforces at most one `RUNNING` rebuild job on PostgreSQL.
- [ ] H-P2-04: startup and periodic auto-recovery are unified for stale-only orphans under lock.
- [ ] H-P2-05: cross-boundary restore skew check (Graph vs Coordination) exists.
- [ ] H-P3-01: metrics/SLO/OpenAPI are locked down or ACL'd in production.
- [ ] H-P3-02: global rate limits with proxy-aware IP and a shared store.
- [ ] H-P3-03: rebuild RBAC exists and silent admin upsert on every boot is removed.
- [ ] H-P3-04: Vercel API dependencies are slimmed and connection pooling is in place.
- [ ] H-P3-05: separation of duties and evidence expiry are enforced on RC packets.
- [ ] Each ID moves to `Satisfied - automated` only when enforced in the release-evidence Assert path, a promotion
      workflow, merge-required CI, or `ci-gate-spec.yaml`; the evidence pack and PR board rows are updated together.
- [ ] `hardening_tier` gains P1–P3 values only when tier-specific checks are wired.

### Non-negotiable boundary

Closed PR 1–9 rows are not reopened. P2/P3 work is not bundled with P0 gate wiring. Fencing, heartbeat, lock, and
authorization changes update the canonical state-machine authority. SQLite compatibility is preserved.

**PR mapping:** One single-decision PR per hardening ID.

## 12. Production-scale validation

**Status at publication:** Partially satisfied — representative CI fixtures exist; production-scale evidence is not yet
recorded.

**Sources:** [Roadmap — Follow-up Hardening Later](enterprise-readiness-roadmap.md#follow-up-hardening-later),
[Index — Roadmap Status Snapshot](../enterprise-readiness-index.md#roadmap-status-snapshot),
[Operational drill and scale-validation pack — Scale-Validation Guidance](../testing/operational-drill-and-scale-validation-pack.md#scale-validation-guidance).

### Completion criteria

- [ ] A stable staging dataset and performance budget are agreed.
- [ ] Production-scale rebuild, lock refresh, memory, and persistence-load evidence is captured outside normal CI
      (manual, scheduled, or nightly).
- [ ] Each run records environment, graph size, elapsed time, and whether the result is advisory or release-blocking.
- [ ] Data is deterministic and results are attached to an evidence record.
- [ ] PR 7 and roadmap status rows are reconciled to the recorded evidence.

### Non-negotiable boundary

Not added to normal CI. Timing numbers are regression baselines, not SLOs. Runs only against a safe target; no
production data mutation.

**PR mapping:** One single-decision PR for any scheduled harness, and a separate docs PR for recorded evidence.

## 13. Operational drills execution

**Status at publication:** Satisfied - documented — the drill pack defines the drills; no execution evidence is recorded
in the source authorities.

**Sources:** [Roadmap — Follow-up Hardening Later](enterprise-readiness-roadmap.md#follow-up-hardening-later),
[Operational drill and scale-validation pack](../testing/operational-drill-and-scale-validation-pack.md),
[Operational evidence-capture framework](../operations/operational-evidence-capture-framework.md).

### Completion criteria

- [ ] Each drill is executed against a safe target: failed graph load, lock loss, stale owner, degraded DB, and failed
      durable smoke.
- [ ] Each execution has an evidence-matrix row with metrics, logs/events, dashboard/alert, and runbook response
      observed, using an allowed result value.
- [ ] Execution records use `.github/ISSUE_TEMPLATE/operational_drill_evidence.md` and are captured in the
      execution-record register.
- [ ] Named operators are recorded for each run.
- [ ] Every observability or runbook gap found is opened as a separate follow-up item.

### Non-negotiable boundary

Drills run only against safe targets. They do not add a new CI surface. Gaps are not fixed inside the drill record.

**PR mapping:** One single-decision docs PR per drill evidence batch; fixes are separate PRs.

## 14. Multi-region / advanced hosting strategy

**Status at publication:** Partially satisfied / Deferred — too early until single-region durable staging/production
evidence and restore rehearsal are complete.

**Sources:** [Roadmap — Follow-up Hardening Later](enterprise-readiness-roadmap.md#follow-up-hardening-later),
[Operating model — Distributed Hosting Semantics](../enterprise-deployment-operating-model.md#distributed-hosting-semantics),
[ADR 0004](../adr/0004-distributed-hosting-semantics.md).

### Completion criteria

- [ ] Single-region durable release (items 3–8) and restore behaviour (item 7) are repeatable, measured, and costed.
- [ ] A cost and provider model, including provider-specific HA decisions, is documented.
- [ ] A proposed ADR defines the multi-region topology, RPO/RTO implications, and how single-writer rebuild semantics
      hold per graph persistence boundary across regions.
- [ ] The ADR is accepted and the roadmap, index, and operating model are reconciled to it.

### Non-negotiable boundary

No multi-region support claim is made before the ADR is accepted and evidence exists. One rebuild writer per graph
persistence boundary is preserved. Strategy and documentation only; no infrastructure change.

**PR mapping:** One single-decision ADR PR; any implementation is separate later work.

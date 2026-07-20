---
name: Operational drill evidence
about: Capture evidence from one operational drill execution
title: "[DRILL EVIDENCE] "
labels: ["operations", "evidence", "observability", "verification"]
assignees: ""
---

## Metadata

**Drill name:**
**Related issue or PR:**
**Claim being proven:**
**Execution date/time UTC:**
**Operator:**
**Reviewer / approver:**
**Environment:** <!-- local / preview / staging / production / scratch -->
**Target URL or deployment label:**
**Release candidate link, if directly release-scoped:**
**Release commit SHA, if directly release-scoped:**

## Drill Classification

- [ ] Failed graph load
- [ ] Lock loss
- [ ] Stale owner
- [ ] Degraded DB
- [ ] Failed durable smoke

**Mapped hardening ID(s), if any:** <!-- e.g. H-P1-03, H-P2-05 -->
**Result classification:** <!-- Passed / Failed / Blocked / Not run / Manual evidence required / Follow-up required -->

## Expected and Actual Behavior

**Expected behavior:**
**Actual behavior:**
**Did the actual behavior match the expected behavior?**

## Canonical Evidence Object

Capture the artifact using the common evidence grammar from the operational evidence capture framework.

```text
Evidence ID:
Gate / drill:
Claim being proven:
Release candidate / commit SHA:
Environment:
Target URL or deployment label:
Durability label:
Database boundary labels:
  Auth DB:
  Coordination DB:
  Asset Graph DB:
Operator:
Capture timestamp UTC:
Command or observation source:
Expected result:
Actual result:
Relevant fields observed:
Metrics observed:
Logs/events observed:
Dashboard/alert observed:
Runbook step verified:
Result:
Redaction performed:
Follow-up issue(s):
Approver / reviewer:
```

## Drill-Specific Evidence

### Failed graph load

- [ ] `graph.persistence_enabled` observed.
- [ ] `graph_persistence_configured` observed.
- [ ] `graph.persistence_loaded` observed.
- [ ] `graph.startup_source` observed.
- [ ] No false persisted-graph claim was emitted.
- [ ] The expected startup failure or degraded signal was observed.
- [ ] The runbook response was recorded.

### Lock loss

- [ ] Lock holder before the drill was recorded.
- [ ] Lock holder after the drill was recorded.
- [ ] Lock refresh metric or event was observed.
- [ ] Rebuild job status before and after was recorded.
- [ ] The stale-owner mutation result was recorded.
- [ ] The failure or recovery category was recorded.

### Stale owner

- [ ] Owner ID was recorded.
- [ ] Heartbeat timestamp was recorded.
- [ ] Lock expiry timestamp was recorded.
- [ ] Current UTC was recorded.
- [ ] RecoveryGate decision was recorded.
- [ ] New-owner mutation result was recorded.
- [ ] Stale-owner mutation result was recorded.

### Degraded DB

- [ ] The affected boundary was named explicitly.
- [ ] The unaffected boundaries were named explicitly.
- [ ] Health status was recorded.
- [ ] `database.reachable` was recorded where relevant.
- [ ] The relevant log or event was attached.
- [ ] The runbook step followed was recorded.

### Failed durable smoke

- [ ] Hosted readiness command exit status was recorded.
- [ ] Hosted readiness was run with `--require-persistence`.
- [ ] `graph.persistence_enabled` was observed.
- [ ] `graph_persistence_configured` was observed.
- [ ] `graph.persistence_loaded` was observed.
- [ ] `graph.startup_source` was observed.
- [ ] Assets smoke result was recorded.
- [ ] Promotion decision impact was recorded.

## Observability Evidence

**Metric or query evidence:**
**Log or event evidence:**
**Dashboard evidence:**
**Alert state:** <!-- inactive / pending / firing / silenced / not configured / not applicable -->
**Dashboard time range and timezone:**
**Scrape or observation window:**

## Runbook Verification

**Runbook or doc consulted:**
**Runbook step followed:**
**Ambiguity found, if any:**
**Follow-up issue, if needed:**

## Redaction Confirmation

- [ ] No secrets, raw database URLs, bearer tokens, private keys, provider account identifiers, full graph dumps, or raw exception traces are included.
- [ ] Redaction preserved field names, booleans, counts, status labels, timestamps needed for ordering, environment labels, and boundary labels.

## Closure

**Decision:** <!-- Passed / Failed / Blocked / Follow-up required -->
**Decision owner:**
**Decision date:**
**Notes:**

## Related Documents

- [Operational Evidence Capture Framework](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/operations/operational-evidence-capture-framework.md)
- [Operational Drill and Scale-Validation Pack](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/testing/operational-drill-and-scale-validation-pack.md)
- [Release Evidence Pack](https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/main/docs/release-evidence-pack.md)

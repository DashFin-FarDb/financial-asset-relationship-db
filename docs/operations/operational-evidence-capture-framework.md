# Operational Evidence Capture Framework

Status: Active
Parent issue: #1317

## Purpose

This framework defines how operators and reviewers should capture, classify, present, and review operational evidence
without inflating or weakening the claim being made.

It is the common evidence grammar for release evidence, operational drills, restore rehearsals, and bounded
scale-validation. It helps answer a narrow question: does this artifact prove the specific claim it is attached to?

## Scope

This framework applies to:

- release evidence capture;
- operational drill evidence;
- disaster-recovery rehearsal evidence;
- bounded scale-validation evidence;
- review and approval of evidence artifacts.

It does not define runtime behavior, tests, CI workflows, alert rules, dashboards, issue templates, or release gates.

## Evidence Hierarchy

Evidence is tiered by the strength of the claim it can support.

| Evidence tier                  | Proves                                                          | Does not prove                                                |
| ------------------------------ | --------------------------------------------------------------- | ------------------------------------------------------------- |
| Repository automated evidence  | Code, model, or invariant behavior is tested in the repository. | A hosted target is configured correctly.                      |
| Repository documented evidence | A runbook, decision record, or operating rule exists.           | An operator rehearsed the procedure.                          |
| Hosted target evidence         | A named deployment produced the expected result.                | Another environment is safe or equivalent.                    |
| Operational rehearsal evidence | An operator executed the procedure in a controlled environment. | Future executions will always pass.                           |
| Release sign-off evidence      | A named owner accepted the residual risk and approved release.  | Technical proof exists unless the attached artifacts show it. |

Decision rule: do not upgrade evidence tier without artifacts from that tier.

## Canonical Evidence Object

Every evidence artifact should be describable using the same fields.

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

Minimum acceptance rule: evidence without environment, commit, target, expected result, and actual result is not
release-grade evidence.

## Field-Path Reference

Use exact field paths when citing hosted readiness or health evidence.

Required paths:

```text
/api/health/detailed.status
/api/health/detailed.graph_persistence_configured
/api/health/detailed.graph.persistence_enabled
/api/health/detailed.graph.persistence_loaded
/api/health/detailed.graph.startup_source
/api/health/detailed.database.configured
/api/health/detailed.database.reachable
```

Durable graph proof must require all of the following:

```text
graph_persistence_configured == true
graph.persistence_enabled == true
graph.persistence_loaded == true
graph.startup_source == "persisted"
```

Explicitly:

- `status == "healthy"` alone is not durable graph proof.
- `database.reachable == true` alone is not graph persistence proof.
- `graph_persistence_configured == true` alone is not persisted startup proof.

## False-Positive Controls

Do not treat any of the following as stronger evidence than they are:

- CI green as hosted proof.
- `/api/health/detailed.status == healthy` as durable graph proof.
- `graph_persistence_configured == true` as persisted startup proof.
- Auth DB reachability as graph DB proof.
- preview evidence as staging or production proof without an explicit durability label.
- DR runbook existence as restore rehearsal.
- alert absence as proof that no incident occurred.
- expected drill failure as a system failure.
- over-redacted artifacts that omit required proof fields.

## False-Negative Controls

Do not misclassify evidence when one of the following is true:

- hosted readiness fails because the base URL is wrong, includes a path, uses credentials incorrectly, or points to the
  wrong target;
- metrics are missing because the scrape window was missed;
- alerts do not fire because the pending window did not elapse;
- dashboard panels look flat because the time range or labels are wrong;
- a valid empty graph is treated as a failure without checking for an approved sentinel or baseline;
- a stale-owner drill is misclassified because heartbeat or TTL never actually expired;
- DR restore is misclassified because historical lock or job rows were not cleaned before restart;
- scale timing is treated as an SLO instead of a regression baseline.

## Drill-Specific Evidence Requirements

Use the operational drill pack as the source of drill names and drill intent. For each drill, attach the evidence object
fields that prove the exact claim.

### Failed Graph Load

Required evidence:

- graph.startup_source field shows the failure path did not falsely report persisted startup;
- readiness or startup output shows the expected degraded or fail-closed result;
- `application_startup_failure_total` or equivalent startup-failure evidence is observed;
- `graph_startup_source_detected` or `startup_reconciliation_failed` output is attached when applicable.

Pass condition:

- the target fails closed or reports the documented degraded state, and the artifact does not claim durable graph proof.

### Lock Loss

Required evidence:

- lock-loss event or blocked execution output is attached;
- `rebuild_lock_refresh_total{status="failure"}` or equivalent failure evidence is observed;
- the rebuild failure or cancellation evidence is attached;
- any recovery trigger evidence is classified with the exact inconsistency type.

Pass condition:

- mutation stops or fails safely, and stale ownership cannot continue writing state.

### Stale Owner

Required evidence:

- the running job owner, heartbeat age, and lock-state evidence are attached;
- RecoveryGate decision output is attached;
- the artifact shows whether the job was blocked or reset under the canonical authority rules.

Pass condition:

- a fresh foreign owner is not reset; a stale owner is only reset under the documented authority rules.

### Degraded DB

Required evidence:

- the affected boundary is named explicitly;
- the database field-path evidence shows the correct boundary as degraded or unreachable;
- unrelated boundaries are not overclaimed as healthy proof;
- any sanitized connection failure or dependency event is attached.

Pass condition:

- the outage is classified at the correct boundary and does not leak secrets.

### Failed Durable Smoke

Required evidence:

- hosted readiness command output with `--require-persistence`;
- redacted `graph_persistence_configured`, `graph.persistence_loaded`, and `graph.startup_source` evidence;
- target labeling that distinguishes durable from non-durable preview evidence.

Pass condition:

- the smoke fails when durable graph truth is absent or invalid, and the artifact cannot be used for promotion.

## Disaster-Recovery Evidence Requirements

Release-grade restore rehearsal evidence must include:

- restore point;
- source environment;
- scratch or non-production restore target;
- effective database-boundary topology;
- restored boundary verification;
- post-restore and pre-restart coordination cleanup;
- schema and data integrity checks;
- post-restore hosted readiness with `--require-persistence`;
- H-P1-03 `post-restore-readiness` artifact from `post-recovery-readiness.yml` (or linked workflow run);
- redacted `/api/health/detailed`;
- redacted `/api/assets?per_page=1` or approved sentinel evidence;
- RPO and RTO targets plus observations;
- decision and follow-up issue references.

Provider backup availability alone does not complete the DR gate.

## Scale-Validation Evidence Requirements

Scale evidence must stay bounded and deterministic.

- Use fixed graph sizes only.
- Current sizes are 10/20, 250/1,000, and 1,000/5,000 (expressed as assets/relationships).
- Treat timing as a regression baseline, not an SLO, unless explicitly promoted.
- Keep true production-scale validation manual, scheduled, or nightly.
- Do not turn normal PR CI into an unbounded load-test harness.

## Redaction Rules

Evidence must never include:

- raw database URLs;
- credentials;
- bearer tokens;
- private keys;
- full graph dumps;
- raw exception traces;
- provider account identifiers;
- private personal contact details.

Redaction must preserve:

- field names;
- booleans;
- counts;
- status labels;
- timestamps needed to prove ordering;
- environment labels;
- boundary labels.

Over-redaction that removes required proof fields is ambiguous evidence.

## Evidence Review Checklist

- [ ] Does the artifact state the exact claim being proven?
- [ ] Does it identify the environment and target?
- [ ] Does it include the required field paths for the claim?
- [ ] Does it distinguish durable, preview, staging, and production evidence correctly?
- [ ] Does it preserve required counts, booleans, labels, and timestamps?
- [ ] Is the artifact redacted without removing proof?
- [ ] Is the evidence tier correct for the claim?
- [ ] Is the result clearly passed, failed, blocked, not run, manual evidence required, or follow-up required?

## Related Documents

- [Release Evidence Pack](../release-evidence-pack.md)
- [Operational Drill and Scale-Validation Pack](../testing/operational-drill-and-scale-validation-pack.md)
- [Enterprise Readiness Index](../enterprise-readiness-index.md)
- [Staging Deployment Operating Baseline](../staging-deployment-operating-baseline.md)
- [Backup, Restore, and DR Runbook](../runbooks/backup-restore-dr.md)
- [Observability & SLO Master Specification](../OBSERVABILITY_MASTER_SPEC.md)

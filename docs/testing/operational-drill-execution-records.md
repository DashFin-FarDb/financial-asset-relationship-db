# Operational Drill Execution Records

Status: Active tracker
Parent issue: #1328

## Purpose

This register is the repository-side index for actual operational drill execution records.

Use it to point to the evidence issue or release-candidate evidence issue that captured a specific drill run, then
summarize the attached evidence at a glance without duplicating the full artifact set.

This document does not replace the operational drill pack, the evidence capture framework, or the dedicated issue
templates. It links them together.

## Scope

In scope:

- one record row per executed drill run;
- canonical evidence object reference;
- result classification;
- follow-up issue links when the run exposes a defect or gap.

Out of scope:

- running the drills;
- changing runtime behavior;
- changing alert thresholds or dashboards;
- duplicating the full drill artifact set inside this register.

## Canonical Evidence Object

Use the repository evidence grammar when attaching or summarizing a drill execution record.

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

## Execution Register

Use one row per actual drill execution. If the drill has not been run yet, leave the row open and keep the parent
issue open.

| Drill | Execution issue / evidence link | Environment | Commit SHA | Result | Notes | Follow-up issue |
| --- | --- | --- | --- | --- | --- | --- |
| Failed graph load |  |  |  | Not run |  |  |
| Lock loss |  |  |  | Not run |  |  |
| Stale owner |  |  |  | Not run |  |  |
| Degraded DB |  |  |  | Not run |  |  |
| Failed durable smoke |  |  |  | Not run |  |  |

Allowed result values:

- Passed
- Failed
- Blocked
- Not run
- Manual evidence required
- Follow-up required

## Recording Rules

- Open one dedicated operational drill evidence issue per drill run by default.
- Link the drill evidence issue here once the record is complete.
- Update the release-candidate evidence issue only when the drill is directly release-scoped or release-blocking.
- Create a focused follow-up issue for any missing metric, ambiguous dashboard, flaky drill, or unsafe runtime behavior.

## Related Documents

- [Operational Drill and Scale-Validation Pack](operational-drill-and-scale-validation-pack.md)
- [Operational Evidence Capture Framework](../operations/operational-evidence-capture-framework.md)
- [Operational Drill Evidence Issue Template](../../.github/ISSUE_TEMPLATE/operational_drill_evidence.md)
- [Release Candidate Evidence Template](../../.github/ISSUE_TEMPLATE/release_candidate_evidence.md)
- [Release Evidence Pack](../release-evidence-pack.md)

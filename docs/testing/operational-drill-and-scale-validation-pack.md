# Operational Drill and Scale-Validation Pack

Status: Active
Issue: #1317

## Purpose

This pack defines a bounded set of operational drills and representative-scale validation checks that prove the
observability, SLOs, dashboards, alerts, and runbooks answer real incidents rather than existing only as static
documentation.

It is intentionally deterministic and CI-safe. It does not turn normal PR validation into a production-scale
load-test harness.

## Scope

### In scope

- 5 operational drills covering representative failure modes.
- Trigger, expected runtime behavior, metrics, logs/events, dashboard/alert evidence, and runbook response for each drill.
- Deterministic, fixed-size graph validation where it stays bounded and repeatable.
- Evidence-capture guidance that operators can fill in after a manual drill.

### Out of scope

- New hosting architecture.
- Normal CI production-scale load testing.
- Release-candidate evidence capture.
- DR restore rehearsal replacement.
- Security scanner policy changes.

## Drill Catalog

The current drill set is chosen to exercise the control-plane boundaries already documented in the repository:

1. Failed graph load drill.
2. Lock loss drill.
3. Stale owner drill.
4. Degraded database drill.
5. Failed durable smoke drill.

### 1. Failed Graph Load Drill

- Trigger: force graph persistence load failure in a safe non-production target.
- Expected behavior: startup/readiness fails closed or reports a degraded state according to the startup contract.
- Metrics to watch: `application_startup_failure_total`, `graph_rebuild_recovery_trigger_total`, and the
  `graph_persistence_configured` / `persistence_loaded` / `startup_source` fields in `/api/health/detailed`.
- Logs / events to watch: `graph_startup_source_detected` and `startup_reconciliation_failed`, plus the sanitized
  startup failure event emitted by the application lifecycle path.
- Dashboard / alert focus: Application Lifecycle row, SLO Overview row, and any persistence-readiness alert surface.
- Runbook response: diagnose persistence configuration and follow the restore / recovery path before retrying
  promotion.

### 2. Lock Loss Drill

- Trigger: simulate distributed lock loss during rebuild or make lock refresh fail.
- Expected behavior: rebuild execution stops or fails safely; stale ownership cannot continue mutating state.
- Metrics to watch: `rebuild_lock_refresh_total{status="failure"}`,
  `rebuild_heartbeat_last_success_timestamp`, `graph_rebuild_recovery_trigger_total`,
  `graph_rebuild_failure_total`, and `graph_rebuild_state_transition_total`.
- Logs / events to watch: `graph_rebuild_recovery_trigger_total`-backed recovery events, `reconciliation_loop_blocked`
  when the loop refuses execution, rebuild failure events, and blocked execution output from the recovery path.
- Dashboard / alert focus: Rebuild Liveness & Heartbeat row, Rebuild Resilience & Recovery row, and the relevant
  recovery alert panels.
- Runbook response: confirm lock ownership, inspect the active writer, and stop any stale writer before retrying.

### 3. Stale Owner Drill

- Trigger: create a running rebuild job with an expired heartbeat and a stale active worker record.
- Expected behavior: RecoveryGate blocks or resets according to the canonical authority rules; a fresh foreign owner
  must not be reset.
- Metrics to watch: `graph_rebuild_recovery_trigger_total`, `graph_rebuild_state_transition_total`,
  `rebuild_lock_acquisition_total`, and `rebuild_heartbeat_last_success_timestamp`.
- Logs / events to watch: recovery-gate decision logs, stale-owner detection events, and `reconciliation_loop_blocked`
  output when a fresh foreign owner prevents mutation.
- Dashboard / alert focus: Rebuild Resilience & Recovery row and the SLO Overview row.
- Runbook response: verify ownership authority, then either allow the stale owner reset path or escalate to manual
  investigation if the lock state is unsafe.

### 4. Degraded Database Drill

- Trigger: make the coordination, auth, or graph persistence database temporarily unavailable in a safe target.
- Expected behavior: affected dependency reports degraded / unavailable without leaking secrets; unrelated boundaries
  should remain correctly classified.
- Metrics to watch: `application_startup_failure_total`, `rebuild_lock_refresh_total{status="failure"}`,
  `graph_rebuild_failure_total`, and `reconciliation_duration_seconds`.
- Logs / events to watch: sanitized database connection failures, degraded dependency events, and any recovery-gate
  blocking event that results from the outage.
- Dashboard / alert focus: Application Lifecycle row, Reconciliation Drift row, and the database-specific alert view.
- Runbook response: diagnose the failing boundary, verify the affected database URL, and avoid treating a healthy
  unrelated boundary as evidence of full system health.

### 5. Failed Durable Smoke Drill

- Trigger: run hosted readiness with `--require-persistence` against a target without durable graph truth or with an
  intentionally invalid durable graph configuration.
- Expected behavior: the smoke fails and cannot be used as promotion evidence.
- Metrics to watch: `graph_persistence_configured`, `persistence_loaded`, `startup_source`, and the hosted readiness
  command exit status.
- Logs / events to watch: hosted readiness diagnostic output and the startup source evidence returned by the target.
- Dashboard / alert focus: Promotion evidence workflow and any readiness gating dashboard that consumes the smoke.
- Runbook response: remediate the graph persistence boundary before retrying promotion.

## Evidence Matrix

Record each drill with a compact evidence row. Use one row per drill execution.

| Drill | Triggered in | Expected behavior | Metrics observed | Logs / events observed | Dashboard / alert observed | Runbook response verified | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Failed graph load |  |  |  |  |  |  | Not run |
| Lock loss |  |  |  |  |  |  | Not run |
| Stale owner |  |  |  |  |  |  | Not run |
| Degraded DB |  |  |  |  |  |  | Not run |
| Failed durable smoke |  |  |  |  |  |  | Not run |

Allowed result values:

- Passed
- Failed
- Blocked
- Not run
- Manual evidence required
- Follow-up required

## Scale-Validation Guidance

Representative scale checks should stay deterministic, fixed-size, and broad enough to catch regressions without
creating a production-scale harness in normal CI.

Current bounded sizes already used by the repository:

- small: 10 assets / 20 relationships
- representative: 250 assets / 1,000 relationships
- upper representative: 1,000 assets / 5,000 relationships

Rules:

- Keep the data deterministic.
- Keep CI guardrails broad enough to avoid flake.
- Treat timing numbers as regression baselines, not SLOs.
- Keep true production-scale validation manual, scheduled, or nightly.
- Record the environment, graph size, elapsed time, and whether the result is advisory or release-blocking.

Current automated anchors:

- `tests/integration/test_distributed_hosting_failure_modes.py`
- `tests/integration/test_graph_persistence_scale_validation.py`
- `docs/testing/failure-mode-and-scale-validation.md`

## How To Use This Pack

1. Choose one drill and run it only against a safe target.
2. Capture the metrics, logs, dashboard evidence, and runbook response.
3. Record the result in the evidence matrix.
4. Keep any discovered observability or runbook gap as a separate follow-up item.

## Related Documents

- `docs/release-evidence-pack.md`
- `docs/release-checklist.md`
- `docs/enterprise-deployment-operating-model.md`
- `docs/governance/state-machine-and-operating-authority.md`
- `docs/runbooks/backup-restore-dr.md`
- `docs/OBSERVABILITY_MASTER_SPEC.md`
- `docs/testing/failure-mode-and-scale-validation.md`

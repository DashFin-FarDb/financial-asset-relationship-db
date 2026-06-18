# Observability & SLO Master Specification

**Date:** June 18, 2026
**Status:** Implemented

## 1. Executive Summary
This document serves as the single source of truth for the project's observability architecture, Service Level Objectives (SLOs), and telemetry design. It catalogs all telemetry emitted by the application, outlines the required Prometheus and Grafana infrastructure, and documents the explicit engineering decisions made to ensure the observability layer is scalable, safe, and maintainable at an enterprise scale.

## 2. Key Design Decisions & "The Why"

To ensure the observability infrastructure can withstand production loads without creating secondary failure modes (e.g., Prometheus Out of Memory panics or Grafana dashboard timeouts), several critical design decisions were made.

### 2.1 Preventing Cardinality Explosions
**Decision:** Extract Starlette route templates (`/assets/{id}`) instead of raw URL paths for HTTP metrics.
**Why:** Grouping metrics by dynamically generated REST paths (e.g. `/assets/123`, `/assets/456`) results in unbounded cardinality, destroying the Prometheus TSDB. The FastAPI `RequestMetricsMiddleware` explicitly bypasses raw paths by reaching into the Starlette `scope` to retrieve the matched route template.

### 2.2 Decoupled Histogram Buckets
**Decision:** Explicitly separate HTTP latency buckets from Rebuild duration buckets.
**Why:** A common mistake is reusing HTTP buckets `(0.01s ... 5s)` for long-running operations. Doing so forces all long-running tasks into the `+Inf` bucket, completely destroying visibility.
- HTTP requests utilize sub-second buckets.
- Rebuild operations utilize minute-scale buckets `(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)`.

### 2.3 Explicit State Transitions vs Gauges
**Decision:** Augment state gauges with `graph_rebuild_state_transition_total` counters.
**Why:** Relying exclusively on gauges (e.g. `RUNNING=2`, `SUCCESS=3`) makes it computationally expensive to track the exact number of transitions over time. Transition counters explicitly log the `from_state` and `to_state`, dramatically improving operational debugging and state-machine analytics.

### 2.4 Error Budget Math: `increase()` vs `rate()`
**Decision:** Use `increase(metric[30d])` instead of `rate(metric[30d])` for calculating monthly Error Budgets.
**Why:** Utilizing `rate()` for massive vectors over 30 days is a known anti-pattern in PromQL that strains the evaluation engine. `increase()` strictly tracks the counter growth and correctly handles counter resets.

### 2.5 Provisioning Recording Rules
**Decision:** Native dashboard calculations for SLOs are offloaded to Prometheus Recording Rules.
**Why:** Querying high-resolution 30-day windows directly in Grafana panels causes significant performance degradation and browser freezes. Pre-computing values like `fardb:availability_5m` or `fardb:rebuild_p95_duration` shifts the compute burden securely to Prometheus.

---

## 3. Catalog of Implemented Metrics

The application telemetry is centralized in `api/metrics.py`.

### 3.1 Application Lifecycle
- `application_startup_duration_seconds` (Histogram): Evaluates application startup health.
- `application_startup_success_total` (Counter): Tracking zero-downtime deployment success.
- `application_startup_failure_total` (Counter): Crash loop detection.

### 3.2 State Machine & Rebuild Analytics
- `graph_rebuild_state_transition_total` (Counter): Tracks state transitions. Labels: `from_state`, `to_state`.
- `graph_rebuild_cancelled_total` (Counter): Monitors cancellation architecture.
- `reconciliation_duration_seconds` (Histogram): Tracks drift evaluator pass durations.
- `graph_rebuild_duration_seconds` (Histogram): Tracks total execution duration of graph generation.

### 3.3 Distributed Coordination & Resilience
- `rebuild_lock_acquisition_total` (Counter): Exposes lock contention. Labels: `status`.
- `rebuild_lock_refresh_total` (Counter) & `rebuild_lock_refresh_duration_seconds` (Histogram): Monitors lock maintenance heartbeat.
- `rebuild_heartbeat_update_total` (Counter) & `rebuild_heartbeat_last_success_timestamp` (Gauge): Provides liveness detection.
- `graph_rebuild_recovery_trigger_total` (Counter): Tracks when the reconciliation engine forces an intervention. Labels: `inconsistency_type`.

### 3.4 API Core
- `http_requests_total` (Counter): Labels: `method`, `route`, `status_group`.
- `http_request_duration_seconds` (Histogram): Labels: `method`, `route`, `status_group`.

---

## 4. SLO Definitions & Alert Rules

To prevent alert fatigue, alerts are built strictly against Service Level Objectives (SLOs) and internal system invariants.

### API Availability (Target: 99.9%)
- **Alert:** `ApiAvailabilityFastBurn`
- **Trigger:** Fast-burn error rate > 0.005 over 5 minutes.

### API Latency (Target: P95 < 0.5s)
- **Alert:** `ApiLatencyP95High`
- **Trigger:** P95 latency exceeds 0.5 seconds for > 10m.

### Rebuild Failure Detection (Target: 99.5% Success)
- **Alerts:** `RebuildFailuresDetected` (Warning), `RebuildFailuresCritical` (Critical)
- **Trigger:** >0 failures in 15m (Warning), >=3 failures in 1h (Critical).

### Liveness & Heartbeats
- **Alert:** `RebuildHeartbeatStale`
- **Trigger:** Difference between `time()` and `rebuild_heartbeat_last_success_timestamp` exceeds 120 seconds.
- **Why it matters:** Arguably the highest-value alert in the system. It detects zombie executors, deadlocked workers, or complete database disconnects during rebuild operations.

### Reconciliation & Drift
- **Alert:** `CriticalDriftDetected`
- **Trigger:** Critical severity drift reported by the reconciliation engine.
- **Alert:** `RecoveryStorm`
- **Trigger:** Auto-recovery triggered > 5 times in 1h, indicating systemic instability.

---

## 5. Dashboard Architecture (Grafana)

The master dashboard is partitioned into 8 thematic rows, designed for rapid incident response:

1. **SLO Overview (11 panels):** Live status against API Availability (99.9%), Startup Success (99%), Rebuild Success (99.5%), and remaining Error Budgets.
2. **API Health (5 panels):** Latency heatmaps, throughput, and error rates grouped by route.
3. **Application Lifecycle (4 panels):** Deployment markers, startup durations, and crash rates.
4. **Rebuild State Machine (5 panels):** Live queue depths, active job states, and transition throughput.
5. **Rebuild Execution Latency (3 panels):** P50/P90/P99 latency bounds.
6. **Rebuild Liveness & Heartbeat (4 panels):** Seconds since last heartbeat, lock refresh latencies.
7. **Rebuild Resilience & Recovery (4 panels):** Inconsistency events, recovery triggers, crash anomalies.
8. **Reconciliation Drift (5 panels):** Active drift volume, drift severities, and reconciliation evaluation durations.

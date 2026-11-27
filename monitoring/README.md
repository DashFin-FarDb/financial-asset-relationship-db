# Observability & Monitoring Integration

This directory contains the infrastructure-as-code definitions for the project's monitoring stack, including Grafana dashboards, Prometheus alerting rules, and Loki log aggregations.

## Directory Structure

```text
monitoring/
├── alertmanager/
│   └── alertmanager.yml      # Severity-based alert routing (critical/warning + inhibit rules)
├── alerts/                   # Prometheus & Loki rules
│   ├── api-alerts.yml        # Latency, Error Rate, and In-flight alerts
│   ├── rebuild-alerts.yml    # Rebuild duration and failure alerts
│   ├── slo-alerts.yml        # Multi-window burn rate and compliance alerts
│   ├── fardb_starter_production_alerts.yml
│   └── loki-recording.yml    # Log-to-Metric aggregations (pre-computed log counts)
├── dashboards/               # Grafana JSON exports (auto-provisioned into FarDB folder)
│   ├── api-overview.json     # Global API health and performance
│   ├── rebuild-operations.json # Graph rebuild lifecycle tracking
│   └── slo-compliance.json   # SLO burn rates and compliance status
├── prometheus/
│   └── prometheus.yml        # Scrape config (/api/metrics), alert rules, Alertmanager target
└── provisioning/             # Grafana auto-configuration
    ├── datasources.yml       # Data source definitions for Prometheus/Loki
    ├── dashboards.yml        # Grafana file-based dashboard provider
    └── fardb_starter_recording_rules.yml
```

## Quick Start (Docker Compose)

Start Prometheus (`:9090`), Alertmanager (`:9093`), and Grafana (`:3001`) with all three FarDB dashboards auto-provisioned:

```bash
export GF_SECURITY_ADMIN_PASSWORD="replace-with-a-strong-password"
docker compose -f docker-compose.observability.yml up -d
```

Grafana opens directly to `api-overview.json`, with `rebuild-operations.json` and `slo-compliance.json` provisioned under the **FarDB** folder. To route alerts to Slack or PagerDuty in hosted environments, mount secret files into `monitoring/alertmanager/alertmanager.yml` (`api_url_file` / `routing_key_file`).

## Setup Instructions

### 1. Prometheus Configuration

Add the following to your `prometheus.yml` under the `rule_files` section:

```yaml
rule_files:
  - "/etc/prometheus/alerts/*.yml"
```

Ensure the contents of `monitoring/alerts/` are mapped to that directory.

### 2. Grafana Provisioning

To automatically load the data sources and dashboards:

1.  Copy `provisioning/datasources.yml` to your Grafana `/etc/grafana/provisioning/datasources/` directory.
2.  Create a dashboard provider in `/etc/grafana/provisioning/dashboards/` pointing to the `monitoring/dashboards/` folder.

Example `dashboards-provider.yml`:

```yaml
apiVersion: 1
providers:
  - name: "Standard Dashboards"
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /etc/grafana/dashboards
```

### 3. SLO Burn Rate Alerts

The `slo-alerts.yml` file implements the Google SRE standard for **Multi-Window Multi-Burn-Rate Alerting**.

- **Fast Burn:** Alerts if the error budget is being consumed at a rate that will exhaust the monthly budget in **24 hours**. (Severity: Critical)
- **Slow Burn:** Alerts if the budget will be exhausted in **3 days**. (Severity: Warning)

These alerts use both a short window (to detect spikes) and a long window (to ensure persistence) to minimize alert noise while preserving sensitivity.

### 4. In-Process SLO Evaluator

`api/slo_evaluator.py` periodically evaluates SLOs from the process-local Prometheus registry and logs an ERROR on each compliance breach transition.

- `SLO_API_LATENCY_AVG_SECONDS` (default `0.1`): average request latency threshold.
- `SLO_API_LATENCY_MIN_REQUESTS` (default `20`): the latency SLO is reported compliant until this many requests have been observed, so cold-start-dominated samples on new serverless instances do not raise breaches. During that warm-up `/api/slo/status` may show a negative margin while compliant. Set to `0` to disable the gate.

## Canonical Schema Usage

All dashboards and alerts rely on the **Phase 3 Observability Layer**:

- **Metrics:** Standardized Prometheus metrics defined in `api/metrics.py`.
- **Logs:** Structured JSON logs emitted via `src/observability/events.py`. Loki queries use the `event` label to filter for specific domain events (e.g., `graph_rebuild_failed`).

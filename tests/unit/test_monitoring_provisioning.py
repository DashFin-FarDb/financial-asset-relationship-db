"""Validation tests for Grafana dashboards, Prometheus config, Alertmanager routing, and compose wiring."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MONITORING_DIR = REPO_ROOT / "monitoring"


def test_grafana_dashboard_json_files_parse_and_have_panels() -> None:
    """All Grafana dashboard JSON files parse cleanly and define non-empty panel lists."""
    dashboards = sorted((MONITORING_DIR / "dashboards").glob("*.json"))
    expected = {"api-overview.json", "rebuild-operations.json", "slo-compliance.json"}
    assert expected.issubset({d.name for d in dashboards})

    for dashboard_path in dashboards:
        payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), f"{dashboard_path.name} must be a JSON object"
        assert payload.get("title"), f"{dashboard_path.name} must have a non-empty title"
        panels = payload.get("panels", [])
        assert isinstance(panels, list) and len(panels) > 0, f"{dashboard_path.name} must define panels"


def test_grafana_provisioning_files_wire_datasources_and_dashboards() -> None:
    """Grafana provisioning YAML files configure Prometheus/Loki datasources and dashboard provider."""
    datasources = yaml.safe_load((MONITORING_DIR / "provisioning" / "datasources.yml").read_text(encoding="utf-8"))
    ds_names = {item["name"] for item in datasources["datasources"]}
    assert {"Prometheus", "Loki"}.issubset(ds_names)

    dashboards_cfg = yaml.safe_load((MONITORING_DIR / "provisioning" / "dashboards.yml").read_text(encoding="utf-8"))
    providers = dashboards_cfg["providers"]
    assert len(providers) >= 1
    assert providers[0]["options"]["path"] == "/etc/grafana/dashboards"


def test_prometheus_and_alertmanager_configs_are_valid() -> None:
    """Prometheus scrapes /api/metrics, loads alert rules, and forwards alerts to Alertmanager."""
    prom = yaml.safe_load((MONITORING_DIR / "prometheus" / "prometheus.yml").read_text(encoding="utf-8"))
    jobs = {job["job_name"]: job for job in prom["scrape_configs"]}
    assert "fardb-api" in jobs
    assert jobs["fardb-api"]["metrics_path"] == "/api/metrics"
    assert len(prom["rule_files"]) >= 4
    assert prom["alerting"]["alertmanagers"][0]["static_configs"][0]["targets"] == ["alertmanager:9093"]

    am = yaml.safe_load((MONITORING_DIR / "alertmanager" / "alertmanager.yml").read_text(encoding="utf-8"))
    receiver_names = {r["name"] for r in am["receivers"]}
    assert {"default-webhook", "critical-paging", "warning-notifications"}.issubset(receiver_names)
    assert len(am["inhibit_rules"]) >= 1


def test_observability_compose_mounts_dashboards_and_pins_images() -> None:
    """docker-compose.observability.yml mounts dashboards/provisioning and avoids :latest tags."""
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.observability.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert {"prometheus", "alertmanager", "grafana"}.issubset(services.keys())

    for name, svc in services.items():
        image = svc["image"]
        assert ":" in image and not image.endswith(":latest"), f"Service {name} must pin an explicit image tag"

    grafana_volumes = "\n".join(services["grafana"]["volumes"])
    assert "monitoring/provisioning/dashboards.yml" in grafana_volumes
    assert "monitoring/provisioning/datasources.yml" in grafana_volumes
    assert "monitoring/dashboards:/etc/grafana/dashboards:ro" in grafana_volumes

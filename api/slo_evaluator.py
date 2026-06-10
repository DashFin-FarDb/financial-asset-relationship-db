"""SLO Evaluator for querying Prometheus metrics and determining compliance."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from prometheus_client import REGISTRY

from api.metrics import update_slo_compliance_status
from src.config.settings import Settings, get_settings
from src.observability.events import SLOBreachEvent
from src.observability.facade import log_event

logger = logging.getLogger(__name__)


@dataclass
class SLOEvaluationResult:
    """Result of an SLO evaluation."""

    slo_name: str
    is_compliant: bool
    current_value: float
    threshold: float
    margin: float


class SLOEvaluator:
    """
    Evaluates SLOs against current metrics.

    NOTE: This evaluator operates on cumulative, in-memory metrics from the local registry.
    It reflects compliance since the process started (lifetime averages). For windowed
    or historical SLO compliance, refer to the Grafana dashboards and Prometheus alerts.
    """

    # Shared state to track last known compliance to prevent log flooding
    _last_compliance: dict[str, bool] = {}

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the SLO Evaluator with configuration settings."""
        self.settings = settings or get_settings()
        self._trigger_side_effects = True

    def _collect_metrics(self) -> dict[str, float]:
        """Collect all required metrics in a single pass over the registry."""
        metrics = {
            "http_duration_sum": 0.0,
            "http_duration_count": 0.0,
            "rebuild_duration_sum": 0.0,
            "rebuild_duration_count": 0.0,
            "http_requests_total": 0.0,
            "http_requests_error": 0.0,
        }
        for metric in REGISTRY.collect():
            if metric.name == "http_request_duration_seconds":
                self._process_duration_samples(metric, metrics, "http_duration")
            elif metric.name == "graph_rebuild_duration_seconds":
                self._process_duration_samples(metric, metrics, "rebuild_duration")
            elif metric.name == "http_requests":  # prometheus_client strips _total from metric.name
                self._process_request_samples(metric, metrics)
        return metrics

    def _process_duration_samples(self, metric: Any, metrics: dict[str, float], prefix: str) -> None:
        """Process duration metric samples to sum sum and count values."""
        for sample in metric.samples:
            if sample.name == f"{metric.name}_sum":
                metrics[f"{prefix}_sum"] += sample.value
            elif sample.name == f"{metric.name}_count":
                metrics[f"{prefix}_count"] += sample.value

    def _process_request_samples(self, metric: Any, metrics: dict[str, float]) -> None:
        """Process HTTP request samples to sum total and error counts."""
        for sample in metric.samples:
            if sample.name == "http_requests_total":
                metrics["http_requests_total"] += sample.value
                status_group = sample.labels.get("status_group", "2xx")
                if status_group.startswith("5"):
                    metrics["http_requests_error"] += sample.value

    def evaluate_api_latency(self, metrics: dict[str, float]) -> SLOEvaluationResult:
        """Evaluate lifetime average API latency against the threshold."""
        total_duration = metrics.get("http_duration_sum", 0.0)
        total_requests = metrics.get("http_duration_count", 0.0)

        current_avg = total_duration / total_requests if total_requests > 0 else 0.0
        threshold = self.settings.slo_api_latency_avg_seconds

        is_compliant = current_avg <= threshold
        margin = threshold - current_avg

        self._record_and_log(
            slo_name="api_latency",
            is_compliant=is_compliant,
            current_value=current_avg,
            threshold=threshold,
        )

        return SLOEvaluationResult(
            slo_name="api_latency",
            is_compliant=is_compliant,
            current_value=current_avg,
            threshold=threshold,
            margin=margin,
        )

    def _check_rebuild_breach(self, threshold: float) -> bool:
        """Check histogram buckets for any rebuild exceeding threshold."""
        for metric in REGISTRY.collect():
            if metric.name != "graph_rebuild_duration_seconds":
                continue
            if self._is_bucket_breached(metric.samples, threshold):
                return True
        return False

    def _is_bucket_breached(self, samples: Any, threshold: float) -> bool:
        """Inspect samples to see if any count exists outside the threshold bucket."""
        total_count = 0.0
        le_count = 0.0

        for sample in samples:
            if sample.name.endswith("_count"):
                total_count = sample.value
                continue

            if not sample.name.endswith("_bucket"):
                continue

            le = float(sample.labels.get("le", 0.0))

            if le <= threshold:
                le_count = max(le_count, sample.value)

        return total_count > le_count

    def evaluate_rebuild_duration(self, metrics: dict[str, float]) -> SLOEvaluationResult:
        """Evaluate if any rebuild duration exceeded the maximum threshold."""
        threshold = float(self.settings.slo_rebuild_duration_max_seconds)
        any_breach = self._check_rebuild_breach(threshold)

        total_duration = metrics.get("rebuild_duration_sum", 0.0)
        total_rebuilds = metrics.get("rebuild_duration_count", 0.0)
        current_avg = total_duration / total_rebuilds if total_rebuilds > 0 else 0.0

        is_compliant = not any_breach

        # If we have a breach, the 'current_value' being an average is misleading if the breach was a spike.
        # However, for lifetime reporting, we'll keep the average but ensure is_compliant is correct.
        margin = threshold - current_avg

        self._record_and_log(
            slo_name="rebuild_duration",
            is_compliant=is_compliant,
            current_value=current_avg,
            threshold=threshold,
        )

        return SLOEvaluationResult(
            slo_name="rebuild_duration",
            is_compliant=is_compliant,
            current_value=current_avg,
            threshold=threshold,
            margin=margin,
        )

    def evaluate_error_rate(self, metrics: dict[str, float]) -> SLOEvaluationResult:
        """Evaluate the overall API HTTP error rate against the error rate threshold."""
        total_requests = metrics.get("http_requests_total", 0.0)
        error_requests = metrics.get("http_requests_error", 0.0)

        current_error_rate = error_requests / total_requests if total_requests > 0 else 0.0
        threshold = self.settings.slo_error_rate_threshold

        is_compliant = current_error_rate <= threshold
        margin = threshold - current_error_rate

        self._record_and_log(
            slo_name="error_rate",
            is_compliant=is_compliant,
            current_value=current_error_rate,
            threshold=threshold,
        )

        return SLOEvaluationResult(
            slo_name="error_rate",
            is_compliant=is_compliant,
            current_value=current_error_rate,
            threshold=threshold,
            margin=margin,
        )

    def evaluate_all(self, trigger_side_effects: bool = True) -> list[SLOEvaluationResult]:
        """Run all SLO evaluations and return the results.

        Args:
            trigger_side_effects: If True, update Prometheus gauges and log breach transitions.
        """
        self._trigger_side_effects = trigger_side_effects
        metrics = self._collect_metrics()

        return [
            self.evaluate_api_latency(metrics),
            self.evaluate_rebuild_duration(metrics),
            self.evaluate_error_rate(metrics),
        ]

    def _record_and_log(self, slo_name: str, is_compliant: bool, current_value: float, threshold: float) -> None:
        """Update the prometheus metric and log an event ONLY on transition to breach."""
        if not self._trigger_side_effects:
            return

        update_slo_compliance_status(slo_name, is_compliant)

        prev_compliant = self._last_compliance.get(slo_name, True)

        if not is_compliant and prev_compliant:
            # Transition from compliant to breached
            log_event(
                logger,
                logging.ERROR,
                SLOBreachEvent(
                    event="slo_breach_detected",
                    message=f"SLO '{slo_name}' breached! Current: {current_value:.4f}, Threshold: {threshold:.4f}",
                    metadata={
                        "slo_name": slo_name,
                        "current_value": current_value,
                        "threshold": threshold,
                    },
                ),
            )
        elif is_compliant and not prev_compliant:
            # Transition from breached to compliant (recovery)
            log_event(
                logger,
                logging.INFO,
                SLOBreachEvent(
                    event="slo_recovery_detected",
                    message=f"SLO '{slo_name}' recovered. Current: {current_value:.4f}, Threshold: {threshold:.4f}",
                    metadata={
                        "slo_name": slo_name,
                        "current_value": current_value,
                        "threshold": threshold,
                    },
                ),
            )

        self._last_compliance[slo_name] = is_compliant

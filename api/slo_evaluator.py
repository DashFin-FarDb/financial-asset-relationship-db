"""SLO Evaluator for querying Prometheus metrics and determining compliance."""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
    """Evaluates SLOs against current metrics."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the SLO Evaluator with configuration settings."""
        self.settings = settings or get_settings()

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
                for sample in metric.samples:
                    if sample.name == "http_request_duration_seconds_sum":
                        metrics["http_duration_sum"] += sample.value
                    elif sample.name == "http_request_duration_seconds_count":
                        metrics["http_duration_count"] += sample.value
            elif metric.name == "graph_rebuild_duration_seconds":
                for sample in metric.samples:
                    if sample.name == "graph_rebuild_duration_seconds_sum":
                        metrics["rebuild_duration_sum"] += sample.value
                    elif sample.name == "graph_rebuild_duration_seconds_count":
                        metrics["rebuild_duration_count"] += sample.value
            elif metric.name == "http_requests":  # prometheus_client strips _total from metric.name
                for sample in metric.samples:
                    if sample.name == "http_requests_total":
                        metrics["http_requests_total"] += sample.value
                        status_group = sample.labels.get("status_group", "2xx")
                        if status_group.startswith("5"):
                            metrics["http_requests_error"] += sample.value
        return metrics

    def evaluate_api_latency(self, metrics: dict[str, float]) -> SLOEvaluationResult:
        """Evaluate average API latency against the average threshold as a proxy for performance."""
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

    def evaluate_rebuild_duration(self, metrics: dict[str, float]) -> SLOEvaluationResult:
        """Evaluate average rebuild duration against the max duration threshold."""
        total_duration = metrics.get("rebuild_duration_sum", 0.0)
        total_rebuilds = metrics.get("rebuild_duration_count", 0.0)

        current_avg = total_duration / total_rebuilds if total_rebuilds > 0 else 0.0
        threshold = float(self.settings.slo_rebuild_duration_max_seconds)

        is_compliant = current_avg <= threshold
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

    def evaluate_all(self) -> list[SLOEvaluationResult]:
        """Run all SLO evaluations and return the results."""
        metrics = self._collect_metrics()
        return [
            self.evaluate_api_latency(metrics),
            self.evaluate_rebuild_duration(metrics),
            self.evaluate_error_rate(metrics),
        ]

    def _record_and_log(self, slo_name: str, is_compliant: bool, current_value: float, threshold: float) -> None:
        """Update the prometheus metric and log an event if breached."""
        update_slo_compliance_status(slo_name, is_compliant)

        if not is_compliant:
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

"""SLO Evaluator for querying Prometheus metrics and determining compliance."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from prometheus_client import REGISTRY

from api.metrics import update_slo_compliance_status
from src.config.slo import SLOSettings, get_slo_settings
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

    def __init__(self, settings: SLOSettings | None = None) -> None:
        """Initialize the SLO Evaluator with configuration settings."""
        self.settings = settings or get_slo_settings()

    def _sum_samples(self, metric_name: str, suffix: str = "") -> float:
        """Sum all sample values for a given metric across all labels.

        Args:
            metric_name: The base name of the metric.
            suffix: Optional suffix for the sample name (e.g., '_total', '_sum', '_count').
        """
        total = 0.0
        target_sample_name = f"{metric_name}{suffix}" if suffix else metric_name
        for metric in REGISTRY.collect():
            if metric.name == metric_name:
                for sample in metric.samples:
                    if sample.name == target_sample_name:
                        total += sample.value
        return total

    def evaluate_api_latency(self) -> SLOEvaluationResult:
        """Evaluate average API latency against the P50 threshold as a proxy for performance."""
        # Note: True P99/P50 requires PromQL histogram_quantile over time.
        # For internal app evaluation, we approximate by checking the overall average latency.
        total_duration = self._sum_samples("http_request_duration_seconds", "_sum")
        total_requests = self._sum_samples("http_request_duration_seconds", "_count")

        current_avg = total_duration / total_requests if total_requests > 0 else 0.0
        threshold = self.settings.slo_api_latency_p50_seconds

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

    def evaluate_rebuild_duration(self) -> SLOEvaluationResult:
        """Evaluate average rebuild duration against the max duration threshold."""
        total_duration = self._sum_samples("graph_rebuild_duration_seconds", "_sum")
        total_rebuilds = self._sum_samples("graph_rebuild_duration_seconds", "_count")

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

    def evaluate_error_rate(self) -> SLOEvaluationResult:
        """Evaluate the overall API HTTP error rate against the error rate threshold."""
        total_requests = 0.0
        error_requests = 0.0

        for metric in REGISTRY.collect():
            if metric.name == "http_requests_total":
                for sample in metric.samples:
                    total_requests += sample.value
                    status_group = sample.labels.get("status_group", "2xx")
                    if status_group.startswith("5"):
                        error_requests += sample.value

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
        return [
            self.evaluate_api_latency(),
            self.evaluate_rebuild_duration(),
            self.evaluate_error_rate(),
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

"""Tests for the SLO Evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from prometheus_client import CollectorRegistry, Counter, Histogram

from api.slo_evaluator import SLOEvaluator
from src.config.settings import Settings

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class SLOExpectation:
    """Grouped expected results for SLO evaluation tests."""

    method_name: str
    metrics: dict[str, float]
    slo_name: str
    is_compliant: bool
    value: float
    threshold: float


@pytest.fixture
def mock_settings() -> Settings:
    """Provide a basic settings fixture."""
    return Settings(
        slo_api_latency_avg_seconds=0.1,
        slo_rebuild_duration_max_seconds=300,
        slo_error_rate_threshold=0.01,
    )


@pytest.mark.parametrize(
    "expectation",
    [
        SLOExpectation(
            method_name="evaluate_api_latency",
            metrics={"http_duration_sum": 0.5, "http_duration_count": 10.0},
            slo_name="api_latency",
            is_compliant=True,
            value=0.05,
            threshold=0.1,
        ),
        SLOExpectation(
            method_name="evaluate_api_latency",
            metrics={"http_duration_sum": 2.0, "http_duration_count": 10.0},
            slo_name="api_latency",
            is_compliant=False,
            value=0.2,
            threshold=0.1,
        ),
        SLOExpectation(
            method_name="evaluate_api_latency",
            metrics={"http_duration_sum": 0.0, "http_duration_count": 0.0},
            slo_name="api_latency",
            is_compliant=True,
            value=0.0,
            threshold=0.1,
        ),
        SLOExpectation(
            method_name="evaluate_rebuild_duration",
            metrics={"rebuild_duration_sum": 500.0, "rebuild_duration_count": 2.0},
            slo_name="rebuild_duration",
            is_compliant=True,
            value=250.0,
            threshold=300.0,
        ),
        SLOExpectation(
            method_name="evaluate_error_rate",
            metrics={"http_requests_total": 1000.0, "http_requests_error": 5.0},
            slo_name="error_rate",
            is_compliant=True,
            value=0.005,
            threshold=0.01,
        ),
        SLOExpectation(
            method_name="evaluate_error_rate",
            metrics={"http_requests_total": 100.0, "http_requests_error": 2.0},
            slo_name="error_rate",
            is_compliant=False,
            value=0.02,
            threshold=0.01,
        ),
    ],
)
def test_slo_evaluations(mock_settings: Settings, expectation: SLOExpectation) -> None:
    """Test various SLO evaluations via parametrization."""
    evaluator = SLOEvaluator(settings=mock_settings)
    eval_method = getattr(evaluator, expectation.method_name)

    # Disable side effects for pure logic tests
    result = eval_method(expectation.metrics)

    assert result.slo_name == expectation.slo_name
    assert result.is_compliant is expectation.is_compliant
    assert result.current_value == pytest.approx(expectation.value)
    assert result.threshold == pytest.approx(expectation.threshold)
    assert result.margin == pytest.approx(expectation.threshold - expectation.value)


def test_evaluate_all(mock_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test evaluating all SLOs via _collect_metrics."""
    evaluator = SLOEvaluator(settings=mock_settings)

    # Mock _collect_metrics to avoid needing a populated registry
    def mock_collect() -> dict[str, float]:
        """Mock metric collection."""
        return {
            "http_duration_sum": 0.5,
            "http_duration_count": 10.0,
            "rebuild_duration_sum": 500.0,
            "rebuild_duration_count": 2.0,
            "http_requests_total": 1000.0,
            "http_requests_error": 5.0,
        }

    monkeypatch.setattr(evaluator, "_collect_metrics", mock_collect)

    results = evaluator.evaluate_all(trigger_side_effects=False)
    assert len(results) == 3
    assert all(r.is_compliant for r in results)


def test_collect_metrics_logic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the core logic of iterating over REGISTRY and extracting metrics."""
    test_registry = CollectorRegistry()

    # Register some dummy metrics
    duration_hist = Histogram(
        "http_request_duration_seconds",
        "test",
        ["method", "route", "status_group"],
        registry=test_registry,
        buckets=(0.1, 0.5, 1.0),
    )
    duration_hist.labels(method="GET", route="/", status_group="2xx").observe(0.05)
    duration_hist.labels(method="GET", route="/", status_group="2xx").observe(0.15)

    rebuild_hist = Histogram("graph_rebuild_duration_seconds", "test", registry=test_registry, buckets=(300,))
    rebuild_hist.observe(200)

    requests_total = Counter("http_requests", "test", ["method", "route", "status_group"], registry=test_registry)
    requests_total.labels(method="GET", route="/", status_group="2xx").inc(10)
    requests_total.labels(method="GET", route="/", status_group="5xx").inc(2)

    # Patch REGISTRY to point to our test registry
    monkeypatch.setattr("api.slo_evaluator.REGISTRY", test_registry)

    evaluator = SLOEvaluator()
    metrics = evaluator._collect_metrics()

    assert metrics["http_duration_sum"] == pytest.approx(0.20)
    assert metrics["http_duration_count"] == pytest.approx(2.0)
    assert metrics["rebuild_duration_sum"] == pytest.approx(200.0)
    assert metrics["http_requests_total"] == pytest.approx(12.0)
    assert metrics["http_requests_error"] == pytest.approx(2.0)


def test_transition_safe_logging(mock_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that logs are only emitted on transition to/from breach."""
    evaluator = SLOEvaluator(settings=mock_settings)
    evaluator._last_compliance = {}  # Reset shared state for test

    mock_log = MagicMock()
    monkeypatch.setattr("api.slo_evaluator.log_event", mock_log)
    monkeypatch.setattr("api.slo_evaluator.update_slo_compliance_status", MagicMock())

    # 1. First run - Breached. Should log.
    evaluator._record_and_log("api_latency", is_compliant=False, current_value=0.5, threshold=0.1)
    assert mock_log.call_count == 1
    assert mock_log.call_args[0][2].event == "slo_breach_detected"

    # 2. Second run - Still Breached. Should NOT log again.
    mock_log.reset_mock()
    evaluator._record_and_log("api_latency", is_compliant=False, current_value=0.5, threshold=0.1)
    assert mock_log.call_count == 0

    # 3. Third run - Recovered. Should log recovery.
    mock_log.reset_mock()
    evaluator._record_and_log("api_latency", is_compliant=True, current_value=0.05, threshold=0.1)
    assert mock_log.call_count == 1
    assert mock_log.call_args[0][2].event == "slo_recovery_detected"

    # 4. Fourth run - Still Compliant. Should NOT log.
    mock_log.reset_mock()
    evaluator._record_and_log("api_latency", is_compliant=True, current_value=0.05, threshold=0.1)
    assert mock_log.call_count == 0

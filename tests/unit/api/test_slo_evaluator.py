"""Tests for the SLO Evaluator."""

from __future__ import annotations

import pytest

from api.slo_evaluator import SLOEvaluator
from src.config.settings import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Provide a basic settings fixture."""
    return Settings(
        slo_api_latency_avg_seconds=0.1,
        slo_rebuild_duration_max_seconds=300,
        slo_error_rate_threshold=0.01,
    )


@pytest.mark.parametrize(
    "method_name, metrics, expected_slo_name, expected_compliant, expected_value, expected_threshold",
    [
        (
            "evaluate_api_latency",
            {"http_duration_sum": 0.5, "http_duration_count": 10.0},
            "api_latency",
            True,
            0.05,
            0.1,
        ),
        (
            "evaluate_api_latency",
            {"http_duration_sum": 2.0, "http_duration_count": 10.0},
            "api_latency",
            False,
            0.2,
            0.1,
        ),
        (
            "evaluate_api_latency",
            {"http_duration_sum": 0.0, "http_duration_count": 0.0},
            "api_latency",
            True,
            0.0,
            0.1,
        ),
        (
            "evaluate_rebuild_duration",
            {"rebuild_duration_sum": 500.0, "rebuild_duration_count": 2.0},
            "rebuild_duration",
            True,
            250.0,
            300.0,
        ),
        (
            "evaluate_error_rate",
            {"http_requests_total": 1000.0, "http_requests_error": 5.0},
            "error_rate",
            True,
            0.005,
            0.01,
        ),
        (
            "evaluate_error_rate",
            {"http_requests_total": 100.0, "http_requests_error": 2.0},
            "error_rate",
            False,
            0.02,
            0.01,
        ),
    ],
)
def test_slo_evaluations(
    mock_settings: Settings,
    method_name: str,
    metrics: dict[str, float],
    expected_slo_name: str,
    expected_compliant: bool,
    expected_value: float,
    expected_threshold: float,
) -> None:
    """Test various SLO evaluations via parametrization."""
    evaluator = SLOEvaluator(settings=mock_settings)
    eval_method = getattr(evaluator, method_name)
    
    result = eval_method(metrics)
    
    assert result.slo_name == expected_slo_name
    assert result.is_compliant is expected_compliant
    assert result.current_value == pytest.approx(expected_value)
    assert result.threshold == pytest.approx(expected_threshold)
    assert result.margin == pytest.approx(expected_threshold - expected_value)


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
    
    results = evaluator.evaluate_all()
    assert len(results) == 3
    assert all(r.is_compliant for r in results)

"""Tests for the SLO Evaluator."""

from __future__ import annotations

import pytest

from api.slo_evaluator import SLOEvaluator
from src.config.settings import Settings

pytestmark = pytest.mark.unit



@pytest.fixture
def mock_settings() -> Settings:
    """Provide a basic settings fixture."""
    return Settings(
        slo_api_latency_avg_seconds=0.1,
        slo_rebuild_duration_max_seconds=300,
        slo_error_rate_threshold=0.01,
    )


def test_evaluate_api_latency_compliant(mock_settings: Settings) -> None:
    """Test API latency evaluation when compliant."""
    evaluator = SLOEvaluator(settings=mock_settings)
    metrics = {"http_duration_sum": 0.5, "http_duration_count": 10.0}

    result = evaluator.evaluate_api_latency(metrics)

    assert result.slo_name == "api_latency"
    assert result.is_compliant is True
    assert result.current_value == pytest.approx(0.05)  # 0.5 / 10
    assert result.threshold == pytest.approx(0.1)
    assert result.margin == pytest.approx(0.05)


def test_evaluate_api_latency_breached(mock_settings: Settings) -> None:
    """Test API latency evaluation when breached."""
    evaluator = SLOEvaluator(settings=mock_settings)
    metrics = {"http_duration_sum": 2.0, "http_duration_count": 10.0}

    result = evaluator.evaluate_api_latency(metrics)

    assert result.is_compliant is False
    assert result.current_value == pytest.approx(0.2)
    assert result.threshold == pytest.approx(0.1)
    assert result.margin == pytest.approx(-0.1)


def test_evaluate_api_latency_zero_requests(mock_settings: Settings) -> None:
    """Test API latency evaluation with no requests."""
    evaluator = SLOEvaluator(settings=mock_settings)
    metrics = {"http_duration_sum": 0.0, "http_duration_count": 0.0}

    result = evaluator.evaluate_api_latency(metrics)

    assert result.is_compliant is True
    assert result.current_value == pytest.approx(0.0)


def test_evaluate_rebuild_duration_compliant(mock_settings: Settings) -> None:
    """Test rebuild duration evaluation when compliant."""
    evaluator = SLOEvaluator(settings=mock_settings)
    metrics = {"rebuild_duration_sum": 500.0, "rebuild_duration_count": 2.0}

    result = evaluator.evaluate_rebuild_duration(metrics)

    assert result.slo_name == "rebuild_duration"
    assert result.is_compliant is True
    assert result.current_value == pytest.approx(250.0)
    assert result.threshold == pytest.approx(300.0)


def test_evaluate_error_rate_compliant(mock_settings: Settings) -> None:
    """Test error rate evaluation when compliant."""
    evaluator = SLOEvaluator(settings=mock_settings)
    metrics = {"http_requests_total": 1000.0, "http_requests_error": 5.0}

    result = evaluator.evaluate_error_rate(metrics)

    assert result.slo_name == "error_rate"
    assert result.is_compliant is True
    assert result.current_value == pytest.approx(0.005)
    assert result.threshold == pytest.approx(0.01)


def test_evaluate_error_rate_breached(mock_settings: Settings) -> None:
    """Test error rate evaluation when breached."""
    evaluator = SLOEvaluator(settings=mock_settings)
    metrics = {"http_requests_total": 100.0, "http_requests_error": 2.0}

    result = evaluator.evaluate_error_rate(metrics)

    assert result.is_compliant is False
    assert result.current_value == pytest.approx(0.02)
    assert result.threshold == pytest.approx(0.01)


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

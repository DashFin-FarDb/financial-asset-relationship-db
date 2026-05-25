"""Unit tests for api.metrics helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.metrics import (
    HEARTBEAT_LAST_SUCCESS_TIMESTAMP,
    HEARTBEAT_UPDATE_TOTAL,
    LOCK_REFRESH_DURATION,
    LOCK_REFRESH_TOTAL,
    update_rebuild_state_metric,
)
from src.data.db_models import RebuildJobStatus


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (None, 0),
        (RebuildJobStatus.RUNNING, 2),
        ("pending", 1),
        ("UNKNOWN", -1),
    ],
)
def test_update_rebuild_state_metric_maps_status_values(monkeypatch: pytest.MonkeyPatch, status, expected) -> None:
    """Status values should map to expected numeric gauge states."""
    gauge_set = MagicMock()
    monkeypatch.setattr("api.metrics.REBUILD_STATE_STATUS.set", gauge_set)

    update_rebuild_state_metric(status)

    gauge_set.assert_called_once_with(expected)


@pytest.mark.unit
def test_lock_refresh_metrics_exist() -> None:
    """Lock refresh metrics should be properly defined."""
    # Verify Counter metrics have labels method
    assert hasattr(LOCK_REFRESH_TOTAL, "labels")
    assert hasattr(HEARTBEAT_UPDATE_TOTAL, "labels")

    # Verify Histogram has time method
    assert hasattr(LOCK_REFRESH_DURATION, "time")

    # Verify Gauge has set method
    assert hasattr(HEARTBEAT_LAST_SUCCESS_TIMESTAMP, "set")


@pytest.mark.unit
def test_lock_refresh_total_counter_labels() -> None:
    """LOCK_REFRESH_TOTAL should accept success/failure status labels."""
    # Test that labels can be accessed without error
    success_counter = LOCK_REFRESH_TOTAL.labels(status="success")
    failure_counter = LOCK_REFRESH_TOTAL.labels(status="failure")

    assert success_counter is not None
    assert failure_counter is not None


@pytest.mark.unit
def test_heartbeat_update_total_counter_labels() -> None:
    """HEARTBEAT_UPDATE_TOTAL should accept success/failure status labels."""
    # Test that labels can be accessed without error
    success_counter = HEARTBEAT_UPDATE_TOTAL.labels(status="success")
    failure_counter = HEARTBEAT_UPDATE_TOTAL.labels(status="failure")

    assert success_counter is not None
    assert failure_counter is not None

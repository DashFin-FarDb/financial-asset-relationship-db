"""Unit tests for api.metrics helpers."""

from __future__ import annotations

import threading
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


def _get_counter_value(counter, **label_dict):
    """Get the current value of a Prometheus counter using public API.
    Args:
        counter: The Prometheus Counter metric
        **label_dict: Label key-value pairs to match
    Returns:
        float: The current counter value, or 0.0 if not found
    """
    for family in counter.collect():
        for sample in family.samples:
            if sample.labels == label_dict and sample.name == f"{counter._name}_total":
            if sample.labels == label_dict and sample.name.endswith('_total'):
    return 0.0


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
def test_heartbeat_keeper_lock_refresh_raises_increments_failure() -> None:
    """When dist_lock.refresh() raises, LOCK_REFRESH_TOTAL failure counter should increment."""
    from api.routers.graph_admin import _heartbeat_keeper

    mock_lock = MagicMock()
    mock_lock.refresh.side_effect = RuntimeError("DB down")
    stop_event = threading.Event()
    lock_lost_event = threading.Event()

    before = _get_counter_value(LOCK_REFRESH_TOTAL, status="failure")

    # Use a very short interval so the loop executes quickly
    # The outer exception handler catches RuntimeError and returns (no exception propagates)
    _heartbeat_keeper(
        session_factory=MagicMock(),
        dist_lock=mock_lock,
        job_id="test",
        worker_id="worker1",
        stop_event=stop_event,
        lock_lost_event=lock_lost_event,
        interval_seconds=0.001,  # Very short interval to execute immediately
    )

    after = _get_counter_value(LOCK_REFRESH_TOTAL, status="failure")
    assert after - before == 1
    # Verify lock_lost_event was set due to the exception
    assert lock_lost_event.is_set()


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

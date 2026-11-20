"""Unit tests for api.metrics helpers."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from prometheus_client import Counter

from api.metrics import (
    GRAPH_REBUILD_STATE_TRANSITION_TOTAL,
    HEARTBEAT_LAST_SUCCESS_TIMESTAMP,
    HEARTBEAT_UPDATE_TOTAL,
    LOCK_REFRESH_DURATION,
    LOCK_REFRESH_TOTAL,
    REBUILD_LOCK_ACQUISITION_TOTAL,
    record_rebuild_state_transition,
    update_rebuild_state_metric,
)
from src.data.db_models import RebuildJobStatus


def _get_counter_value(counter: Counter, **label_dict: str) -> float:
    """Get the current value of a Prometheus counter using public API.

    Args:
        counter: The Prometheus Counter metric.
        **label_dict: Label key-value pairs to match.
    Returns:
        float: The value of the matching counter sample, or 0.0 if not found.
    """
    desc = counter.describe()
    # Provide explicit default to next() to avoid StopIteration if describe() yields no descriptors.
    raw_name = next((d.name for d in desc), getattr(counter, "_name", ""))
    base_name = raw_name.removesuffix("_total")
    target_names = {raw_name, base_name, f"{base_name}_total"}
    for family in counter.collect():
        for sample in family.samples:
            if sample.name.endswith("_created") or sample.name not in target_names:
                continue
            if sample.labels == label_dict:
                return sample.value
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
@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        ("none", "pending"),
        ("pending", "running"),
        ("running", "succeeded"),
        ("running", "failed"),
        ("pending_or_running", "cancel_requested"),
        ("cancel_requested", "cancelled"),
    ],
)
def test_rebuild_state_transition_metric_records_bounded_transition(from_state: str, to_state: str) -> None:
    """Each supported rebuild lifecycle transition is recorded with only state labels."""
    before = _get_counter_value(GRAPH_REBUILD_STATE_TRANSITION_TOTAL, from_state=from_state, to_state=to_state)

    record_rebuild_state_transition(from_state, to_state)

    after = _get_counter_value(GRAPH_REBUILD_STATE_TRANSITION_TOTAL, from_state=from_state, to_state=to_state)
    assert after - before == 1


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
        execution_id="test_exec_id",
        worker_id="worker1",
        stop_event=stop_event,
        lock_lost_event=lock_lost_event,
        cancel_event=threading.Event(),
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


@pytest.mark.unit
@pytest.mark.parametrize(
    ("outcome", "acquire_error", "lock_state", "error_type"),
    [
        ("acquired", None, "valid", None),
        ("timeout", "timeout", "valid", RuntimeError),
        ("error", "error", "valid", RuntimeError),
        ("lost", None, "lost", RuntimeError),
        ("invalid", None, "unknown", RuntimeError),
    ],
)
def test_rebuild_lock_acquisition_records_each_outcome(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    acquire_error: str | None,
    lock_state: str,
    error_type,
) -> None:
    """Lock acquire success and failure outcomes each increment their bounded label."""
    from api.routers import graph_admin
    from src.data.distributed_lock import LockAcquisitionTimeout, LockState

    lock = MagicMock()
    if acquire_error == "timeout":
        lock.acquire.side_effect = LockAcquisitionTimeout("timeout")
    elif acquire_error == "error":
        lock.acquire.side_effect = RuntimeError("database error")
    lock.check_state.return_value = LockState(lock_state)
    monkeypatch.setattr(graph_admin, "_validate_coordination_database_primary", lambda _factory: None)
    monkeypatch.setattr(graph_admin, "DistributedLock", lambda **_kwargs: lock)
    outcomes = ("acquired", "timeout", "error", "lost", "invalid")
    before = {status: _get_counter_value(REBUILD_LOCK_ACQUISITION_TOTAL, status=status) for status in outcomes}

    if error_type is None:
        assert graph_admin._acquire_rebuild_lock(MagicMock(), 30) is lock
    else:
        with pytest.raises(error_type):
            graph_admin._acquire_rebuild_lock(MagicMock(), 30)

    after = {status: _get_counter_value(REBUILD_LOCK_ACQUISITION_TOTAL, status=status) for status in outcomes}
    assert after[outcome] - before[outcome] == 1
    assert all(after[status] - before[status] == 0 for status in outcomes if status != outcome)
    emitted_statuses = {
        sample.labels.get("status")
        for metric_family in REBUILD_LOCK_ACQUISITION_TOTAL.collect()
        for sample in metric_family.samples
        if sample.name == "rebuild_lock_acquisition_total"
    }
    assert emitted_statuses <= set(outcomes)

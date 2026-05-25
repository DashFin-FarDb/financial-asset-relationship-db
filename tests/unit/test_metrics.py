"""Unit tests for api.metrics helpers."""

from __future__ import annotations

import threading
import weakref
from unittest.mock import MagicMock

import pytest
from prometheus_client import Counter

from api.metrics import (
    HEARTBEAT_LAST_SUCCESS_TIMESTAMP,
    HEARTBEAT_UPDATE_TOTAL,
    LOCK_REFRESH_DURATION,
    LOCK_REFRESH_TOTAL,
    update_rebuild_state_metric,
)
from src.data.db_models import RebuildJobStatus

_WEAK_COUNTER_CACHE = weakref.WeakKeyDictionary()
_FALLBACK_COUNTER_CACHE: dict[int, set[str]] = {}


def _fallback_cleanup(ref: weakref.ReferenceType) -> None:
    """Evict entries from the integer-keyed fallback cache upon object GC."""
    # The dictionary key is the integer ID of the original object, 
    # which we can extract by looking at the memory address of the dead ref.
    _FALLBACK_COUNTER_CACHE.pop(id(ref), None)


def _get_or_compute_expected_names(counter: Counter) -> set[str]:
    try:
        expected_names = _WEAK_COUNTER_CACHE.get(counter)
    except TypeError:
        expected_names = _FALLBACK_COUNTER_CACHE.get(id(counter))

    if expected_names is not None:
        return expected_names

    desc = counter.describe()
    raw_name = desc[0].name if desc else getattr(counter, "_name", "")
    base_name = raw_name.removesuffix("_total")
    expected_names = {raw_name, base_name, f"{base_name}_total"}

    try:
        _WEAK_COUNTER_CACHE[counter] = expected_names
    except TypeError:
        # Create a weak reference with a callback to safely clean up the int key
        # id(counter) matches id(ref) when the callback executes
        try:
            weakref.ref(counter, _fallback_cleanup)
            _FALLBACK_COUNTER_CACHE[id(counter)] = expected_names
        except TypeError:
            # Absolute fallback for entirely non-weakrefable structures (e.g., builtins)
            _FALLBACK_COUNTER_CACHE[id(counter)] = expected_names

    return expected_names


def _get_counter_value(counter: Counter, **label_dict: str) -> float:
    expected_names = _get_or_compute_expected_names(counter)

    for family in counter.collect():
        for sample in family.samples:
            if sample.name.endswith("_created") or sample.name not in expected_names:
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

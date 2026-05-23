"""Unit tests for api.metrics helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.metrics import update_rebuild_state_metric
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

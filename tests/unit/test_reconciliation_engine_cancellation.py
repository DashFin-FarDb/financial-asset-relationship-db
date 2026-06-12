"""Unit tests for ReconciliationEngine rebuild cancellation."""

import threading
from typing import Any

import pytest

from src.logic.reconciliation_engine import RebuildCancelledError, ReconciliationEngine, Severity
from src.models.financial_models import Asset, AssetClass


class _NoOpEvaluator:
    def evaluate_drift(self) -> tuple[str, Severity, dict[str, Any]]:
        return "none", Severity.NONE, {}


def test_run_rebuild_aborts_when_cancel_event_is_set():
    """run_rebuild must raise RebuildCancelledError when cancel_event is set."""
    engine = ReconciliationEngine(_NoOpEvaluator())
    cancel_event = threading.Event()

    # Create some assets to process
    assets = [
        Asset(
            id=f"asset-{i}",
            symbol=f"SYM{i}",
            name=f"Asset {i}",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        for i in range(10)
    ]

    # Pre-set the cancel event
    cancel_event.set()

    with pytest.raises(RebuildCancelledError, match="Rebuild cancelled via API request"):
        engine.run_rebuild(assets=assets, regulatory_events=[], cancel_event=cancel_event)


def test_run_rebuild_aborts_mid_loop():
    """run_rebuild must raise RebuildCancelledError if cancelled during processing."""
    engine = ReconciliationEngine(_NoOpEvaluator())
    cancel_event = threading.Event()

    # Create assets
    assets = [
        Asset(
            id=f"asset-{i}",
            symbol=f"SYM{i}",
            name=f"Asset {i}",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
        for i in range(100)
    ]

    # Helper to set cancel event after some assets processed via checkpoint callback
    def on_checkpoint(data: dict[str, Any]) -> None:
        if data["processed_count"] >= 50:
            cancel_event.set()

    with pytest.raises(RebuildCancelledError, match="Rebuild cancelled via API request"):
        engine.run_rebuild(
            assets=assets,
            regulatory_events=[],
            on_checkpoint=on_checkpoint,
            cancel_event=cancel_event,
        )

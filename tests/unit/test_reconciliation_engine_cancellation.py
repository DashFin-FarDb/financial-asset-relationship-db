"""Unit tests for ReconciliationEngine rebuild cancellation."""

import threading
from typing import Any
from unittest.mock import patch

import pytest

from src.logic.rebuild_executor import RebuildExecutor
from src.logic.reconciliation_engine import RebuildCancelledError, ReconciliationEngine, Severity
from src.models.financial_models import Asset, AssetClass


class _NoOpEvaluator:
    """Minimal stub satisfying ReconciliationEngine's evaluator protocol."""

    def evaluate_drift(self) -> tuple[str, Severity, dict[str, Any]]:
        """Return a no-op drift result."""
        return "none", Severity.NONE, {}


def test_run_rebuild_aborts_when_cancel_event_is_set():
    """run_rebuild must raise RebuildCancelledError when cancel_event is set."""
    executor = RebuildExecutor()
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
        executor.run_rebuild(assets=assets, regulatory_events=[], cancel_event=cancel_event)


def test_run_rebuild_aborts_mid_loop():
    """run_rebuild must raise RebuildCancelledError if cancelled during processing."""
    executor = RebuildExecutor()
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
        """Trigger cancellation after 50 assets."""
        if data["processed_count"] >= 50:
            cancel_event.set()

    with pytest.raises(RebuildCancelledError, match="Rebuild cancelled via API request"):
        executor.run_rebuild(
            assets=assets,
            regulatory_events=[],
            on_checkpoint=on_checkpoint,
            cancel_event=cancel_event,
        )


def test_run_rebuild_aborts_at_final_checkpoint():
    """run_rebuild must raise RebuildCancelledError if cancelled during the final checkpoint."""
    executor = RebuildExecutor()
    cancel_event = threading.Event()

    # Create assets (fewer than 50, so it only hits the final checkpoint)
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

    # Helper to set cancel event exactly when final checkpoint is called
    def on_checkpoint(data: dict[str, Any]) -> None:
        """Trigger cancellation at final checkpoint."""
        if data["processed_count"] == 10:
            cancel_event.set()

    with pytest.raises(RebuildCancelledError, match="Rebuild cancelled via API request"):
        executor.run_rebuild(
            assets=assets,
            regulatory_events=[],
            on_checkpoint=on_checkpoint,
            cancel_event=cancel_event,
        )


def test_run_rebuild_aborts_during_regulatory_events():
    """run_rebuild must raise RebuildCancelledError if cancelled during regulatory event processing."""
    from src.models.financial_models import RegulatoryEvent

    executor = RebuildExecutor()
    cancel_event = threading.Event()

    assets = [
        Asset(
            id="asset-1",
            symbol="SYM1",
            name="Asset 1",
            asset_class=AssetClass.EQUITY,
            sector="Technology",
            price=100.0,
        )
    ]

    events = [
        RegulatoryEvent(
            id=f"event-{i}",
            asset_id="asset-1",
            event_type="test",
            description="test event",
            date="2024-01-01",
            impact_score=0.5,
        )
        for i in range(10)
    ]

    # Subclass AssetRelationshipGraph to trigger cancellation during add_regulatory_event
    from src.logic.asset_graph import AssetRelationshipGraph

    class CancellingGraph(AssetRelationshipGraph):
        """Mock graph that triggers cancellation during event addition."""

        def add_regulatory_event(self, event):
            """Set cancel event when a specific event ID is encountered."""
            if event.id == "event-5":
                cancel_event.set()
            super().add_regulatory_event(event)

    with (
        patch("src.logic.asset_graph.AssetRelationshipGraph", side_effect=CancellingGraph),
        pytest.raises(RebuildCancelledError, match="Rebuild cancelled via API request"),
    ):
        executor.run_rebuild(
            assets=assets,
            regulatory_events=events,
            cancel_event=cancel_event,
        )

"""Rebuild execution orchestration for the reconciliation engine.

This module is responsible for the actual application of Desired State onto
the Observed State graph, managing checkpoints, cancellations, and progress.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from src.logic.reconciliation_engine import RebuildCancelledError
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

if TYPE_CHECKING:
    from src.logic.asset_graph import AssetRelationshipGraph
    from src.models.financial_models import Asset, RegulatoryEvent

logger = logging.getLogger(__name__)

_REBUILD_CANCELLED_MSG = "Rebuild cancelled via API request"


class RebuildExecutor:
    """Handles the execution phase of graph rebuilds."""

    def run_rebuild(
        self,
        assets: Iterable[Asset],
        regulatory_events: Iterable[RegulatoryEvent],
        on_checkpoint: Callable[[dict[str, Any]], None] | None = None,
        initial_checkpoint: dict[str, Any] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> AssetRelationshipGraph:
        """
        Execute a checkpointed graph rebuild from the provided assets and events.

        This method implements the core reconstruction loop, applying assets to a new graph
        at bounded intervals and invoking the provided checkpoint callback.

        Parameters:
            assets: Iterable of assets to add to the graph.
            regulatory_events: Iterable of regulatory events to add to the graph.
            on_checkpoint: Optional callback invoked every 50 assets.
            initial_checkpoint: Optional state used to resume a partial rebuild.
            cancel_event: Optional event to signal rebuild cancellation.

        Returns:
            AssetRelationshipGraph: The fully reconstructed graph.

        Raises:
            RebuildCancelledError: If the cancel_event is set during execution.
        """
        from src.config.settings import get_settings
        from src.logic.asset_graph import AssetRelationshipGraph

        settings = get_settings()
        graph = AssetRelationshipGraph(
            same_sector_strength=settings.same_sector_strength,
            corporate_bond_strength=settings.corporate_bond_strength,
        )
        skipped_ids = self._get_skipped_ids(initial_checkpoint)

        self._process_assets(assets, graph, skipped_ids, on_checkpoint, cancel_event)

        self._check_cancellation(cancel_event, "regulatory event preparation")
        self._process_regulatory_events(regulatory_events, graph, cancel_event)
        self._check_cancellation(cancel_event, "relationship building preparation")

        graph.build_relationships()

        self._log_rebuild_completion(graph)
        return graph

    def _check_cancellation(self, cancel_event: threading.Event | None, stage: str = "processing") -> None:
        """Raise RebuildCancelledError if the cancel_event is set."""
        if cancel_event and cancel_event.is_set():
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="reconciliation_rebuild_cancelled",
                    message=f"Rebuild cancelled via signal during {stage}",
                ),
            )
            raise RebuildCancelledError(_REBUILD_CANCELLED_MSG)

    def _get_skipped_ids(self, initial_checkpoint: dict[str, Any] | None) -> set[str]:
        """Identify assets to skip based on the initial checkpoint."""
        if not initial_checkpoint or "processed_ids" not in initial_checkpoint:
            return set()

        skipped_ids = set(initial_checkpoint["processed_ids"])
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="reconciliation_rebuild_resume_started",
                message=f"Resuming rebuild: skipping {len(skipped_ids)} already processed assets",
                metadata={"skipped_count": len(skipped_ids)},
            ),
        )
        return skipped_ids

    def _process_assets(
        self,
        assets: Iterable[Asset],
        graph: AssetRelationshipGraph,
        skipped_ids: set[str],
        on_checkpoint: Callable[[dict[str, Any]], None] | None,
        cancel_event: threading.Event | None,
    ) -> None:
        """Add assets to the graph and invoke checkpoints."""
        processed_count = 0
        for asset in assets:
            self._check_cancellation(cancel_event, "asset processing")

            graph.add_asset(asset)
            if asset.id in skipped_ids:
                continue

            processed_count += 1

            if on_checkpoint and processed_count % 50 == 0:
                on_checkpoint(
                    {
                        "processed_ids": list(graph.assets.keys()),
                        "last_asset_id": asset.id,
                        "processed_count": len(graph.assets),
                    }
                )

        self._check_cancellation(cancel_event, "asset processing completion")

        if on_checkpoint and processed_count > 0:
            on_checkpoint(
                {
                    "processed_ids": list(graph.assets.keys()),
                    "processed_count": len(graph.assets),
                }
            )
        self._check_cancellation(cancel_event, "asset loop completion")

    def _process_regulatory_events(
        self,
        regulatory_events: Iterable[RegulatoryEvent],
        graph: AssetRelationshipGraph,
        cancel_event: threading.Event | None,
    ) -> None:
        """Add regulatory events to the graph."""
        for event in regulatory_events:
            self._check_cancellation(cancel_event, "regulatory event processing")
            graph.add_regulatory_event(event)

    def _log_rebuild_completion(self, graph: AssetRelationshipGraph) -> None:
        """Log the successful completion of the rebuild."""
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="reconciliation_rebuild_completed",
                message=(
                    f"Rebuild completed: {len(graph.assets)} assets, {len(graph.regulatory_events)} events processed"
                ),
                metadata={
                    "asset_count": len(graph.assets),
                    "event_count": len(graph.regulatory_events),
                },
            ),
        )

"""Rebuild execution orchestration for the reconciliation engine.

This module is responsible for the actual application of Desired State onto
the Observed State graph, managing checkpoints, cancellations, and progress.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
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
        **kwargs: Any,
    ) -> AssetRelationshipGraph:
        """
        Execute a checkpointed graph rebuild from the provided assets and events.

        This method implements the core reconstruction loop, applying assets to a new graph
        at bounded intervals and invoking the provided checkpoint callback.

        Parameters:
            assets: Iterable of assets to add to the graph.
            regulatory_events: Iterable of regulatory events to add to the graph.
            on_checkpoint: Optional callback invoked every 50 assets.
            initial_checkpoint: Optional dict state used to resume a partial rebuild. Expected to contain 'processed_ids' (list of str).
            cancel_event: Optional threading.Event to signal rebuild cancellation.
            execution_id: Optional string identifying the current execution process.
            expected_execution_id: Optional string (or callable returning a string) identifying the expected owner. Rebuild raises if execution_id != expected_execution_id.

        Returns:
            AssetRelationshipGraph: The fully reconstructed graph.

        Raises:
            RebuildCancelledError: If the cancel_event is set during execution.
        """
        from src.config.settings import get_settings
        from src.logic.asset_graph import AssetRelationshipGraph

        settings = get_settings()

        allowed_kwargs = {
            "on_checkpoint",
            "initial_checkpoint",
            "cancel_event",
            "execution_id",
            "expected_execution_id",
        }
        unexpected = set(kwargs.keys()) - allowed_kwargs
        if unexpected:
            raise TypeError(f"run_rebuild got unexpected keyword arguments: {', '.join(sorted(unexpected))}")

        graph = AssetRelationshipGraph(
            same_sector_strength=settings.same_sector_strength,
            corporate_bond_strength=settings.corporate_bond_strength,
        )

        on_checkpoint = kwargs.get("on_checkpoint")
        initial_checkpoint = kwargs.get("initial_checkpoint")
        cancel_event = kwargs.get("cancel_event")

        skipped_ids = self._get_skipped_ids(initial_checkpoint)

        self._validate_execution_ownership(**kwargs)
        self._process_assets(
            assets,
            graph,
            skipped_ids,
            on_checkpoint=on_checkpoint,
            cancel_event=cancel_event,
        )

        self._check_cancellation(cancel_event, "regulatory event preparation")
        self._validate_execution_ownership(**kwargs)
        self._process_regulatory_events(regulatory_events, graph, cancel_event)

        self._check_cancellation(cancel_event, "relationship building preparation")
        self._validate_execution_ownership(**kwargs)
        graph.build_relationships()

        self._log_rebuild_completion(graph)
        return graph

    def _validate_execution_ownership(self, **kwargs: Any) -> None:
        """Validate that the current execution_id matches the expected execution ownership."""
        execution_id = kwargs.get("execution_id")
        expected_owner = kwargs.get("expected_execution_id")

        if callable(expected_owner):
            expected_owner = expected_owner()

        if execution_id and expected_owner and execution_id != expected_owner:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="stale_execution_rejected",
                    message=f"Stale executor rejected: {execution_id} != {expected_owner}",
                ),
            )
            raise RebuildCancelledError(f"Stale execution context: {execution_id} != {expected_owner}")

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
        **kwargs: Any,
    ) -> None:
        """
        Add assets to the graph and invoke checkpoints.

        Note: Assets in `skipped_ids` are still added to the graph to ensure the graph
        state is fully reconstructed, but they are excluded from processing count metrics
        and checkpoint evaluations.
        """
        on_checkpoint = kwargs.get("on_checkpoint")
        cancel_event = kwargs.get("cancel_event")
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

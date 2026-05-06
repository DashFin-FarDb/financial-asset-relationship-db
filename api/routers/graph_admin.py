"""Operator routes for graph administration."""

from __future__ import annotations

import asyncio
import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status  # pylint: disable=import-error

from ..api_models import GraphRebuildResponse
from ..auth import User, get_current_active_user
from ..graph_lifecycle import synchronize_runtime_graph
from ..graph_lifecycle_providers import (
    GraphLifecycleSettings,
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    GraphPersistenceSaveError,
    GraphRebuildSourceError,
    build_rebuild_graph,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    save_graph_to_persistence,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class _RebuildRuntime:
    """Process-local rebuild concurrency and executor state."""

    def __init__(self) -> None:
        """Create empty rebuild runtime state."""
        self.lock: asyncio.Lock | None = None
        self.lock_loop: asyncio.AbstractEventLoop | None = None
        self.executor: ThreadPoolExecutor | None = None

    def get_lock(self) -> asyncio.Lock:
        """Return a rebuild lock bound to the current event loop."""
        loop = asyncio.get_running_loop()
        if self.lock is None or self.lock_loop is not loop:
            self.lock = asyncio.Lock()
            self.lock_loop = loop
        return self.lock

    def get_executor(self) -> ThreadPoolExecutor:
        """Return the process-local rebuild executor."""
        if self.executor is None:
            self.executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="GraphRebuild",
            )
        return self.executor

    def shutdown_executor(self) -> None:
        """Shut down the process-local rebuild executor."""
        if self.executor is not None:
            self.executor.shutdown(wait=True)
            self.executor = None


_REBUILD_RUNTIME = _RebuildRuntime()


@router.post("/api/graph/rebuild")
async def rebuild_graph(
    _current_user: Annotated[User, Depends(get_current_active_user)],
) -> GraphRebuildResponse:
    """Rebuild, persist, and synchronize graph state."""
    settings = get_graph_lifecycle_settings()
    loop = asyncio.get_running_loop()
    rebuild_lock = _REBUILD_RUNTIME.get_lock()

    # No await occurs between locked() and acquire; this gives same-loop
    # fail-fast behavior without queueing behind the active rebuild.
    if rebuild_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A graph rebuild is already in progress. Please try again later.",
        )

    async with rebuild_lock:
        try:
            ctx = contextvars.copy_context()
            return await loop.run_in_executor(
                _REBUILD_RUNTIME.get_executor(),
                ctx.run,
                _perform_rebuild_and_persist_sync,
                settings,
            )
        except Exception as exc:
            raise _map_rebuild_error(exc) from None


def _map_rebuild_error(exc: Exception) -> HTTPException:
    """Map rebuild domain errors to sanitized HTTP errors."""
    if isinstance(
        exc,
        (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (GraphRebuildSourceError, GraphPersistenceSaveError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    logger.error(
        "Unexpected graph rebuild failure: %s",
        exc.__class__.__name__,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Graph rebuild failed.",
    )


def shutdown_rebuild_executor() -> None:
    """Shut down the process-local graph rebuild executor."""
    _REBUILD_RUNTIME.shutdown_executor()


def _perform_rebuild_and_persist_sync(
    settings: GraphLifecycleSettings,
) -> GraphRebuildResponse:
    """Rebuild the graph, persist it, then publish it to runtime state."""
    resolved_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)

    graph, source = build_rebuild_graph(settings)

    save_graph_to_persistence(resolved_url, graph)

    synchronize_runtime_graph(graph)

    regulatory_events = getattr(graph, "regulatory_events", []) or []
    return GraphRebuildResponse(
        status="persisted",
        source=source,
        asset_count=len(graph.assets),
        relationship_count=sum(len(items) for items in graph.relationships.values()),
        regulatory_event_count=len(regulatory_events),
    )

"""Operator routes for graph administration."""

from __future__ import annotations

import asyncio
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

_rebuild_lock: asyncio.Lock | None = None
_rebuild_lock_loop: asyncio.AbstractEventLoop | None = None
_rebuild_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="GraphRebuild",
)


@router.post("/api/graph/rebuild", response_model=GraphRebuildResponse)
async def rebuild_graph(
    _current_user: Annotated[User, Depends(get_current_active_user)],
) -> GraphRebuildResponse:
    """
    Rebuilds the asset graph, persists it to durable storage, and synchronizes the in-memory runtime graph, serializing concurrent rebuild requests with a per-event-loop lock.
    
    Returns:
        GraphRebuildResponse: Response with rebuild outcome and counts (`status`, `source`, `asset_count`, `relationship_count`, `regulatory_event_count`).
    
    Raises:
        HTTPException: 409 CONFLICT if persistence is not configured or not durable.
        HTTPException: 500 INTERNAL SERVER ERROR if the rebuild source cannot be determined or saving the graph fails.
    """
    settings = get_graph_lifecycle_settings()
    loop = asyncio.get_running_loop()

    async with _get_rebuild_lock():
        try:
            return await loop.run_in_executor(
                _rebuild_executor,
                _perform_rebuild_and_persist_sync,
                settings,
            )
        except (
            GraphPersistenceNotConfiguredError,
            GraphPersistenceNonDurableError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from None
        except GraphRebuildSourceError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from None
        except GraphPersistenceSaveError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from None


def _get_rebuild_lock() -> asyncio.Lock:
    """
    Get an asyncio.Lock bound to the current event loop, creating a new lock if none exists or the existing lock is bound to a different loop.
    
    Returns:
        asyncio.Lock: Lock instance associated with the current event loop.
    """
    global _rebuild_lock, _rebuild_lock_loop  # noqa: PLW0603
    loop = asyncio.get_running_loop()
    if _rebuild_lock is None or _rebuild_lock_loop is not loop:
        _rebuild_lock = asyncio.Lock()
        _rebuild_lock_loop = loop
    return _rebuild_lock


def _perform_rebuild_and_persist_sync(
    settings: GraphLifecycleSettings,
) -> GraphRebuildResponse:
    """
    Perform a full rebuild of the asset graph, persist it to durable storage, and synchronize the runtime graph state.
    
    Parameters:
        settings (GraphLifecycleSettings): Configuration for graph lifecycle operations; must include the durable persistence URL or enough information to resolve it.
    
    Returns:
        GraphRebuildResponse: Result summary with:
            - status: The final persistence status (e.g., "persisted").
            - source: Identifier of the graph source produced during the rebuild.
            - asset_count: Number of assets in the rebuilt graph.
            - relationship_count: Total number of relationship entries across all relationship lists.
            - regulatory_event_count: Number of regulatory events collected from the graph (0 if none).
    """
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

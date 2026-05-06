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
    """Rebuild, persist, and synchronize graph state."""
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
    """Return an asyncio lock bound to the current event loop."""
    global _rebuild_lock, _rebuild_lock_loop  # noqa: PLW0603
    loop = asyncio.get_running_loop()
    if _rebuild_lock is None or _rebuild_lock_loop is not loop:
        _rebuild_lock = asyncio.Lock()
        _rebuild_lock_loop = loop
    return _rebuild_lock


def _perform_rebuild_and_persist_sync(
    settings: GraphLifecycleSettings,
) -> GraphRebuildResponse:
    """Run the blocking rebuild, persistence, and runtime sync workflow."""
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

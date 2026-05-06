"""Operator routes for graph administration."""

from __future__ import annotations

import threading
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..api_models import GraphRebuildResponse
from ..auth import User, get_current_active_user
from ..graph_lifecycle import synchronize_runtime_graph
from ..graph_lifecycle_providers import (
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
_rebuild_lock = threading.Lock()


@router.post("/api/graph/rebuild", response_model=GraphRebuildResponse)
def rebuild_graph(
    _current_user: Annotated[User, Depends(get_current_active_user)],
) -> GraphRebuildResponse:
    """Build, persist, and publish a fresh graph snapshot."""
    settings = get_graph_lifecycle_settings()

    with _rebuild_lock:
        try:
            resolved_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

        try:
            graph, source = build_rebuild_graph(settings)
        except GraphRebuildSourceError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from None

        try:
            save_graph_to_persistence(resolved_url, graph)
        except GraphPersistenceSaveError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from None

        synchronize_runtime_graph(graph)

        regulatory_events = getattr(graph, "regulatory_events", []) or []
        return GraphRebuildResponse(
            status="persisted",
            source=source,
            asset_count=len(graph.assets),
            relationship_count=sum(len(items) for items in graph.relationships.values()),
            regulatory_event_count=len(regulatory_events),
        )

"""Operator routes for graph administration."""

from __future__ import annotations

import asyncio
import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import perf_counter
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
    GraphRebuildSource,
    GraphRebuildSourceError,
    build_rebuild_graph,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    save_graph_to_persistence,
)

router = APIRouter()
logger = logging.getLogger(__name__)
_REBUILD_IN_PROGRESS_MESSAGE = "A graph rebuild is already in progress. Please try again later."
_REBUILD_AUDIT_REQUESTED = "graph_rebuild_requested"
_REBUILD_AUDIT_REJECTED = "graph_rebuild_rejected"
_REBUILD_AUDIT_SUCCEEDED = "graph_rebuild_succeeded"
_REBUILD_AUDIT_FAILED = "graph_rebuild_failed"
_REBUILD_PATH = "/api/graph/rebuild"
_MAX_AUDIT_USER_REF_LENGTH = 64


class _RebuildRuntime:
    """Process-local rebuild concurrency and executor state."""

    def __init__(self) -> None:
        """Create empty rebuild runtime state."""
        self.lock: asyncio.Lock | None = None
        self.lock_loop: asyncio.AbstractEventLoop | None = None
        self.executor: ThreadPoolExecutor | None = None
        self.busy = False

    def is_busy(self) -> bool:
        """Return whether a rebuild is running or queued."""
        return self.busy

    def mark_busy(self) -> None:
        """Mark rebuild execution as active."""
        self.busy = True

    def mark_idle(self) -> None:
        """Mark rebuild execution as idle."""
        self.busy = False

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


class _RebuildExecutionError(Exception):
    """Wrap rebuild execution errors with bounded audit source context."""

    def __init__(self, source: GraphRebuildSource, cause: Exception) -> None:
        """Store source and underlying failure without exposing raw details."""
        super().__init__(cause.__class__.__name__)
        self.source = source
        self.cause = cause


@router.post("/api/graph/rebuild")
async def rebuild_graph(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> GraphRebuildResponse:
    """Rebuild, persist, and synchronize graph state."""
    settings = get_graph_lifecycle_settings()
    loop = asyncio.get_running_loop()
    started_at = perf_counter()
    user_ref = _resolve_user_ref(current_user)

    _log_rebuild_requested(user_ref=user_ref)

    try:
        rebuild_lock = _claim_rebuild_or_raise()
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            _log_rebuild_rejected(user_ref=user_ref)
        raise

    async with rebuild_lock:
        if _REBUILD_RUNTIME.is_busy():
            _log_rebuild_rejected(user_ref=user_ref)
            raise _rebuild_in_progress_error()

        _REBUILD_RUNTIME.mark_busy()
        try:
            return await _run_rebuild_in_executor(
                loop,
                settings,
                user_ref=user_ref,
                started_at=started_at,
            )
        except Exception as exc:
            raise _map_rebuild_error(exc) from None


def _rebuild_in_progress_error() -> HTTPException:
    """Return the graph rebuild in-progress response."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=_REBUILD_IN_PROGRESS_MESSAGE,
    )


def _claim_rebuild_or_raise() -> asyncio.Lock:
    """Claim rebuild execution or raise a fail-fast HTTP error."""
    rebuild_lock = _REBUILD_RUNTIME.get_lock()
    if _REBUILD_RUNTIME.is_busy():
        raise _rebuild_in_progress_error()
    return rebuild_lock


async def _run_rebuild_in_executor(
    loop: asyncio.AbstractEventLoop,
    settings: GraphLifecycleSettings,
    *,
    user_ref: str,
    started_at: float,
) -> GraphRebuildResponse:
    """Run rebuild work in the dedicated executor."""
    ctx = contextvars.copy_context()
    try:
        future = loop.run_in_executor(
            _REBUILD_RUNTIME.get_executor(),
            ctx.run,
            _perform_rebuild_and_persist_sync,
            settings,
        )
    except Exception as exc:
        _REBUILD_RUNTIME.mark_idle()
        _log_rebuild_failed(
            user_ref=user_ref,
            exc=exc,
            status_code=_rebuild_status_code(exc),
            duration_ms=_duration_ms(started_at),
        )
        raise

    def on_done(done_future: asyncio.Future[GraphRebuildResponse]) -> None:
        """Finalize rebuild state and emit outcome audit logs."""
        _REBUILD_RUNTIME.mark_idle()
        try:
            response = done_future.result()
        except Exception as exc:
            _log_rebuild_failed(
                user_ref=user_ref,
                exc=exc,
                status_code=_rebuild_status_code(exc),
                duration_ms=_duration_ms(started_at),
            )
            return

        _log_rebuild_succeeded(
            user_ref=user_ref,
            response=response,
            duration_ms=_duration_ms(started_at),
        )

    future.add_done_callback(on_done)
    return await asyncio.shield(future)


def _map_rebuild_error(exc: Exception) -> HTTPException:
    """Map rebuild domain errors to sanitized HTTP errors."""
    root_exc = _unwrap_rebuild_error(exc)
    
    if isinstance(
        root_exc,
        (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(root_exc))

    if isinstance(root_exc, (GraphRebuildSourceError, GraphPersistenceSaveError)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(root_exc),
        )

    logger.error(
        "Unexpected graph rebuild failure: %s",
        root_exc.__class__.__name__,
    )
    
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Graph rebuild failed.",
    )


def _rebuild_status_code(exc: Exception) -> int:
    """Return sanitized rebuild status code for audit logging without side effects."""
    root_exc = _unwrap_rebuild_error(exc)
    if isinstance(
        root_exc,
        (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError),
    ):
        return status.HTTP_409_CONFLICT
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _resolve_user_ref(user: User) -> str:
    """Return the bounded user reference used in rebuild audit logs."""
    username = user.username or ""
    normalized = "".join(char if char.isprintable() and char not in "\r\n\t" else "_" for char in username.strip())
    if not normalized:
        return "unknown"
    return normalized[:_MAX_AUDIT_USER_REF_LENGTH]


def _audit_timestamp() -> str:
    """Return a UTC timestamp string for audit log records."""
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017 - Python 3.10 compatibility


def _duration_ms(started_at: float) -> int:
    """Return non-negative elapsed wall time in milliseconds."""
    return max(0, int((perf_counter() - started_at) * 1000))


def _log_rebuild_requested(*, user_ref: str) -> None:
    """Emit a bounded audit event for rebuild request start."""
    logger.info(
        "graph_rebuild_audit",
        extra={
            "event": _REBUILD_AUDIT_REQUESTED,
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "timestamp": _audit_timestamp(),
        },
    )


def _log_rebuild_rejected(*, user_ref: str) -> None:
    """Emit a bounded audit event for rebuild concurrency rejection."""
    logger.warning(
        "graph_rebuild_audit",
        extra={
            "event": _REBUILD_AUDIT_REJECTED,
            "reason": "rebuild_in_progress",
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "status_code": status.HTTP_429_TOO_MANY_REQUESTS,
            "timestamp": _audit_timestamp(),
        },
    )


def _log_rebuild_succeeded(*, user_ref: str, response: GraphRebuildResponse, duration_ms: int) -> None:
    """Emit a bounded audit event for successful rebuild completion."""
    logger.info(
        "graph_rebuild_audit",
        extra={
            "event": _REBUILD_AUDIT_SUCCEEDED,
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "status_code": status.HTTP_200_OK,
            "source": response.source,
            "duration_ms": duration_ms,
            "asset_count": response.asset_count,
            "relationship_count": response.relationship_count,
            "regulatory_event_count": response.regulatory_event_count,
            "timestamp": _audit_timestamp(),
        },
    )


def _rebuild_failure_category(exc: Exception) -> str:
    """Return a bounded failure category for rebuild audit logs."""
    root_exc = _unwrap_rebuild_error(exc)
    if isinstance(root_exc, GraphPersistenceNotConfiguredError):
        return "persistence_not_configured"
    if isinstance(root_exc, GraphPersistenceNonDurableError):
        return "persistence_non_durable"
    if isinstance(root_exc, GraphRebuildSourceError):
        return "rebuild_source_error"
    if isinstance(root_exc, GraphPersistenceSaveError):
        return "persistence_save_error"
    return "unexpected_error"


def _rebuild_source_from_exception(exc: Exception) -> GraphRebuildSource | None:
    """Return bounded rebuild source from wrapped execution errors when available."""
    if isinstance(exc, _RebuildExecutionError):
        return exc.source
    return None


def _log_rebuild_failed(*, user_ref: str, exc: Exception, status_code: int, duration_ms: int) -> None:
    """Emit a bounded audit event for rebuild failure."""
    logger.error(
        "graph_rebuild_audit",
        extra={
            "event": _REBUILD_AUDIT_FAILED,
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "failure_category": _rebuild_failure_category(exc),
            "status_code": status_code,
            "duration_ms": duration_ms,
            "source": _rebuild_source_from_exception(exc),
            "timestamp": _audit_timestamp(),
        },
    )


def _unwrap_rebuild_error(exc: Exception) -> Exception:
    """Return the underlying rebuild error for mapping and audit categorization."""
    if isinstance(exc, _RebuildExecutionError):
        return exc.cause
    return exc


def shutdown_rebuild_executor() -> None:
    """Shut down the process-local graph rebuild executor."""
    _REBUILD_RUNTIME.shutdown_executor()


def _perform_rebuild_and_persist_sync(
    settings: GraphLifecycleSettings,
) -> GraphRebuildResponse:
    """Rebuild the graph, persist it, then publish it to runtime state."""
    resolved_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)

    graph, source = build_rebuild_graph(settings)

    try:
        save_graph_to_persistence(resolved_url, graph)
        synchronize_runtime_graph(graph)
    except Exception as exc:
        raise _RebuildExecutionError(source, exc) from exc

    regulatory_events = getattr(graph, "regulatory_events", []) or []
    return GraphRebuildResponse(
        status="persisted",
        source=source,
        asset_count=len(graph.assets),
        relationship_count=sum(len(items) for items in graph.relationships.values()),
        regulatory_event_count=len(regulatory_events),
    )

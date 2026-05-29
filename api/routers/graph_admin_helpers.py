"""Private helper functions, metrics and exceptions for graph administration.

This module houses audit logging, exception mappings, and database status-tracking
logic to keep the main graph_admin router focused on HTTP request routing.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import perf_counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data.repository import AssetGraphRepository

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Repository imports are done dynamically inside functions to respect test patches on graph_admin.AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.recovery_gate import ExecutionBlockedError

from ..api_models import GraphRebuildResponse
from ..auth import User
from ..graph_lifecycle import (
    GraphRuntimeLifecycleState,
    begin_rebuild,
    complete_rebuild,
    get_runtime_lifecycle_state,
)
from ..graph_lifecycle_providers import (
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    GraphPersistenceSaveError,
    GraphRebuildSource,
    GraphRebuildSourceError,
)
from ..metrics import (
    REBUILD_DURATION,
    REBUILD_FAILURE,
    REBUILD_REQUESTS,
    REBUILD_SUCCESS,
    update_graph_metrics,
    update_rebuild_state_metric,
)

LOGGER_NAME = "api.routers.graph_admin"
logger = logging.getLogger(LOGGER_NAME)

_REBUILD_IN_PROGRESS_MESSAGE = "A graph rebuild is already in progress. Please try again later."
_REBUILD_AUDIT_REQUESTED = "graph_rebuild_requested"
_REBUILD_AUDIT_REJECTED = "graph_rebuild_rejected"
_REBUILD_AUDIT_SUCCEEDED = "graph_rebuild_succeeded"
_REBUILD_AUDIT_FAILED = "graph_rebuild_failed"
_REBUILD_PATH = "/api/graph/rebuild"
_MAX_AUDIT_USER_REF_LENGTH = 64
_MAX_FAILURE_MESSAGE_LENGTH = 512

# Regex to match URLs, DSNs, and user:pass@host credential sequences for redaction.
# Intent: Redact connection strings, credentials, and full URL segments containing sensitive details.
_URL_PATTERN = re.compile(
    r"\b(?:[a-z0-9+\-.]+://\S+|[a-z0-9_.+\-]+:[^\s@/]+@[^\s'\"<>()/]+)",
    re.IGNORECASE,
)

_SECRET_PATTERN = re.compile(
    r"(password|token|secret|key|api[_-]?key|auth|authorization)\s*[:=]\s*(?:Bearer\s+)?['\"]?[^\s'\"]+",
    re.IGNORECASE,
)


def _get_graph_admin_module():
    """Delay importing api.routers.graph_admin to avoid circular imports and allow test monkeypatching."""
    from importlib import import_module

    return import_module("api.routers.graph_admin")


class _RebuildRuntime:
    """Process-local rebuild concurrency and executor state."""

    def __init__(self) -> None:
        """Create empty rebuild runtime state."""
        self.lock: asyncio.Lock | None = None
        self.lock_loop: asyncio.AbstractEventLoop | None = None
        self.executor: ThreadPoolExecutor | None = None

    def is_busy(self) -> bool:
        """Return whether a rebuild is running or queued."""
        return get_runtime_lifecycle_state() == GraphRuntimeLifecycleState.REBUILDING

    def mark_busy(self) -> None:
        """Mark rebuild execution as active."""
        begin_rebuild()

    def mark_idle(self, *, succeeded: bool) -> None:
        """Finalize lifecycle after rebuild via complete_rebuild()."""
        complete_rebuild(succeeded=succeeded)

    def clear_busy_after_contention(self) -> None:
        """Clear transient REBUILDING state when work was rejected before execution."""
        complete_rebuild(succeeded=True)

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


class _RebuildExecutionError(RuntimeError):
    """Wrap rebuild execution errors with bounded audit source context."""

    def __init__(self, source: GraphRebuildSource, cause: Exception | asyncio.CancelledError) -> None:
        """Store source and underlying failure without exposing raw details.

        Do not wrap asyncio.CancelledError — allow task cancellation to propagate.
        """
        if isinstance(cause, asyncio.CancelledError):
            # Re-raise CancelledError so it isn't swallowed by wrapper construction.
            raise cause from None
        super().__init__(cause.__class__.__name__)
        self.source = source
        self.cause = cause


class _DistributedLockAcquisitionError(RuntimeError):
    """Raised when the distributed lock cannot be acquired."""


class _DistributedLockLostError(RuntimeError):
    """Raised when the distributed lock is lost mid-rebuild."""


def _rebuild_in_progress_error() -> HTTPException:
    """Return the graph rebuild in-progress response."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=_REBUILD_IN_PROGRESS_MESSAGE,
    )


def _claim_rebuild_or_raise() -> asyncio.Lock:
    """Claim rebuild execution or raise a fail-fast HTTP error."""
    rebuild_lock = _REBUILD_RUNTIME.get_lock()
    if _REBUILD_RUNTIME.is_busy() or rebuild_lock.locked():
        raise _rebuild_in_progress_error()
    _REBUILD_RUNTIME.mark_busy()
    return rebuild_lock


def _map_rebuild_error(exc: Exception | asyncio.CancelledError) -> HTTPException:
    """Map rebuild domain errors to sanitized HTTP errors."""
    root_exc = _unwrap_rebuild_error(exc)

    if isinstance(root_exc, _DistributedLockAcquisitionError):
        return _rebuild_in_progress_error()

    if isinstance(root_exc, (_DistributedLockLostError, ExecutionBlockedError)):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": (
                    "distributed_lock_lost_during_rebuild"
                    if isinstance(root_exc, _DistributedLockLostError)
                    else "execution_blocked"
                ),
                "message": (
                    "Distributed lock lost during rebuild."
                    if isinstance(root_exc, _DistributedLockLostError)
                    else str(root_exc)
                ),
            },
        )

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

    logger.error("Unexpected graph rebuild failure: %s", root_exc.__class__.__name__)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Graph rebuild failed.",
    )


def _rebuild_status_code(exc: Exception | asyncio.CancelledError) -> int:
    """Return sanitized rebuild status code for audit logging."""
    root_exc = _unwrap_rebuild_error(exc)

    if isinstance(root_exc, _DistributedLockAcquisitionError):
        return status.HTTP_429_TOO_MANY_REQUESTS
    if isinstance(root_exc, (_DistributedLockLostError, ExecutionBlockedError)):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if isinstance(
        root_exc,
        (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError),
    ):
        return status.HTTP_409_CONFLICT

    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _resolve_user_ref(user: User) -> str:
    """Return the bounded user reference used in rebuild audit logs."""
    username = (user.username or "").strip()[:_MAX_AUDIT_USER_REF_LENGTH]
    normalized = "".join(char if char.isprintable() else "_" for char in username)
    return normalized or "unknown"


def _audit_timestamp() -> str:
    """Return a UTC timestamp string for audit log records."""
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017


def _duration_ms(started_at: float) -> int:
    """Return non-negative elapsed wall time in milliseconds."""
    return max(0, int((perf_counter() - started_at) * 1000))


def _log_rebuild_requested(*, user_ref: str) -> None:
    """Emit a bounded audit event for rebuild request start."""
    REBUILD_REQUESTS.inc()
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


def _log_rebuild_succeeded(
    *,
    user_ref: str,
    response: GraphRebuildResponse,
    duration_ms: int,
) -> None:
    """Emit a bounded audit event for successful rebuild completion."""
    REBUILD_SUCCESS.labels(source=response.source).inc()
    REBUILD_DURATION.observe(duration_ms / 1000.0)
    update_graph_metrics(response.asset_count, response.relationship_count)
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


def _rebuild_failure_category(exc: Exception | asyncio.CancelledError) -> str:
    """Return a bounded failure category for rebuild audit logs."""
    root_exc = _unwrap_rebuild_error(exc)
    categories = {
        _DistributedLockAcquisitionError: "distributed_lock_acquisition_failed",
        _DistributedLockLostError: "distributed_lock_lost",
        ExecutionBlockedError: "execution_blocked_by_recovery_gate",
        GraphPersistenceNotConfiguredError: "persistence_not_configured",
        GraphPersistenceNonDurableError: "persistence_non_durable",
        GraphRebuildSourceError: "rebuild_source_error",
        GraphPersistenceSaveError: "persistence_save_error",
    }
    return categories.get(type(root_exc), "unexpected_error")


def _rebuild_source_from_exception(exc: Exception | asyncio.CancelledError) -> GraphRebuildSource | None:
    """Return the bounded rebuild source, if one is available on the exception."""
    if isinstance(exc, _RebuildExecutionError):
        return exc.source
    return None


def _log_rebuild_failed(
    *,
    user_ref: str,
    exc: Exception | asyncio.CancelledError,
    status_code: int,
    duration_ms: int,
) -> None:
    """Emit a bounded audit event for rebuild failure."""
    category = _rebuild_failure_category(exc)
    REBUILD_FAILURE.labels(category=category).inc()
    REBUILD_DURATION.observe(duration_ms / 1000.0)

    logger.error(
        "graph_rebuild_audit",
        extra={
            "event": _REBUILD_AUDIT_FAILED,
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "failure_category": category,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "source": _rebuild_source_from_exception(exc),
            "timestamp": _audit_timestamp(),
        },
    )


def _log_unexpected_rebuild_exception(*, user_ref: str, exc: Exception | asyncio.CancelledError) -> None:
    """Emit a sentinel alert log for unexpected rebuild failures."""
    logger.critical(
        "graph_rebuild_unexpected_exception",
        exc_info=False,
        extra={
            "event": "graph_rebuild_unexpected_exception",
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "exception_type": type(exc).__name__,
            "timestamp": _audit_timestamp(),
        },
    )
    logger.debug("Unexpected rebuild exception details", exc_info=True)


def _unwrap_rebuild_error(exc: Exception | asyncio.CancelledError) -> Exception | asyncio.CancelledError:
    """Return the underlying rebuild error for mapping and audit categorization."""
    if isinstance(exc, _RebuildExecutionError):
        return exc.cause
    return exc


def _create_job_safe(session_factory: Callable[[], Session], user_ref: str) -> str:
    """Create a rebuild job record in pending status."""
    graph_admin = _get_graph_admin_module()
    repo_cls = graph_admin.AssetGraphRepository
    session_scope = graph_admin.session_scope

    try:
        with session_scope(session_factory) as session:
            return repo_cls(session).create_rebuild_job(requested_by=user_ref)
    except Exception as exc:
        logger.exception("Failed to create rebuild job record: %s", exc.__class__.__name__)
        raise GraphPersistenceSaveError("Failed to create rebuild job record.") from exc


def _run_job_update(
    session_factory: Callable[[], Session],
    job_id: str,
    action: Callable[[AssetGraphRepository], None],
    error_message: str,
) -> None:
    """Execute a repository job-update action; raise GraphPersistenceSaveError on failure."""
    graph_admin = _get_graph_admin_module()
    repo_cls = graph_admin.AssetGraphRepository
    session_scope = graph_admin.session_scope

    try:
        with session_scope(session_factory) as session:
            action(repo_cls(session))
    except Exception as exc:
        logger.exception("Rebuild job %s update failed: %s", job_id, exc.__class__.__name__)
        raise GraphPersistenceSaveError(error_message) from exc


def _update_job_source_safe(session_factory: Callable[[], Session], job_id: str, source: str) -> None:
    """Update rebuild job source safely."""
    _run_job_update(
        session_factory,
        job_id,
        lambda repo: repo.update_rebuild_job_source(job_id, source),
        "Failed to update rebuild job source.",
    )


def _mark_job_running_safe(session_factory: Callable[[], Session], job_id: str) -> None:
    """Mark rebuild job as running safely."""
    _run_job_update(
        session_factory,
        job_id,
        lambda repo: repo.mark_rebuild_job_running(job_id),
        "Failed to mark rebuild job as running.",
    )


def _mark_job_succeeded_safe(
    session_factory: Callable[[], Session],
    job_id: str,
    node_count: int,
    edge_count: int,
    duration_ms: int,
) -> None:
    """Mark rebuild job as succeeded safely."""
    _run_job_update(
        session_factory,
        job_id,
        lambda repo: repo.mark_rebuild_job_succeeded(
            job_id,
            node_count=node_count,
            edge_count=edge_count,
            duration_ms=duration_ms,
        ),
        "Failed to persist rebuild job success state.",
    )


def _mark_job_failed_safe(
    session_factory: Callable[[], Session],
    job_id: str,
    exc: Exception | asyncio.CancelledError,
    duration_ms: int,
) -> None:
    """Mark a rebuild job as failed safely."""
    _run_job_update(
        session_factory,
        job_id,
        lambda repo: repo.mark_rebuild_job_failed(
            job_id,
            failure_category=_rebuild_failure_category(exc),
            failure_message=_sanitize_failure_message(exc),
            duration_ms=duration_ms,
        ),
        "Failed to persist rebuild job failure state.",
    )


def _sanitize_failure_message(exc: Exception | asyncio.CancelledError) -> str:
    """Return a bounded, sanitized failure message for rebuild job persistence.

    Security goals:
        - prevent credential/DSN leakage
        - prevent internal topology disclosure
        - prevent traceback persistence
        - preserve operator-actionable semantics

    Behaviour:
        - known safe/domain exceptions retain sanitized messages
        - unknown exceptions collapse to stable class/category names
        - output is bounded to fixed maximum size
    """
    root_exc = _unwrap_rebuild_error(exc)

    # Explicitly safe/domain-facing exceptions
    safe_exceptions = (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
        GraphRebuildSourceError,
        GraphPersistenceSaveError,
        ExecutionBlockedError,
    )

    # Materialize safe message
    if isinstance(root_exc, safe_exceptions):
        raw_message = str(root_exc).strip() or root_exc.__class__.__name__
    else:
        # IMPORTANT: Do not persist arbitrary exception strings
        raw_message = f"InternalError[{root_exc.__class__.__name__}]"

    # Redact sensitive patterns
    sanitized = raw_message

    # URLs / DSNs
    sanitized = _URL_PATTERN.sub(
        "[REDACTED_URL]",
        sanitized,
    )

    # Basic credential-like patterns
    sanitized = _SECRET_PATTERN.sub(
        "[REDACTED_SECRET]",
        sanitized,
    )

    # Normalize whitespace
    sanitized = " ".join(sanitized.split()).strip()

    # Enforce bounded persistence size
    if len(sanitized) > _MAX_FAILURE_MESSAGE_LENGTH:
        sanitized = sanitized[: _MAX_FAILURE_MESSAGE_LENGTH - 3] + "..."

    return sanitized


def _finalize_rebuild_success(
    *,
    session_factory: Callable[[], Session],
    job_id: str,
    graph: AssetRelationshipGraph,
    source: GraphRebuildSource,
    job_started_at: float,
) -> GraphRebuildResponse:
    """Build the rebuild response payload and persist success job state."""
    regulatory_events = getattr(graph, "regulatory_events", []) or []
    response = GraphRebuildResponse(
        status="persisted",
        source=source,
        asset_count=len(graph.assets),
        relationship_count=sum(len(items) for items in graph.relationships.values()),
        regulatory_event_count=len(regulatory_events),
    )
    _mark_job_succeeded_safe(
        session_factory,
        job_id,
        node_count=response.asset_count,
        edge_count=response.relationship_count,
        duration_ms=_duration_ms(job_started_at),
    )
    update_rebuild_state_metric("succeeded")
    return response


def _finalize_rebuild_failure(
    *,
    session_factory: Callable[[], Session],
    job_id: str,
    exc: Exception | asyncio.CancelledError,
    job_started_at: float,
) -> None:
    """Persist failed rebuild terminal state."""
    _mark_job_failed_safe(session_factory, job_id, exc, _duration_ms(job_started_at))
    update_rebuild_state_metric("failed")


def _create_and_start_rebuild_job(
    session_factory: Callable[[], Session],
    user_ref: str,
    worker_id: str,
) -> tuple[str, float]:
    """Create a rebuild job record and transition it to running."""
    graph_admin = _get_graph_admin_module()
    repo_cls = graph_admin.AssetGraphRepository
    session_scope = graph_admin.session_scope

    job_id = _create_job_safe(session_factory, user_ref)
    update_rebuild_state_metric("pending")
    job_started_at = perf_counter()
    _mark_job_running_safe(session_factory, job_id)
    update_rebuild_state_metric("running")

    try:
        with session_scope(session_factory) as session:
            repo_cls(session).update_rebuild_heartbeat(job_id, worker_id)
    except Exception as exc:
        logger.exception(
            "Failed to record initial rebuild heartbeat: %s (job_id=%s). Failing closed.",
            type(exc).__name__,
            job_id,
        )
        try:
            _finalize_rebuild_failure(
                session_factory=session_factory,
                job_id=job_id,
                exc=exc,
                job_started_at=job_started_at,
            )
        except Exception as fallback_exc:
            logger.error("Failed to persist failed status for job %s: %s", job_id, fallback_exc)
        raise GraphPersistenceSaveError(
            f"Cannot track rebuild liveness: heartbeat failed ({type(exc).__name__})"
        ) from exc

    return job_id, job_started_at

"""Operator routes for graph administration."""

from __future__ import annotations

import asyncio
import contextvars
import logging
import re
import threading
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import Annotated, NoReturn, cast
from sqlalchemy import text
from sqlalchemy import text

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import RebuildJobORM
from src.data.distributed_lock import DistributedLock
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

from ..api_models import GraphRebuildResponse, RebuildJobListResponse, RebuildJobResponse
from ..auth import User, get_current_rebuild_operator_user
from ..graph_lifecycle import (
    GraphRuntimeLifecycleState,
    begin_rebuild,
    complete_rebuild,
    get_runtime_lifecycle_state,
    synchronize_runtime_graph,
)
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
from ..metrics import (
    HEARTBEAT_LAST_SUCCESS_TIMESTAMP,
    HEARTBEAT_UPDATE_TOTAL,
    LOCK_REFRESH_DURATION,
    LOCK_REFRESH_TOTAL,
    REBUILD_DURATION,
    REBUILD_FAILURE,
    REBUILD_REQUESTS,
    REBUILD_SUCCESS,
    increment_recovery_trigger,
    update_graph_metrics,
    update_rebuild_state_metric,
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
_MAX_REBUILD_JOB_LIST_RESULTS = 100

_URL_PATTERN = re.compile(
    r"\b(?:[a-z][a-z0-9+\-.]*://\S+|[a-z][a-z0-9+\-.]*:[^\s/@]+:[^\s/@]+@\S+)",
    re.IGNORECASE,
)


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


class _RebuildExecutionError(Exception):
    """Wrap rebuild execution errors with bounded audit source context."""

    def __init__(self, source: GraphRebuildSource, cause: Exception | BaseException) -> None:
        """Store source and underlying failure without exposing raw details."""
        super().__init__(cause.__class__.__name__)
        self.source = source
        self.cause = cause


class _DistributedLockAcquisitionError(Exception):
    """Raised when the distributed lock cannot be acquired."""


class _DistributedLockLostError(Exception):
    """Raised when the distributed lock is lost mid-rebuild."""


@router.post(_REBUILD_PATH)
async def rebuild_graph(
    current_user: Annotated[User, Depends(get_current_rebuild_operator_user)],
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

    # A mutable reference container to share logging states across async frames
    tracking_state = {"audit_logged": False}
    lock_acquired = False

    try:
        await rebuild_lock.acquire()
        lock_acquired = True

        try:
            return await _run_rebuild_in_executor(
                loop,
                settings,
                user_ref=user_ref,
                started_at=started_at,
                tracking_state=tracking_state,
            )
        except (
            HTTPException,
            _RebuildExecutionError,
            _DistributedLockAcquisitionError,
            _DistributedLockLostError,
            GraphPersistenceNonDurableError,
            GraphPersistenceNotConfiguredError,
            GraphPersistenceSaveError,
            GraphRebuildSourceError,
            ExecutionBlockedError,
        ) as exc:
            root_exc = _unwrap_rebuild_error(exc)

            # If it's a lock contention error, handle it cleanly as a rejection
            if isinstance(root_exc, _DistributedLockAcquisitionError):
                _REBUILD_RUNTIME.clear_busy_after_contention()
                # Intercept here: on_done has already handled the _log_rebuild_rejected event.
                # Flag it as accounted for so the general fallback failure block doesn't trigger.
                tracking_state["audit_logged"] = True
            else:
                _REBUILD_RUNTIME.mark_idle(succeeded=False)

            # Defensive safety net: If the callback never completed to write any audit trace, write it now
            if not tracking_state["audit_logged"]:
                _log_rebuild_failed(
                    user_ref=user_ref,
                    exc=exc,
                    status_code=_rebuild_status_code(exc),
                    duration_ms=_duration_ms(started_at),
                )
                tracking_state["audit_logged"] = True

            raise _map_rebuild_error(exc) from None

        except Exception as exc:
            # Emit the structured critical alert sentinel identically to the callback path
            _log_unexpected_rebuild_exception(user_ref=user_ref, exc=exc)
            _REBUILD_RUNTIME.mark_idle(succeeded=False)

            # Ensure structural audit coverage for general unexpected programming errors
            if not tracking_state["audit_logged"]:
                _log_rebuild_failed(
                    user_ref=user_ref,
                    exc=exc,
                    status_code=_rebuild_status_code(exc),
                    duration_ms=_duration_ms(started_at),
                )
                tracking_state["audit_logged"] = True

            raise _map_rebuild_error(exc) from None
    finally:
        if lock_acquired:
            rebuild_lock.release()
        else:
            _REBUILD_RUNTIME.mark_idle(succeeded=False)


async def _run_rebuild_in_executor(
    loop: asyncio.AbstractEventLoop,
    settings: GraphLifecycleSettings,
    *,
    user_ref: str,
    started_at: float,
    tracking_state: dict[str, bool],
) -> GraphRebuildResponse:
    """Run rebuild work in the dedicated executor."""
    ctx = contextvars.copy_context()

    def rebuild_with_context() -> GraphRebuildResponse:
        return _perform_rebuild_and_persist_sync(settings, user_ref=user_ref)

    try:
        future = cast(
            asyncio.Future[GraphRebuildResponse],
            loop.run_in_executor(
                _REBUILD_RUNTIME.get_executor(),
                ctx.run,
                rebuild_with_context,
            ),
        )
    except Exception as exc:
        _REBUILD_RUNTIME.mark_idle(succeeded=False)
        _log_rebuild_failed(
            user_ref=user_ref,
            exc=exc,
            status_code=_rebuild_status_code(exc),
            duration_ms=_duration_ms(started_at),
        )
        tracking_state["audit_logged"] = True
        raise

    def on_done(done_future: asyncio.Future[GraphRebuildResponse]) -> None:
        """Finalize rebuild state and emit outcome audit logs."""
        try:
            response = done_future.result()
        except (
            HTTPException,
            _RebuildExecutionError,
            _DistributedLockAcquisitionError,
            GraphPersistenceNonDurableError,
            GraphPersistenceNotConfiguredError,
            GraphPersistenceSaveError,
            GraphRebuildSourceError,
            ExecutionBlockedError,
        ) as exc:
            if isinstance(_unwrap_rebuild_error(exc), _DistributedLockAcquisitionError):
                _REBUILD_RUNTIME.mark_idle(succeeded=True)
                _log_rebuild_rejected(user_ref=user_ref)
            else:
                _REBUILD_RUNTIME.mark_idle(succeeded=False)
                _log_rebuild_failed(
                    user_ref=user_ref,
                    exc=exc,
                    status_code=_rebuild_status_code(exc),
                    duration_ms=_duration_ms(started_at),
                )
            tracking_state["audit_logged"] = True
            return
        except _DistributedLockLostError as exc:
            _REBUILD_RUNTIME.mark_idle(succeeded=False)
            _log_rebuild_failed(
                user_ref=user_ref,
                exc=exc,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                duration_ms=_duration_ms(started_at),
            )
            tracking_state["audit_logged"] = True
            return
        except Exception as exc:
            _log_unexpected_rebuild_exception(user_ref=user_ref, exc=exc)
            _REBUILD_RUNTIME.mark_idle(succeeded=False)
            _log_rebuild_failed(
                user_ref=user_ref,
                exc=exc,
                status_code=_rebuild_status_code(exc),
                duration_ms=_duration_ms(started_at),
            )
            tracking_state["audit_logged"] = True
            return

        _REBUILD_RUNTIME.mark_idle(succeeded=True)
        _log_rebuild_succeeded(
            user_ref=user_ref,
            response=response,
            duration_ms=_duration_ms(started_at),
        )
        tracking_state["audit_logged"] = True

    future.add_done_callback(on_done)
    return await asyncio.shield(future)


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


def _map_rebuild_error(exc: Exception) -> HTTPException:
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


def _rebuild_status_code(exc: Exception) -> int:
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


def _rebuild_failure_category(exc: Exception | BaseException) -> str:
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


def _rebuild_source_from_exception(exc: Exception | BaseException) -> GraphRebuildSource | None:
    """Return the bounded rebuild source, if one is available on the exception."""
    if isinstance(exc, _RebuildExecutionError):
        return exc.source
    return None


def _log_rebuild_failed(
    *,
    user_ref: str,
    exc: Exception | BaseException,
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


def _log_unexpected_rebuild_exception(*, user_ref: str, exc: Exception) -> None:
    """Emit a sentinel alert log for unexpected rebuild failures."""
    logger.critical(
        "graph_rebuild_unexpected_exception",
        exc_info=True,
        extra={
            "event": "graph_rebuild_unexpected_exception",
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "exception_type": type(exc).__name__,
            "timestamp": _audit_timestamp(),
        },
    )


def _unwrap_rebuild_error(exc: Exception | BaseException) -> Exception | BaseException:
    """Return the underlying rebuild error for mapping and audit categorization."""
    if isinstance(exc, _RebuildExecutionError):
        return exc.cause
    return exc


def shutdown_rebuild_executor_sync() -> None:
    """Shut down the rebuild executor synchronously."""
    _REBUILD_RUNTIME.shutdown_executor()


def init_rebuild_executor(_settings: GraphLifecycleSettings | None = None) -> None:
    """Explicitly initialize the process-local rebuild executor."""
    _REBUILD_RUNTIME.get_executor()


def _create_job_safe(session_factory: Callable[[], Session], user_ref: str) -> str:
    """Create a rebuild job record in pending status."""
    try:
        with session_scope(session_factory) as session:
            return AssetGraphRepository(session).create_rebuild_job(requested_by=user_ref)
    except Exception as exc:
        logger.error("Failed to create rebuild job record: %s", exc.__class__.__name__)
        raise GraphPersistenceSaveError("Failed to create rebuild job record.") from exc


def _run_job_update(
    session_factory: Callable[[], Session],
    job_id: str,
    action: Callable[[AssetGraphRepository], None],
    error_message: str,
) -> None:
    """Execute a repository job-update action; raise GraphPersistenceSaveError on failure."""
    try:
        with session_scope(session_factory) as session:
            action(AssetGraphRepository(session))
    except Exception as exc:
        logger.error("Rebuild job %s update failed: %s", job_id, exc.__class__.__name__)
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
    exc: Exception | BaseException,
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


def _create_and_start_rebuild_job(
    session_factory: Callable[[], Session],
    user_ref: str,
    worker_id: str,
) -> tuple[str, float]:
    """Create a rebuild job record and transition it to running."""
    job_id = _create_job_safe(session_factory, user_ref)
    update_rebuild_state_metric("pending")
    job_started_at = perf_counter()
    _mark_job_running_safe(session_factory, job_id)
    update_rebuild_state_metric("running")

    try:
        with session_scope(session_factory) as session:
            AssetGraphRepository(session).update_rebuild_heartbeat(job_id, worker_id)
    except Exception as exc:
        logger.error(
            "Failed to record initial rebuild heartbeat: %s (job_id=%s). Failing closed.",
            type(exc).__name__,
            job_id,
        )
        _finalize_rebuild_failure(
            session_factory=session_factory,
            job_id=job_id,
            exc=exc,
            job_started_at=job_started_at,
        )
        raise GraphPersistenceSaveError(
            f"Cannot track rebuild liveness: heartbeat failed ({type(exc).__name__})"
        ) from exc

    return job_id, job_started_at


def _heartbeat_keeper(
    *,
    session_factory: Callable[[], Session],
    dist_lock: DistributedLock,
    job_id: str,
    worker_id: str,
    stop_event: threading.Event,
    lock_lost_event: threading.Event,
    interval_seconds: float,
) -> None:
    """Background thread that periodically refreshes both the distributed lock and rebuild heartbeat."""
    while not stop_event.wait(timeout=interval_seconds):
        try:
            # Lock refresh with metrics instrumentation
            with LOCK_REFRESH_DURATION.time():
                refresh_ok = dist_lock.refresh()

            if not refresh_ok:
                LOCK_REFRESH_TOTAL.labels(status="failure").inc()
                logger.error("Heartbeat keeper lost distributed lock for job %s.", job_id)
                lock_lost_event.set()
                return

            LOCK_REFRESH_TOTAL.labels(status="success").inc()

            # Heartbeat update with metrics instrumentation
            # NOTE: Transient DB errors currently trigger lock-lost signal.
            # Future enhancement: implement retry logic for transient failures.
            try:
                with session_scope(session_factory) as session:
                    AssetGraphRepository(session).update_rebuild_heartbeat(job_id, worker_id)
                HEARTBEAT_UPDATE_TOTAL.labels(status="success").inc()
                HEARTBEAT_LAST_SUCCESS_TIMESTAMP.set(time.time())
            except Exception as hb_exc:
                HEARTBEAT_UPDATE_TOTAL.labels(status="failure").inc()
                logger.error(
                    "Heartbeat keeper database update failed for job %s: %s.",
                    job_id,
                    type(hb_exc).__name__,
                )
                lock_lost_event.set()
                return
        except Exception as exc:
            # Catches exceptions from lock refresh (e.g., database connectivity issues)
            LOCK_REFRESH_TOTAL.labels(status="failure").inc()
            logger.error(
                "Heartbeat keeper lock refresh failed for job %s: %s.",
                job_id,
                type(exc).__name__,
            )
            lock_lost_event.set()
            return


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
    exc: Exception | BaseException,
    job_started_at: float,
) -> None:
    """Persist failed rebuild terminal state."""
    _mark_job_failed_safe(session_factory, job_id, exc, _duration_ms(job_started_at))
    update_rebuild_state_metric("failed")


def _load_persisted_graph_snapshot(
    session_factory: Callable[[], Session],
) -> AssetRelationshipGraph:
    """Load the currently persisted graph snapshot for rollback safety."""
    with session_scope(session_factory) as session:
        return AssetGraphRepository(session).load_graph()


def _restore_persisted_graph_snapshot(
    persistence_url: str,
    snapshot: AssetRelationshipGraph,
) -> None:
    """Best-effort rollback of durable graph state when success persistence fails."""
    try:
        save_graph_to_persistence(persistence_url, snapshot)
    except Exception:
        logger.exception("Failed to restore persisted graph snapshot after rebuild failure")


def _handle_rebuild_failure(
    session_factory: Callable[[], Session],
    job_id: str,
    exc: Exception | BaseException,
    job_started_at: float,
    success_persisted: bool,
    graph_saved: bool,
    graph_snapshot: AssetRelationshipGraph | None,
    resolved_url: str,
    source: GraphRebuildSource | None,
) -> NoReturn:
    """Handle rebuild failure with rollback and persistence."""
    if not success_persisted:
        if graph_saved and graph_snapshot is not None:
            _restore_persisted_graph_snapshot(resolved_url, graph_snapshot)
        _finalize_rebuild_failure(
            session_factory=session_factory,
            job_id=job_id,
            exc=exc,
            job_started_at=job_started_at,
        )
    if source is not None:
        raise _RebuildExecutionError(source, exc) from exc
    raise


@contextmanager
def _orchestrate_heartbeat(
    session_factory: Callable[[], Session],
    dist_lock: DistributedLock,
    job_id: str,
    lock_ttl: int,
) -> Generator[threading.Event, None, None]:
    """Context manager to cleanly scope background heartbeat tracking threads."""
    stop_heartbeat = threading.Event()
    lock_lost = threading.Event()
    heartbeat_interval = max(1, lock_ttl // 3)

    heartbeat_thread = threading.Thread(
        target=_heartbeat_keeper,
        kwargs={
            "session_factory": session_factory,
            "dist_lock": dist_lock,
            "job_id": job_id,
            "worker_id": dist_lock.holder_id,
            "stop_event": stop_heartbeat,
            "lock_lost_event": lock_lost,
            "interval_seconds": heartbeat_interval,
        },
        daemon=True,
        name=f"heartbeat-keeper-{job_id}",
    )
    heartbeat_thread.start()
    try:
        yield lock_lost
    finally:
        stop_heartbeat.set()
        if heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=2.0)


def _run_rebuild_pipeline(
    session_factory: Callable[[], Session],
    settings: GraphLifecycleSettings,
    resolved_url: str,
    job_id: str,
    job_started_at: float,
    lock_lost: threading.Event,
) -> GraphRebuildResponse:
    """Run sequential synchronization logic after setup validations pass."""
    source: GraphRebuildSource | None = None
    success_persisted = False
    graph_snapshot: AssetRelationshipGraph | None = None
    graph_saved = False

    try:
        if lock_lost.is_set():
            raise _DistributedLockLostError("Lost distributed lock at stage=initialization")

        graph, source = build_rebuild_graph(settings)
        _update_job_source_safe(session_factory, job_id, str(source))

        if lock_lost.is_set():
            raise _DistributedLockLostError("Lost distributed lock at stage=pre-persistence")

        graph_snapshot = _load_persisted_graph_snapshot(session_factory)

        def _ensure_lock_not_lost_before_commit() -> None:
            if lock_lost.is_set():
                raise _DistributedLockLostError("Lost distributed lock at stage=graph-commit")

        save_graph_to_persistence(
            resolved_url,
            graph,
            pre_commit_check=_ensure_lock_not_lost_before_commit,
        )
        graph_saved = True

        if lock_lost.is_set():
            graph_saved = False
            raise _DistributedLockLostError("Lost distributed lock at stage=pre-success-write")

        response = _finalize_rebuild_success(
            session_factory=session_factory,
            job_id=job_id,
            graph=graph,
            source=source,
            job_started_at=job_started_at,
        )
        success_persisted = True
        synchronize_runtime_graph(graph, job_id=job_id)
        return response
    except (Exception, asyncio.CancelledError) as exc:
        _handle_rebuild_failure(
            session_factory=session_factory,
            job_id=job_id,
            exc=exc,
            job_started_at=job_started_at,
            success_persisted=success_persisted,
            graph_saved=graph_saved,
            graph_snapshot=graph_snapshot,
            resolved_url=resolved_url,
            source=source,
        )
        raise


def _perform_rebuild_and_persist_sync(
    settings: GraphLifecycleSettings,
    *,
    user_ref: str,
) -> GraphRebuildResponse:
    """
    Rebuild the graph, persist it, then publish it to runtime state.

    Architecture:
        Plane 1 (Domain Plane):
            - Asset graph persistence
            - Rebuild execution
            - Runtime graph publication
            - May use regional/local replicas for read scaling

        Plane 2 (Coordination Plane):
            - Distributed lock coordination
            - Heartbeat authority
            - Recovery gating
            - MUST target authoritative primary-only database

    Coordination Safety Rules:
        - coordination_database_url MUST be explicitly configured
        - coordination plane MUST use isolated engine/session pools
        - coordination plane MUST NOT reuse domain-plane sessions
        - coordination authority MUST fail closed on connectivity loss
    """
    from src.data.distributed_lock import LockLease, LockLifecycleState, LockState

    #
    # -------------------------------------------------------------------------
    # Resolve Domain Plane (Plane 1)
    # -------------------------------------------------------------------------
    #

    resolved_domain_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)

    domain_engine = create_engine_from_url(
        resolved_domain_url,
    )

    #
    # -------------------------------------------------------------------------
    # Resolve Coordination Plane (Plane 2)
    # -------------------------------------------------------------------------
    #
    # IMPORTANT:
    # Coordination isolation MUST be explicit.
    #
    # Never silently inherit DATABASE_URL / asset_graph_database_url.
    # Silent fallback structurally defeats split-brain protections.
    #

    coordination_database_url = settings.coordination_database_url

    if not coordination_database_url:
        raise RuntimeError(
Choose one policy and remove the other. For single-DB deployments with a fallback:

coordination_database_url = settings.coordination_database_url or settings.asset_graph_database_url
if not coordination_database_url:
    raise RuntimeError('Neither coordination_database_url nor asset_graph_database_url is configured.')
if not settings.coordination_database_url:
    logger.warning('coordination_database_url not set; falling back to asset_graph_database_url.')
resolved_coordination_url = resolve_durable_graph_persistence_url(coordination_database_url)
        )

    resolved_coordination_url = resolve_durable_graph_persistence_url(coordination_database_url)

    #
    # IMPORTANT:
    # Option A: Warn and fall back to asset_graph_database_url for single-DB deployments
    coordination_database_url = settings.coordination_database_url or settings.asset_graph_database_url
    if not coordination_database_url:
        raise RuntimeError(
            "Neither coordination_database_url nor asset_graph_database_url is configured."
        )
    if not settings.coordination_database_url:
        logger.warning(
            "coordination_database_url is not set; falling back to asset_graph_database_url. "
            "For production, set COORDINATION_DATABASE_URL to an authoritative primary."
        )

    # Option B: If the strict no-fallback policy is intentional, document it in DEPLOYMENT.md
    # and add a migration note in the PR, then keep the RuntimeError but update
    # get_graph_lifecycle_settings() to read from the env var with a clear error.
    #
    # Rationale:
    #   - separate pool sizing
    #   - separate retry semantics
    #   - separate observability
    #   - coordination isolation guarantees
    #

    coordination_engine = create_engine_from_url(
        resolved_coordination_url,
    )

    #
    # -------------------------------------------------------------------------
    # Runtime Coordination State
    # -------------------------------------------------------------------------
    #

    lock_acquired = False
    dist_lock: DistributedLock | None = None

    try:
        #
        # ---------------------------------------------------------------------
        # Create isolated session factories
        # ---------------------------------------------------------------------
        #
        domain_session_factory = create_session_factory(domain_engine)

        coordination_session_factory = create_session_factory(coordination_engine)

        # Validate coordination authority (require primary)
        validate_coordination_database_primary(coordination_session_factory)

        # ---------------------------------------------------------------------

        coordination_session_factory = create_session_factory(coordination_engine)

        #
        # ---------------------------------------------------------------------
        # Validate coordination authority
        # ---------------------------------------------------------------------
        #
        # Coordination plane MUST point to authoritative primary.
        #
        # Example PostgreSQL validation:
        #   SELECT pg_is_in_recovery();
        #
        # This helper should fail closed if:
        #   - DB unreachable
        #   - server is replica
        #   - authority uncertain
        #

        validate_coordination_database_primary(coordination_session_factory)

        #
        # ---------------------------------------------------------------------
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

def validate_coordination_database_primary(session_factory):
    """Verify the coordination DB is a writable primary, not a replica.

    For PostgreSQL this uses pg_is_in_recovery(); for non-Postgres backends (e.g. SQLite)
    the check is a no-op because replica detection isn't applicable.
    """
    try:
        with session_factory() as session:
            bind = session.get_bind()
            dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
            # Only run pg_is_in_recovery on PostgreSQL; other backends don't have replicas
            if dialect_name != "postgresql":
                return
            result = session.execute(text("SELECT pg_is_in_recovery()")).scalar()
    except (SQLAlchemyError, OSError) as exc:
        # Fail closed: if we cannot determine DB role, prevent proceeding
        raise RuntimeError("Could not verify coordination database role") from exc

    if result:
        raise RuntimeError(
            "Coordination database is a read replica; coordination_database_url must point to the primary."
        )
        # ---------------------------------------------------------------------
        #

        lock_ttl = settings.rebuild_lock_ttl_seconds

        dist_lock = DistributedLock(
            coordination_session_factory=coordination_session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=lock_ttl,
        )

        lease = dist_lock.acquire()

        if not lease.acquired:
            raise _DistributedLockAcquisitionError("Could not acquire distributed rebuild lock")

        lock_acquired = True

        #
        # ---------------------------------------------------------------------
        # Validate authoritative coordination state
        # ---------------------------------------------------------------------
        #
        # LOST is reserved strictly for:
        #   - connectivity failure
        #   - coordination uncertainty
        #
        # UNKNOWN / EXPIRED are not LOST.
        #

        lock_state = dist_lock.check_state()

        if lock_state == LockState.LOST:
            raise RuntimeError("Coordination state lost immediately after lock acquisition")

        if lock_state != LockState.VALID:
            raise RuntimeError(f"Unexpected coordination state after acquisition: {lock_state}")

        #
        # ---------------------------------------------------------------------
        # Recovery safety gate
        # ---------------------------------------------------------------------
        #

        RecoveryGate(
            session_factory=domain_session_factory,
            lock=dist_lock,
            increment_recovery_trigger=increment_recovery_trigger,
            runtime_has_active_executor=False,
            lock_ttl_seconds=lock_ttl,
        ).ensure_safe_to_execute()

        #
        # ---------------------------------------------------------------------
        # Create rebuild job metadata
        # ---------------------------------------------------------------------
        #

        job_id, job_started_at = _create_and_start_rebuild_job(
            domain_session_factory,
            user_ref,
            dist_lock.holder_id,
        )

        #
        # ---------------------------------------------------------------------
        # Heartbeat orchestration
        # ---------------------------------------------------------------------
        #
        # lock_lost MUST ONLY represent:
        #   - coordination uncertainty
        #   - lost authority
        #
        # NOT:
        #   - normal contention
        #   - expiry
        #   - release
        #

        with _orchestrate_heartbeat(
            domain_session_factory,
            dist_lock,
            job_id,
            lock_ttl,
        ) as lock_lost:

            #
            # -------------------------------------------------------------
            # Execute rebuild pipeline
            # -------------------------------------------------------------
            #

            return _run_rebuild_pipeline(
                domain_session_factory,
                settings,
                resolved_domain_url,
                job_id,
                job_started_at,
                lock_lost,
            )

    finally:
        #
        # ---------------------------------------------------------------------
        # Best-effort lock release
        # ---------------------------------------------------------------------
        #
        # Do not attempt authoritative release if coordination state is LOST.
        #
        # LOST implies:
        #   - ownership uncertainty
        #   - connectivity uncertainty
        #   - fencing uncertainty
        #

        if lock_acquired and dist_lock is not None:
            try:
                state = dist_lock.check_state()
            except Exception:
                logger.exception("Error checking distributed lock state; treating as LOST and skipping release")
                state = LockState.LOST
            if state != LockState.LOST:
                try:
                    dist_lock.release()
                except Exception:
                    logger.exception("Failed to release distributed rebuild lock")
                logger.exception("Failed to release distributed rebuild lock")

        #
        # ---------------------------------------------------------------------
        # Dispose isolated engines independently
        # ---------------------------------------------------------------------
        #

        try:
            coordination_engine.dispose()
        finally:
            domain_engine.dispose()


def _sanitize_failure_message(exc: Exception | BaseException) -> str:
    """Return a bounded, sanitized failure message for job persistence."""
    root_exc = _unwrap_rebuild_error(exc)
    safe_exceptions = (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
        GraphRebuildSourceError,
        GraphPersistenceSaveError,
        ExecutionBlockedError,
    )
    if isinstance(root_exc, safe_exceptions):
        message = str(root_exc) if str(root_exc) else root_exc.__class__.__name__
    else:
        message = root_exc.__class__.__name__

    message = _URL_PATTERN.sub("[REDACTED_URL]", message)
    return message[:512]


@contextmanager
def _rebuild_persistence_session() -> Generator[Session, None, None]:
    """Context manager scoping data-source connection sessions."""
    settings = get_graph_lifecycle_settings()
    engine = None
    try:
        persistence_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        engine = create_engine_from_url(persistence_url)
        session_factory = create_session_factory(engine)

        with session_scope(session_factory) as session:
            yield session
    except HTTPException:
        raise
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database not configured",
        ) from exc
    except Exception as exc:
        logger.error("Rebuild persistence operation failed: %s", exc.__class__.__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database unavailable",
        ) from exc
    finally:
        if engine is not None:
            engine.dispose()


def _orm_to_response(job_orm: RebuildJobORM) -> RebuildJobResponse:
    """Convert RebuildJobORM to bounded RebuildJobResponse."""
    return RebuildJobResponse(
        job_id=job_orm.job_id,
        status=job_orm.status,
        source=job_orm.source,
        requested_by=job_orm.requested_by,
        created_at=job_orm.created_at,
        updated_at=job_orm.updated_at,
        started_at=job_orm.started_at,
        completed_at=job_orm.completed_at,
        duration_ms=job_orm.duration_ms,
        node_count=job_orm.node_count,
        edge_count=job_orm.edge_count,
        failure_category=job_orm.sanitized_failure_category,
        failure_message=job_orm.sanitized_failure_message,
    )


@router.get("/api/graph/rebuild/jobs/{job_id}")
def get_rebuild_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_rebuild_operator_user)],
) -> RebuildJobResponse:
    """Get rebuild job status by job ID."""
    with _rebuild_persistence_session() as session:
        job_orm = AssetGraphRepository(session).get_rebuild_job(job_id)
        if job_orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rebuild job not found",
            )
        return _orm_to_response(job_orm)


@router.get("/api/graph/rebuild/jobs")
def list_rebuild_jobs(
    current_user: Annotated[User, Depends(get_current_rebuild_operator_user)],
) -> RebuildJobListResponse:
    """List rebuild jobs ordered newest-first."""
    with _rebuild_persistence_session() as session:
        jobs_orm = AssetGraphRepository(session).list_rebuild_jobs(limit=_MAX_REBUILD_JOB_LIST_RESULTS)
        jobs = [_orm_to_response(job_orm) for job_orm in jobs_orm]
        return RebuildJobListResponse(jobs=jobs, count=len(jobs))

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
from typing import Annotated, cast

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
# Regex to detect and redact URL/DSN-like patterns from failure messages, including:
# - postgresql+asyncpg://user:pass@host/db
# - malformed postgresql:user:pass@host/db
# - https://example.com/path
# First alternation matches standard scheme:// URLs.
# Second alternation matches malformed DSN-like credentials without //.
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
        """Finalize lifecycle after rebuild via complete_rebuild().

        Args:
            succeeded: True if the rebuild completed successfully (→ READY),
                False if it failed (→ FAILED).
        """
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
        """Shut down the process-local rebuild executor.

        This is a blocking call that waits for threads to complete.
        Should be called via asyncio.to_thread() in async contexts.
        """
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


class _DistributedLockAcquisitionError(Exception):
    """Raised when the distributed lock cannot be acquired."""


class _DistributedLockLostError(Exception):
    """Raised when the distributed lock is lost mid-rebuild.

    Using a distinct exception class (rather than a plain RuntimeError) allows
    handlers to match by type instead of by error-message substring, making the
    code robust to any future rewording of the message text.  Lock loss is an
    expected operational condition (TTL expiry, DB connectivity), not a
    programming error, so this inherits from Exception rather than RuntimeError.
    """


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
            # Defensive cleanup for direct contention exceptions (e.g. tests that
            # monkeypatch executor paths): normal contention paths already clear
            # REBUILDING in the executor completion callback.
            root_exc = _unwrap_rebuild_error(exc)
            if isinstance(root_exc, _DistributedLockAcquisitionError) and _REBUILD_RUNTIME.is_busy():
                _REBUILD_RUNTIME.clear_busy_after_contention()
            elif isinstance(root_exc, _DistributedLockLostError) and _REBUILD_RUNTIME.is_busy():
                # Fallback for direct/test executor raises where the on_done
                # callback path did not run cleanup. Normal future-based lock-loss
                # cleanup is handled in on_done.
                _REBUILD_RUNTIME.mark_idle(succeeded=False)
            raise _map_rebuild_error(exc) from None
        except Exception as exc:
            runtime_was_busy = _REBUILD_RUNTIME.is_busy()
            if runtime_was_busy:
                _log_unexpected_rebuild_exception(user_ref=user_ref, exc=exc)
                _REBUILD_RUNTIME.mark_idle(succeeded=False)
            raise _map_rebuild_error(exc) from None
    finally:
        if lock_acquired:
            rebuild_lock.release()
        else:
            _REBUILD_RUNTIME.mark_idle(succeeded=False)


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


async def _run_rebuild_in_executor(
    loop: asyncio.AbstractEventLoop,
    settings: GraphLifecycleSettings,
    *,
    user_ref: str,
    started_at: float,
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
            return
        except _DistributedLockLostError as exc:
            # Lock lost mid-rebuild: heartbeat keeper has already signaled abort to
            # the worker; this branch still finalizes runtime state and emits
            # failure audit logging with a 503 status.
            _REBUILD_RUNTIME.mark_idle(succeeded=False)
            _log_rebuild_failed(
                user_ref=user_ref,
                exc=exc,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                duration_ms=_duration_ms(started_at),
            )
            return
        except Exception as exc:
            # Catch-all for unexpected (programming-bug) errors from rebuild execution.
            # Emit an explicit sentinel alert so unexpected failures are easy to
            # find during incident triage; the structured audit log from
            # _log_rebuild_failed records only the bounded category.
            # Re-raising inside an add_done_callback does not propagate to the awaiter
            # (the future result is already consumed above), so we intentionally do not
            # re-raise here.
            _log_unexpected_rebuild_exception(user_ref=user_ref, exc=exc)
            _REBUILD_RUNTIME.mark_idle(succeeded=False)
            _log_rebuild_failed(
                user_ref=user_ref,
                exc=exc,
                status_code=_rebuild_status_code(exc),
                duration_ms=_duration_ms(started_at),
            )
            return

        _REBUILD_RUNTIME.mark_idle(succeeded=True)
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

    if isinstance(root_exc, _DistributedLockAcquisitionError):
        return _rebuild_in_progress_error()

    if isinstance(root_exc, _DistributedLockLostError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Distributed lock lost during rebuild.",
        )

    if isinstance(root_exc, ExecutionBlockedError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(root_exc))

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
    return datetime.now(timezone.utc).isoformat()  # noqa: UP017 - Python 3.10 compatibility


def _duration_ms(started_at: float) -> int:
    """Return non-negative elapsed wall time in milliseconds."""
    return max(0, int((perf_counter() - started_at) * 1000))


def _log_rebuild_requested(*, user_ref: str) -> None:
    """Emit a bounded audit event for rebuild request start."""
    REBUILD_REQUESTS.inc()  # label-free; operator identity captured in audit log below
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


def _rebuild_failure_category(exc: Exception) -> str:
    """Return a bounded failure category for rebuild audit logs."""
    root_exc = _unwrap_rebuild_error(exc)
    if isinstance(root_exc, _DistributedLockAcquisitionError):
        return "distributed_lock_acquisition_failed"
    if isinstance(root_exc, _DistributedLockLostError):
        return "distributed_lock_lost"
    if isinstance(root_exc, ExecutionBlockedError):
        return "execution_blocked_by_recovery_gate"
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
    category = _rebuild_failure_category(exc)
    REBUILD_FAILURE.labels(category=category).inc()
    REBUILD_DURATION.observe(duration_ms / 1000.0)
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


def _log_unexpected_rebuild_exception(*, user_ref: str, exc: Exception) -> None:
    """Emit a sentinel alert log for unexpected rebuild failures."""
    logger.critical(
        "graph_rebuild_unexpected_exception",
        extra={
            "event": "graph_rebuild_unexpected_exception",
            "user_ref": user_ref,
            "path": _REBUILD_PATH,
            "exception_type": type(exc).__name__,
            "timestamp": _audit_timestamp(),
        },
    )


def _unwrap_rebuild_error(exc: Exception) -> Exception:
    """Return the underlying rebuild error for mapping and audit categorization."""
    if isinstance(exc, _RebuildExecutionError):
        return exc.cause
    return exc


async def shutdown_rebuild_executor() -> None:
    """Shut down the process-local graph rebuild executor.

    Uses asyncio.to_thread to avoid blocking the event loop during
    ThreadPoolExecutor.shutdown(wait=True).
    """
    await asyncio.to_thread(_REBUILD_RUNTIME.shutdown_executor)


def shutdown_rebuild_executor_sync() -> None:
    """Synchronous wrapper for shutdown_rebuild_executor.

    For use in sync test cleanup and other sync contexts.
    Prefer the async version in production async contexts.
    """
    _REBUILD_RUNTIME.shutdown_executor()


def init_rebuild_executor() -> None:
    """Explicitly initialize the process-local graph rebuild executor."""
    _REBUILD_RUNTIME.get_executor()


def _create_job_safe(session_factory: Callable[[], Session], user_ref: str) -> str:
    """Create a rebuild job record in pending status.

    Returns:
        str: Durable rebuild job identifier.

    Raises:
        GraphPersistenceSaveError: If the job record cannot be durably created.
    """
    try:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            return repo.create_rebuild_job(requested_by=user_ref)
    except Exception as exc:
        logger.error(
            "Failed to create rebuild job record: %s",
            exc.__class__.__name__,
        )
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
        logger.error(
            "Rebuild job %s update failed: %s",
            job_id,
            exc.__class__.__name__,
        )
        raise GraphPersistenceSaveError(error_message) from exc


def _update_job_source_safe(session_factory: Callable[[], Session], job_id: str, source: str) -> None:
    """Update rebuild job source.

    Raises:
        GraphPersistenceSaveError: If the source update cannot be durably persisted.
    """
    _run_job_update(
        session_factory,
        job_id,
        lambda repo: repo.update_rebuild_job_source(job_id, source),
        "Failed to update rebuild job source.",
    )


def _mark_job_running_safe(session_factory: Callable[[], Session], job_id: str) -> None:
    """Mark rebuild job as running.

    Raises:
        GraphPersistenceSaveError: If the running transition cannot be durably persisted.
    """
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
    """Mark rebuild job as succeeded.

    Raises:
        GraphPersistenceSaveError: If success metadata cannot be durably persisted.
    """
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
    exc: Exception,
    duration_ms: int,
) -> None:
    """Mark a rebuild job as failed.

    Raises:
        GraphPersistenceSaveError: If failed-state metadata cannot be durably persisted.
    """
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
    """Create a rebuild job record and transition it to running.

    Args:
        session_factory: Session factory for persistence operations.
        user_ref: Operator username recorded on the job record.
        worker_id: Worker/instance identifier (must match distributed lock holder_id).

    Returns:
        tuple[str, float]: (job_id, job_started_at monotonic timestamp).

    Raises:
        GraphPersistenceSaveError: If job creation or running transition fails.
    """
    job_id = _create_job_safe(session_factory, user_ref)
    # Reflect persisted status immediately after job creation; if transition to
    # running fails the durable job remains pending.
    update_rebuild_state_metric("pending")
    job_started_at = perf_counter()
    _mark_job_running_safe(session_factory, job_id)
    update_rebuild_state_metric("running")

    # Record initial heartbeat to establish ownership and enable liveness tracking
    # This must be called after transitioning to RUNNING so recovery logic can
    # distinguish real rebuilds from missing instrumentation
    #
    # CRITICAL: If heartbeat write fails, we must fail closed. Proceeding without
    # reliable owner/liveness data allows unsafe recovery (healthy rebuild could
    # be classified as orphaned and reset by another worker).
    try:
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            # worker_id MUST match the lock holder_id to ensure RecoveryGate
            # owner mismatch detection works correctly (see recovery_gate.py:119)
            repo.update_rebuild_heartbeat(job_id, worker_id)
    except Exception as exc:
        logger.error(
            "Failed to record initial rebuild heartbeat: %s (job_id=%s, worker_id=%s). "
            "Failing closed to prevent unsafe recovery.",
            type(exc).__name__,
            job_id,
            worker_id,
        )
        # Mark job as failed since we cannot track its liveness
        _finalize_rebuild_failure(
            session_factory=session_factory,
            job_id=job_id,
            exc=exc,
            job_started_at=job_started_at,
        )
        # Raise to abort rebuild execution
        raise GraphPersistenceSaveError(
            f"Cannot track rebuild liveness: initial heartbeat failed ({type(exc).__name__})"
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
    interval_seconds: int,
) -> None:
    """
    Background thread that periodically refreshes both the distributed lock and rebuild heartbeat.

    Prevents lock expiry and stale heartbeat detection during long-running rebuilds.

    Args:
        session_factory: Session factory for DB operations.
        dist_lock: Distributed lock to refresh.
        job_id: Rebuild job ID for heartbeat updates.
        worker_id: Worker/instance identifier.
        stop_event: Threading event to signal shutdown.
        lock_lost_event: Threading event to signal lock loss to main thread.
        interval_seconds: Refresh interval in seconds.
    """
    while not stop_event.wait(timeout=interval_seconds):
        try:
            # Refresh the distributed lock TTL
            if not dist_lock.refresh():
                logger.error(
                    "Heartbeat keeper lost distributed lock for job %s (worker %s). " "Signaling main thread to abort.",
                    job_id,
                    worker_id,
                )
                lock_lost_event.set()  # Signal lock loss to main thread
                return

            # Update rebuild job heartbeat
            with session_scope(session_factory) as session:
                repo = AssetGraphRepository(session)
                repo.update_rebuild_heartbeat(job_id, worker_id)

            logger.debug(
                "Heartbeat keeper refreshed lock and heartbeat for job %s",
                job_id,
            )
        except Exception as exc:
            logger.error(
                "Heartbeat keeper failed for job %s (worker %s): %s. " "Signaling main thread to abort.",
                job_id,
                worker_id,
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
    """Build the rebuild response payload and persist success job state.

    Args:
        session_factory: Session factory used to persist job transitions.
        job_id: Durable rebuild job identifier.
        graph: Rebuilt graph instance used to derive response counts.
        source: Rebuild source marker included in the response.
        job_started_at: Monotonic start time used for duration calculation.

    Returns:
        GraphRebuildResponse: The rebuild outcome response.

    Raises:
        GraphPersistenceSaveError: If success metadata cannot be durably persisted.
    """
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
    exc: Exception,
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
        logger.exception("Failed to restore persisted graph snapshot after rebuild persistence failure")


def _handle_rebuild_failure(
    session_factory,
    job_id: str,
    exc: Exception,
    job_started_at: float,
    success_persisted: bool,
    graph_saved: bool,
    graph_snapshot: AssetRelationshipGraph | None,
    resolved_url: str,
    source: GraphRebuildSource | None,
) -> None:
    """Handle rebuild failure with rollback and persistence."""
    if not success_persisted:
        if graph_saved:
            if graph_snapshot is not None:
                _restore_persisted_graph_snapshot(resolved_url, graph_snapshot)
            else:
                logger.warning("Skipped graph rollback because no snapshot was available")
        _finalize_rebuild_failure(
            session_factory=session_factory,
            job_id=job_id,
            exc=exc,
            job_started_at=job_started_at,
        )
    # Re-wrap if source context exists, otherwise re-raise original
    if source is not None:
        raise _RebuildExecutionError(source, exc) from exc
    raise


def _perform_rebuild_and_persist_sync(
    settings: GraphLifecycleSettings,
    *,
    user_ref: str,
) -> GraphRebuildResponse:
    """Rebuild the graph, persist it, then publish it to runtime state."""
    resolved_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
    engine = create_engine_from_url(resolved_url)

    # Initialize variables outside try to prevent UnboundLocalError in finally
    lock_acquired = False
    dist_lock = None
    stop_heartbeat = None
    heartbeat_thread = None

    try:
        session_factory = create_session_factory(engine)

        lock_ttl = getattr(settings, "rebuild_lock_ttl_seconds", 300)
        if not isinstance(lock_ttl, int) or lock_ttl <= 0:
            lock_ttl = 300

        dist_lock = DistributedLock(
            session_factory,
            "graph_rebuild",
            ttl_seconds=lock_ttl,
        )

        if not dist_lock.acquire():
            raise _DistributedLockAcquisitionError("Could not acquire distributed rebuild lock.")

        lock_acquired = True

        gate = RecoveryGate(
            session_factory=session_factory,
            lock=dist_lock,
            increment_recovery_trigger=increment_recovery_trigger,
            runtime_has_active_executor=False,
            lock_ttl_seconds=lock_ttl,
        )

        # Stage 5C.2: CRITICAL recovery gate enforcement point
        # Blocks execution if state is unsafe (UNKNOWN/LOST lock, unresolved recovery state)
        # or performs RESET recovery if needed before allowing rebuild to proceed
        gate.ensure_safe_to_execute()

        job_id, job_started_at = _create_and_start_rebuild_job(session_factory, user_ref, dist_lock.holder_id)

        # Start background heartbeat keeper thread to prevent lock expiry
        # and stale heartbeat detection during long rebuilds
        stop_heartbeat = threading.Event()
        lock_lost = threading.Event()  # Signaled if heartbeat keeper loses lock
        heartbeat_interval = max(1, lock_ttl // 3)  # Refresh at 1/3 TTL, at least 1s
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

        source: GraphRebuildSource | None = None
        success_persisted = False
        graph_snapshot: AssetRelationshipGraph | None = None
        graph_saved = False
        try:
            # Check if heartbeat keeper lost lock before expensive operations
            if lock_lost.is_set():
                raise _DistributedLockLostError("Lost distributed lock at stage=initialization")

            graph, source = build_rebuild_graph(settings)
            _update_job_source_safe(session_factory, job_id, str(source))

            # Check lock status before persisting
            if lock_lost.is_set():
                raise _DistributedLockLostError("Lost distributed lock at stage=pre-persistence")

            # Load rollback snapshot before any durable write. If snapshot loading
            # fails, the rebuild fails closed before persistence is modified.
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

            # Final lock check before success persistence
            if lock_lost.is_set():
                graph_saved = False  # Prevent unsafe rollback without lock
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
        except Exception as exc:
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

    finally:
        # Stop heartbeat keeper thread
        if stop_heartbeat is not None:
            stop_heartbeat.set()
        if heartbeat_thread is not None and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=2.0)

        if lock_acquired and dist_lock:
            dist_lock.release()
        engine.dispose()


def _sanitize_failure_message(exc: Exception) -> str:
    """Return a bounded, sanitized failure message for job persistence.

    For known safe domain exceptions the message text is retained.
    For unknown exceptions only the class name is stored to avoid
    leaking secrets, connection strings, or credentials.
    URL-like patterns are redacted as an additional safety layer.
    """
    root_exc = _unwrap_rebuild_error(exc)
    if isinstance(
        root_exc,
        (
            GraphPersistenceNotConfiguredError,
            GraphPersistenceNonDurableError,
            GraphRebuildSourceError,
            GraphPersistenceSaveError,
            ExecutionBlockedError,
        ),
    ):
        # Known safe domain exceptions — message is intentionally bounded
        message = str(root_exc) if str(root_exc) else root_exc.__class__.__name__
    else:
        # Unknown exception — use only class name to prevent secret leakage
        message = root_exc.__class__.__name__
    # Redact any URL-like patterns as a defence-in-depth measure
    message = _URL_PATTERN.sub("[REDACTED_URL]", message)
    return message[:512]


@contextmanager
def _rebuild_persistence_session() -> Generator[Session, None, None]:
    settings = get_graph_lifecycle_settings()

    engine = None

    try:
        persistence_url = resolve_durable_graph_persistence_url(
            settings.asset_graph_database_url,
        )
        engine = create_engine_from_url(persistence_url)
        session_factory = create_session_factory(engine)

        with session_scope(session_factory) as session:
            yield session

    except HTTPException:
        raise

    except (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database not configured",
        ) from exc

    except Exception as exc:
        logger.error(
            "Rebuild persistence operation failed: %s",
            exc.__class__.__name__,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database unavailable",
        ) from exc

    finally:
        if engine is not None:
            engine.dispose()


def _orm_to_response(job_orm: RebuildJobORM) -> RebuildJobResponse:
    """Convert RebuildJobORM to bounded RebuildJobResponse.

    Args:
        job_orm: The RebuildJobORM instance.

    Returns:
        RebuildJobResponse with sanitized bounded fields.
    """
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
    """Get rebuild job status by job ID.

    Operator-authenticated read-only endpoint returning bounded sanitized
    rebuild job state.

    Args:
        job_id: The rebuild job identifier.
        current_user: Authenticated operator user.

    Returns:
        RebuildJobResponse with bounded job state.

    Raises:
        HTTPException:
            404 if the rebuild job does not exist.
            503 if rebuild-job persistence is unavailable or not configured.
    """
    with _rebuild_persistence_session() as session:
        repo = AssetGraphRepository(session)
        job_orm = repo.get_rebuild_job(job_id)
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
    """List rebuild jobs ordered newest-first.

    Operator-authenticated read-only endpoint returning bounded sanitized
    rebuild job summaries in deterministic newest-first order.

    Args:
        current_user: Authenticated operator user.

    Returns:
        RebuildJobListResponse with up to _MAX_REBUILD_JOB_LIST_RESULTS newest jobs.

    Raises:
        HTTPException: 503 if persistence not configured.
    """
    with _rebuild_persistence_session() as session:
        repo = AssetGraphRepository(session)
        jobs_orm = repo.list_rebuild_jobs(limit=_MAX_REBUILD_JOB_LIST_RESULTS)
        jobs = [_orm_to_response(job_orm) for job_orm in jobs_orm]
        return RebuildJobListResponse(jobs=jobs, count=len(jobs))

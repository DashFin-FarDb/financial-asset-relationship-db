"""Operator routes for graph administration."""

from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from time import perf_counter
from typing import Annotated, NoReturn, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import RebuildJobORM, RebuildJobStatus
from src.data.distributed_lock import DistributedLock, LockLifecycleState, LockState
from src.data.repository import AssetGraphRepository, session_scope
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

from ..api_models import GraphRebuildResponse, RebuildJobListResponse, RebuildJobResponse
from ..auth import User, get_current_rebuild_operator_user
from ..graph_lifecycle import (
    GraphRuntimeLifecycleState,
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
    increment_recovery_trigger,
)
from .graph_admin_helpers import (
    _REBUILD_PATH,
    _REBUILD_RUNTIME,
    _claim_rebuild_or_raise,
    _create_and_start_rebuild_job,
    _DistributedLockAcquisitionError,
    _DistributedLockLostError,
    _duration_ms,
    _finalize_rebuild_failure,
    _finalize_rebuild_success,
    _log_rebuild_failed,
    _log_rebuild_rejected,
    _log_rebuild_requested,
    _log_rebuild_succeeded,
    _log_unexpected_rebuild_exception,
    _map_rebuild_error,
    _rebuild_status_code,
    _RebuildExecutionError,
    _resolve_user_ref,
    _sanitize_failure_message,
    _unwrap_rebuild_error,
    _update_job_source_safe,
)

# Re-exported explicitly for intra-package routing.
# TODO: Exported solely for test convenience (monkeypatching). Move these symbols to a dedicated tests.helpers module and import them via fully-qualified test paths to avoid expanding the module's public API.
__all__ = [
    "GraphRuntimeLifecycleState",
    "get_runtime_lifecycle_state",
    "synchronize_runtime_graph",
    "_REBUILD_PATH",
    "_REBUILD_RUNTIME",
    "_claim_rebuild_or_raise",
    "_create_and_start_rebuild_job",
    "_DistributedLockAcquisitionError",
    "_DistributedLockLostError",
    "_duration_ms",
    "_finalize_rebuild_failure",
    "_finalize_rebuild_success",
    "_log_rebuild_failed",
    "_log_rebuild_rejected",
    "_log_rebuild_requested",
    "_log_rebuild_succeeded",
    "_log_unexpected_rebuild_exception",
    "_map_rebuild_error",
    "_rebuild_status_code",
    "_RebuildExecutionError",
    "_resolve_user_ref",
    "_sanitize_failure_message",
    "_unwrap_rebuild_error",
    "_update_job_source_safe",
]

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_REBUILD_JOB_LIST_RESULTS = 100


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


def shutdown_rebuild_executor_sync() -> None:
    """Shut down the rebuild executor synchronously."""
    _REBUILD_RUNTIME.shutdown_executor()


def init_rebuild_executor(_settings: GraphLifecycleSettings | None = None) -> None:
    """Explicitly initialize the process-local rebuild executor."""
    _REBUILD_RUNTIME.get_executor()


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
    exc: Exception,
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
    #
    # ------------------------------------------------------------------
    # Pre-allocation Safety & Guard checks
    # ------------------------------------------------------------------
    #

    # Use coordination DB if configured; otherwise fall back to asset_graph_database_url.
    # Note: this creates a separate Engine instance for coordination even if the DSN equals the domain DB.
    coordination_database_url = settings.coordination_database_url or settings.asset_graph_database_url

    if not coordination_database_url:
        raise RuntimeError(
            "Neither coordination_database_url nor asset_graph_database_url is configured. "
            "At least one durable database URL must be configured for rebuild coordination."
        )

    domain_engine: Engine | None = None
    coordination_engine: Engine | None = None
    dist_lock: DistributedLock | None = None
    lock_acquired = False

    try:
        #
        # --------------------------------------------------------------
        # Resolve DB URLs & Initialize isolated engines
        # --------------------------------------------------------------
        #

        resolved_domain_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
        domain_engine = create_engine_from_url(
            resolved_domain_url,
        )

        resolved_coordination_url = resolve_durable_graph_persistence_url(coordination_database_url)
        # Normalize and compare SQLAlchemy URLs to robustly detect identical database targets
        try:
            same_db = make_url(resolved_coordination_url) == make_url(resolved_domain_url)
        except Exception:
            # Fall back to string comparison if URL parsing fails for any reason
            same_db = resolved_coordination_url == resolved_domain_url

        if same_db:
            coordination_engine = domain_engine
        else:
            coordination_engine = create_engine_from_url(
                resolved_coordination_url,
            )

        #
        # --------------------------------------------------------------
        # Create isolated session factories
        # --------------------------------------------------------------
        #

        domain_session_factory = create_session_factory(domain_engine)
        # Reuse the domain session factory when both targets resolve to the same engine to avoid
        # creating a duplicate engine/pool. If the coordination engine is a separate engine instance
        # (different URL), create an isolated coordination session factory.
        coordination_session_factory = (
            domain_session_factory
            if coordination_engine is domain_engine
            else create_session_factory(coordination_engine)
        )

        #
        # --------------------------------------------------------------
        # Validate coordination authority
        # --------------------------------------------------------------
        #
        # Coordination plane MUST point to authoritative primary.
        #

        _validate_coordination_database_primary(coordination_session_factory)

        #
        # --------------------------------------------------------------
        # Create distributed coordination lock
        # --------------------------------------------------------------
        #

        lock_ttl = settings.rebuild_lock_ttl_seconds

        dist_lock = DistributedLock(
            coordination_session_factory=coordination_session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=lock_ttl,
        )

        lease = dist_lock.acquire()

        if not lease:
            raise _DistributedLockAcquisitionError("Could not acquire distributed rebuild lock.")

        lock_acquired = True

        #
        # --------------------------------------------------------------
        # Validate coordination state
        # --------------------------------------------------------------
        #

        lock_state = dist_lock.check_state()

        if lock_state == LockState.LOST:
            raise RuntimeError("Coordination state lost immediately after acquisition.")

        if lock_state != LockState.VALID:
            raise RuntimeError(f"Unexpected coordination state after acquisition: {lock_state}")

        #
        # --------------------------------------------------------------
        # Recovery safety gate
        # --------------------------------------------------------------
        #

        RecoveryGate(
            session_factory=domain_session_factory,
            lock=dist_lock,
            increment_recovery_trigger=increment_recovery_trigger,
            runtime_has_active_executor=False,
            lock_ttl_seconds=lock_ttl,
        ).ensure_safe_to_execute()

        #
        # --------------------------------------------------------------
        # Create rebuild job
        # --------------------------------------------------------------
        #

        job_id, job_started_at = _create_and_start_rebuild_job(
            domain_session_factory,
            user_ref,
            dist_lock.holder_id,
        )

        #
        # --------------------------------------------------------------
        # Heartbeat orchestration
        # --------------------------------------------------------------
        #

        with _orchestrate_heartbeat(
            domain_session_factory,
            dist_lock,
            job_id,
            lock_ttl,
        ) as lock_lost:

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
        # --------------------------------------------------------------
        # Best-effort lock release
        # --------------------------------------------------------------
        #
        if dist_lock is not None and lock_acquired and dist_lock.state != LockLifecycleState.LOST:
            try:
                dist_lock.release()
            except Exception:
                logger.exception("Failed to release distributed rebuild lock")

        #
        # --------------------------------------------------------------
        # Dispose coordination engine
        # --------------------------------------------------------------
        #
        # fmt: off
        if (
            coordination_engine is not None
            and coordination_engine is not domain_engine
        ):
            # fmt: on
            try:
                coordination_engine.dispose()
            except Exception:
                logger.exception("Failed to dispose coordination database engine")

        #
        # --------------------------------------------------------------
        # Dispose domain engine
        # --------------------------------------------------------------
        #
        if domain_engine is not None:
            try:
                domain_engine.dispose()
            except Exception:
                logger.exception("Failed to dispose domain database engine")


def _validate_coordination_database_primary(session_factory: Callable[[], Session]) -> None:
    """Verify the coordination DB is a writable primary, not a replica.

    For PostgreSQL this uses pg_is_in_recovery(); for non-Postgres backends (e.g. SQLite)
    the check is a no-op because replica detection isn't applicable.
    """
    try:
        with session_scope(session_factory) as session:
            bind = session.get_bind()
            dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
            # Only run pg_is_in_recovery on PostgreSQL; other backends don't have replicas
            if dialect_name != "postgresql":
                return
            result = session.execute(text("SELECT pg_is_in_recovery()")).scalar()
            if result:
                raise RuntimeError(
                    "Coordination database is a read replica; coordination_database_url must point to the primary."
                )
    except RuntimeError:
        # Re-raise explicit replica/role check failures directly
        raise
    except (SQLAlchemyError, OSError) as exc:
        logger.error("Error while verifying coordination database role: %s", type(exc).__name__)
        logger.debug("Full exception while verifying coordination database role", exc_info=True)
        # Fail closed: if we cannot determine DB role, prevent proceeding
        raise RuntimeError("Could not verify coordination database role") from exc
    except Exception as exc:
        # Unexpected error during session cleanup (rollback/close). Log and raise a consistent RuntimeError.
        logger.error("Unexpected error while verifying coordination database role: %s", type(exc).__name__)
        logger.debug("Full exception while verifying coordination database role", exc_info=True)
        raise RuntimeError("Could not verify coordination database role") from exc


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


def _safe_parse_status(raw_status: str) -> RebuildJobStatus:
    """Safely parse database status to Enum, falling back to failed on corruption."""
    try:
        return RebuildJobStatus(raw_status)
    except ValueError:
        # Crucial to log as error so that alerting systems capture database status corruption.
        logger.error("Corrupted status in DB: %s, falling back to failed", raw_status)
        return RebuildJobStatus.FAILED


def _orm_to_response(job_orm: RebuildJobORM) -> RebuildJobResponse:
    """Convert RebuildJobORM to bounded RebuildJobResponse."""
    return RebuildJobResponse(
        job_id=job_orm.job_id,
        status=_safe_parse_status(job_orm.status),
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

"""FastAPI application factory for the Financial Asset Relationship Database API.

This module contains the FastAPI application construction, middleware setup,
and router registration logic.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from .graph_lifecycle_providers import GraphLifecycleSettings

# pylint: disable=import-error
from slowapi import _rate_limit_exceeded_handler  # type: ignore[import-not-found]
from slowapi.errors import RateLimitExceeded  # type: ignore[import-not-found]

from .cors_policy import configure_cors
from .graph_lifecycle import (
    GraphRuntimeLifecycleState,
    begin_shutdown,
    get_graph,
    get_runtime_lifecycle_state,
    sync_with_latest_rebuild,
)
from .rate_limit import limiter
from .routers.assets import router as assets_router
from .routers.auth import router as auth_router
from .routers.graph_admin import init_rebuild_executor, shutdown_rebuild_executor
from .routers.graph_admin import router as graph_admin_router
from .routers.relationships import router as relationships_router
from .routers.system import router as system_router
from .routers.visualization import router as visualization_router

# pylint: enable=import-error


logger = logging.getLogger(__name__)

# Startup reconciliation uses a fixed TTL. GraphLifecycleSettings does not carry
# a configurable lock TTL, so using a named constant makes the intentional choice
# explicit rather than hiding it behind a getattr fallback.
_STARTUP_LOCK_TTL_SECONDS = 300


def _run_startup_reconciliation(settings: GraphLifecycleSettings) -> None:
    """
    Run recovery gate validation before executor initialization.

    Stage 5C.2: Startup reconciliation hook ensures no rebuild execution
    can begin without passing recovery gate validation.

    Applies schema migrations before running the gate so that ORM queries
    succeed on fresh installs and legacy databases that pre-date the heartbeat
    columns.  Without this ordering, the gate's SELECT against the ``rebuild_jobs``
    table would raise an ``OperationalError`` (table or column missing) and be
    classified as UNSAFE, permanently blocking startup.

    Blocks startup if:
    - Lock state is LOST (DB connectivity failure)
    - Recovery gate returns UNSAFE (unresolvable inconsistency)

    Allows startup after:
    - Successful RESET recovery (orphaned job cleaned up)
    - RESUME decision (consistent state, lock held)
    - WAIT decision with no active job (clean install / lock not yet acquired;
      the executor will acquire the lock before any rebuild)

    The lock TTL used here is the module-level ``_STARTUP_LOCK_TTL_SECONDS``
    constant (300 s).  ``GraphLifecycleSettings`` does not carry a configurable
    lock TTL, so a fixed value is used intentionally rather than a ``getattr``
    that would silently always fall through to the same default.

    If RESET recovery reacquires the lock, it is released before this function
    returns so that subsequent rebuild requests are not blocked until TTL expiry.

    Args:
        settings: Graph lifecycle settings containing persistence configuration.

    Raises:
        ExecutionBlockedError: If recovery gate blocks execution.
        Exception: If recovery gate evaluation fails.
    """
    from src.data.database import create_engine_from_url, create_session_factory, init_db
    from src.data.distributed_lock import DistributedLock, LockState
    from src.logic.recovery_gate import ExecutionBlockedError, RecoveryGate

    from .graph_lifecycle_providers import resolve_durable_graph_persistence_url
    from .metrics import increment_recovery_trigger

    persistence_url = resolve_durable_graph_persistence_url(
        settings.asset_graph_database_url
    )
    engine = create_engine_from_url(persistence_url)
    lock = None
    
    try:
        # Apply schema migrations BEFORE running the gate so ORM queries succeed on
        # fresh installs and legacy databases lacking the heartbeat columns.
        init_db(engine)
    
        session_factory = create_session_factory(engine)
        lock = DistributedLock(
            session_factory=session_factory,
            lock_name="graph_rebuild",
            ttl_seconds=_STARTUP_LOCK_TTL_SECONDS,
        )
    
        gate = RecoveryGate(
            session_factory=session_factory,
            lock=lock,
            increment_recovery_trigger=increment_recovery_trigger,
            runtime_has_active_executor=False,  # No executor yet at startup
            lock_ttl_seconds=_STARTUP_LOCK_TTL_SECONDS,
        )
    
        # Evaluate state and act based on startup semantics:
        # - RESUME: consistent state, proceed.
        # - RESET: perform recovery then re-evaluate via ensure_safe_to_execute().
        # - WAIT: at startup, WAIT always means "no inconsistency but lock not yet acquired"
        #   (clean install or previous lock expired naturally). The executor will
        #   acquire the lock before any rebuild, so this is safe to allow.
        # - UNSAFE: block startup.
        try:
            gate.ensure_safe_to_execute()
        except ExecutionBlockedError as exc:
            if exc.action == "wait" and exc.inconsistency_type == "none":
                # WAIT with no detected inconsistency means the system state is clean
                # but this process has not yet acquired the distributed lock.
                logger.info(
                    "Startup reconciliation allowing WAIT state; "
                    "executor will acquire lock before rebuild"
                )
            else:
                raise
    
        logger.info("Startup reconciliation passed - executor initialization allowed")
    
    finally:
        # Release the lock if RESET recovery acquired it.
        if lock is not None:
            try:
                lock.release()
                logger.debug("Released startup reconciliation lock after recovery")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "Failed startup reconciliation lock release for %s: %s",
                    lock.lock_name,
                    type(exc).__name__,
                )
    
        try:
            engine.dispose()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(
                "Failed during startup reconciliation cleanup: %s",
                type(exc).__name__,
            )


@asynccontextmanager
async def lifespan(_fastapi_app: FastAPI):
    """Initialize graph state and clean up rebuild resources."""
    try:
        from src.data.database import create_engine_from_url, create_session_factory  # noqa: C0415
        from src.logic.recovery_gate import ExecutionBlockedError  # noqa: C0415

        from .graph_lifecycle_providers import (  # noqa: C0415 - avoid circular import
            get_graph_lifecycle_settings,
            resolve_durable_graph_persistence_url,
        )
        from .metrics import initialize_rebuild_state_metric_from_db  # noqa: C0415

        settings = get_graph_lifecycle_settings()
        has_durable_graph_persistence = bool(settings.asset_graph_database_url)

        get_graph()

        # Stage 5C.2: Run recovery gate before executor initialization
        # Block startup on explicit recovery-gate safety blocks; only unexpected
        # reconciliation failures are downgraded to bounded warnings.
        if has_durable_graph_persistence:
            try:
                await asyncio.to_thread(_run_startup_reconciliation, settings)
            except ExecutionBlockedError:
                raise
            except Exception as exc:
                # Log only the exception type to prevent DSN/credential leakage
                # from SQLAlchemy exception messages (per repo convention).
                logger.warning(
                    "Startup reconciliation failed; continuing startup: %s",
                    type(exc).__name__,
                )

        # Only initialize executor after startup reconciliation has been attempted
        init_rebuild_executor()

        if has_durable_graph_persistence:
            try:
                await asyncio.to_thread(sync_with_latest_rebuild)
            except Exception as exc:  # noqa: BLE001 - bounded logging below
                logger.warning(
                    "Startup graph reconciliation failed: %s",
                    type(exc).__name__,
                )

            # Initialize rebuild state metric from DB after graph reconciliation.
            # init_db has already run inside _run_startup_reconciliation above, so
            # the schema is guaranteed to be up-to-date at this point.
            try:
                persistence_url = resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
                engine = create_engine_from_url(persistence_url)
                try:
                    session_factory = create_session_factory(engine)
                    await asyncio.to_thread(initialize_rebuild_state_metric_from_db, session_factory)
                finally:
                    # Dispose engine after metric initialization to prevent connection leak
                    engine.dispose()
            except Exception as exc:  # noqa: BLE001 - bounded logging below
                logger.warning(
                    "Failed to initialize rebuild state metric: %s",
                    type(exc).__name__,
                )
                # Set metric to unknown state instead of default 0 (none) to avoid
                # misleading healthy state when persistence is unavailable/misconfigured
                from api.metrics import REBUILD_STATE_STATUS  # noqa: C0415

                REBUILD_STATE_STATUS.set(-1)  # -1 = unknown

        logger.info("Application startup complete - graph and rebuild executor initialized")
    except Exception:
        logger.exception("Failed to initialize graph during startup")
        raise

    # Start background synchronization task
    sync_task = asyncio.create_task(_run_graph_sync_loop())

    yield

    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        # Expected during shutdown after sync_task.cancel(); suppress intentionally.
        pass
    finally:
        begin_shutdown()
        await shutdown_rebuild_executor()
        logger.info("Application shutdown")


async def _run_graph_sync_loop(interval_seconds: int = 60) -> None:
    """Run the graph synchronization loop in the background."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            if get_runtime_lifecycle_state() in (
                GraphRuntimeLifecycleState.SHUTTING_DOWN,
                GraphRuntimeLifecycleState.STOPPED,
            ):
                return
            await asyncio.to_thread(sync_with_latest_rebuild)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - bounded logging below
            logger.warning(
                "Unexpected error in graph synchronization loop: %s",
                type(exc).__name__,
            )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Initialise FastAPI app with lifespan handler
    app = FastAPI(
        title="Financial Asset Relationship API",
        description="REST API for Financial Asset Relationship Database",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Configure CORS via extracted policy
    configure_cors(app)

    app.include_router(auth_router)
    app.include_router(system_router)
    app.include_router(graph_admin_router)
    app.include_router(assets_router)
    app.include_router(relationships_router)
    app.include_router(visualization_router)

    return app


# Create the application instance
app = create_app()

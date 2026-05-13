"""Graph lifecycle management for the Financial Asset Relationship API.

This module provides thread-safe initialization and management of the global
AssetRelationshipGraph instance used by the API.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from enum import Enum
from typing import Final

from src.logic.asset_graph import AssetRelationshipGraph

from . import graph_lifecycle_providers
from .api_models import AssetGraphSource

logger = logging.getLogger(__name__)

# Global graph instance with thread-safe initialization and configurable
# factory.


class GraphRuntimeLifecycleState(str, Enum):  # noqa: UP042 - StrEnum requires Python 3.11+
    """Explicit hosted graph runtime lifecycle states."""

    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    REBUILDING = "REBUILDING"
    FAILED = "FAILED"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    STOPPED = "STOPPED"


_VALID_LIFECYCLE_TRANSITIONS: dict[GraphRuntimeLifecycleState, frozenset[GraphRuntimeLifecycleState]] = {
    GraphRuntimeLifecycleState.UNINITIALIZED: frozenset(
        {
            GraphRuntimeLifecycleState.INITIALIZING,
            GraphRuntimeLifecycleState.REBUILDING,
            GraphRuntimeLifecycleState.SHUTTING_DOWN,
        }
    ),
    GraphRuntimeLifecycleState.INITIALIZING: frozenset(
        {
            GraphRuntimeLifecycleState.READY,
            GraphRuntimeLifecycleState.FAILED,
            GraphRuntimeLifecycleState.SHUTTING_DOWN,
        }
    ),
    GraphRuntimeLifecycleState.READY: frozenset(
        {
            GraphRuntimeLifecycleState.REBUILDING,
            GraphRuntimeLifecycleState.SHUTTING_DOWN,
        }
    ),
    GraphRuntimeLifecycleState.REBUILDING: frozenset(
        {
            GraphRuntimeLifecycleState.READY,
            GraphRuntimeLifecycleState.FAILED,
            GraphRuntimeLifecycleState.SHUTTING_DOWN,
        }
    ),
    GraphRuntimeLifecycleState.FAILED: frozenset(
        {
            GraphRuntimeLifecycleState.INITIALIZING,
            GraphRuntimeLifecycleState.REBUILDING,
            GraphRuntimeLifecycleState.SHUTTING_DOWN,
        }
    ),
    # SHUTTING_DOWN progresses to STOPPED (normal shutdown) only.
    GraphRuntimeLifecycleState.SHUTTING_DOWN: frozenset({GraphRuntimeLifecycleState.STOPPED}),
    # STOPPED is terminal for the normal production lifecycle.
    # The only permitted outgoing transition is an explicit reset to UNINITIALIZED,
    # which is reserved for test isolation and administrative restart paths.
    GraphRuntimeLifecycleState.STOPPED: frozenset({GraphRuntimeLifecycleState.UNINITIALIZED}),
}


def _transition_lifecycle_state(next_state: GraphRuntimeLifecycleState) -> None:
    """Transition runtime lifecycle state while graph_lock is held."""
    current_state = graph_state.lifecycle_state
    if current_state == next_state:
        return

    if next_state not in _VALID_LIFECYCLE_TRANSITIONS[current_state]:
        raise RuntimeError(f"Invalid graph runtime lifecycle transition: {current_state.value} -> {next_state.value}")

    graph_state.lifecycle_state = next_state


def _normalize_shutdown_state() -> None:
    """Complete any in-progress shutdown sequence by advancing to UNINITIALIZED.

    SHUTTING_DOWN progresses to STOPPED, then STOPPED progresses to UNINITIALIZED,
    following the validated transition matrix. Used internally by restart/reset paths.
    Must be called while holding graph_lock.
    """
    if graph_state.lifecycle_state == GraphRuntimeLifecycleState.SHUTTING_DOWN:
        _transition_lifecycle_state(GraphRuntimeLifecycleState.STOPPED)
    if graph_state.lifecycle_state == GraphRuntimeLifecycleState.STOPPED:
        _transition_lifecycle_state(GraphRuntimeLifecycleState.UNINITIALIZED)


def _shutdown_to_uninitialized() -> None:
    """Return lifecycle to UNINITIALIZED from any non-UNINITIALIZED state.

    States already in the shutdown sequence (SHUTTING_DOWN, STOPPED) skip the
    initial transition to SHUTTING_DOWN and resume from their current position.
    Reserved for administrative reset and test isolation; must be called while
    holding graph_lock.
    """
    if graph_state.lifecycle_state == GraphRuntimeLifecycleState.UNINITIALIZED:
        return
    if graph_state.lifecycle_state not in (
        GraphRuntimeLifecycleState.SHUTTING_DOWN,
        GraphRuntimeLifecycleState.STOPPED,
    ):
        _transition_lifecycle_state(GraphRuntimeLifecycleState.SHUTTING_DOWN)
    _normalize_shutdown_state()


def get_runtime_lifecycle_state() -> GraphRuntimeLifecycleState:
    """Return the current hosted graph runtime lifecycle state via graph_lock."""
    with graph_lock:
        return graph_state.lifecycle_state


def transition_runtime_lifecycle_state(next_state: GraphRuntimeLifecycleState) -> None:
    """Transition runtime lifecycle to the provided state with validation."""
    with graph_lock:
        _transition_lifecycle_state(next_state)


class _GraphState:
    """Mutable container for module graph lifecycle state."""

    def __init__(self) -> None:
        """Create empty graph lifecycle state."""
        self.graph: AssetRelationshipGraph | None = None
        self.graph_factory: Callable[[], AssetRelationshipGraph] | None = None
        self.startup_source: GraphStartupSource | None = None
        self.lifecycle_state = GraphRuntimeLifecycleState.UNINITIALIZED
        self.last_synced_job_id: str | None = None


graph_state = _GraphState()
graph_lock = threading.Lock()


class _UnsetLastSyncedJobId:
    """Sentinel marker for omitted expected_last_synced_job_id."""


UNSET_LAST_SYNC: Final = _UnsetLastSyncedJobId()


def _sync_state_changed(expected_last_synced_job_id: str | None | _UnsetLastSyncedJobId) -> bool:
    """Return whether sync state has changed from the expected value."""
    if isinstance(expected_last_synced_job_id, _UnsetLastSyncedJobId):
        return False
    return graph_state.last_synced_job_id != expected_last_synced_job_id


def get_graph() -> AssetRelationshipGraph:
    """Get the module-global graph, initializing it when needed."""
    if graph_state.graph is not None:
        return graph_state.graph

    graph, _startup_source = get_graph_with_startup_source()
    return graph


def get_graph_with_startup_source() -> tuple[AssetRelationshipGraph, AssetGraphSource | None]:
    """Return the module-global graph and its tracked startup source atomically."""
    with graph_lock:
        if graph_state.graph is None:
            _normalize_shutdown_state()
            _transition_lifecycle_state(GraphRuntimeLifecycleState.INITIALIZING)
            try:
                graph, startup_source = _initialize_graph_with_source()
            except Exception:
                _transition_lifecycle_state(GraphRuntimeLifecycleState.FAILED)
                raise
            graph_state.graph = graph
            graph_state.startup_source = startup_source
            _transition_lifecycle_state(GraphRuntimeLifecycleState.READY)
            logger.info("Graph initialized successfully")

        if graph_state.graph is None:
            raise RuntimeError("Global graph initialization failed; graph is None.")

        return graph_state.graph, graph_state.startup_source


def set_graph(graph_instance: AssetRelationshipGraph) -> None:
    """Register a global graph instance returned by get_graph()."""
    with graph_lock:
        _normalize_shutdown_state()
        if graph_state.lifecycle_state in (
            GraphRuntimeLifecycleState.UNINITIALIZED,
            GraphRuntimeLifecycleState.FAILED,
        ):
            _transition_lifecycle_state(GraphRuntimeLifecycleState.INITIALIZING)
        graph_state.graph = graph_instance
        graph_state.graph_factory = None
        graph_state.startup_source = "unknown"
        _transition_lifecycle_state(GraphRuntimeLifecycleState.READY)


def synchronize_runtime_graph(
    graph_instance: AssetRelationshipGraph,
    *,
    job_id: str | None = None,
    expected_last_synced_job_id: str | None | _UnsetLastSyncedJobId = UNSET_LAST_SYNC,
) -> bool:
    """Publish a runtime graph and mirror it into legacy api.main.

    Rebuild callers publish the freshly persisted graph while lifecycle state is
    still REBUILDING. Preserve that state so complete_rebuild() remains the
    single transition point for REBUILDING -> READY/FAILED.
    """
    with graph_lock:
        if graph_state.lifecycle_state in (
            GraphRuntimeLifecycleState.SHUTTING_DOWN,
            GraphRuntimeLifecycleState.STOPPED,
        ):
            return False
        if _sync_state_changed(expected_last_synced_job_id):
            return False
        preserve_rebuild = graph_state.lifecycle_state == GraphRuntimeLifecycleState.REBUILDING
        if graph_state.lifecycle_state in (
            GraphRuntimeLifecycleState.UNINITIALIZED,
            GraphRuntimeLifecycleState.FAILED,
        ):
            _transition_lifecycle_state(GraphRuntimeLifecycleState.INITIALIZING)
        graph_state.graph = graph_instance
        graph_state.graph_factory = None
        graph_state.startup_source = "unknown"
        if job_id:
            graph_state.last_synced_job_id = job_id
        if not preserve_rebuild:
            _transition_lifecycle_state(GraphRuntimeLifecycleState.READY)

        api_main = sys.modules.get("api.main")
        if api_main is not None and hasattr(api_main, "graph"):
            setattr(api_main, "graph", graph_instance)
        return True


def _query_latest_successful_rebuild_job_id(
    settings: graph_lifecycle_providers.GraphLifecycleSettings,
) -> str | None:
    """Return the latest successful rebuild job id using durable persistence."""
    from src.data.database import create_engine_from_url, create_session_factory
    from src.data.repository import AssetGraphRepository, session_scope

    resolved_url = graph_lifecycle_providers.resolve_durable_graph_persistence_url(settings.asset_graph_database_url)
    engine = create_engine_from_url(resolved_url)
    try:
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            repo = AssetGraphRepository(session)
            latest_job = repo.get_latest_successful_rebuild_job()
            if latest_job is None:
                return None
            return latest_job.job_id
    finally:
        engine.dispose()


def set_graph_factory(
    factory: Callable[[], AssetRelationshipGraph] | None,
) -> None:
    """Configure the callable used to lazily construct the global graph."""
    with graph_lock:
        graph_state.graph_factory = factory
        graph_state.graph = None
        graph_state.startup_source = None
        _shutdown_to_uninitialized()


def reset_graph() -> None:
    """
    Reset module-level graph state so the graph will be recreated on next access.

    Clears the cached graph instance, any configured graph factory, and the
    settings cache to ensure environment variable changes are observed on the
    next initialization.
    """
    # Clear settings cache to preserve reset semantics: environment variable
    # changes made after reset should be picked up on next initialization.
    graph_lifecycle_providers.clear_graph_lifecycle_settings_cache()
    with graph_lock:
        graph_state.graph_factory = None
        graph_state.graph = None
        graph_state.startup_source = None
        _shutdown_to_uninitialized()


def begin_rebuild() -> None:
    """Transition lifecycle state to REBUILDING before rebuild execution."""
    with graph_lock:
        # Rebuild can be the first hosted lifecycle operation after process start
        # (UNINITIALIZED), or a recovery path after startup/rebuild failure (FAILED).
        # Normalize those states through INITIALIZING->READY before entering REBUILDING.
        _normalize_shutdown_state()
        if graph_state.lifecycle_state in (
            GraphRuntimeLifecycleState.UNINITIALIZED,
            GraphRuntimeLifecycleState.FAILED,
        ):
            _transition_lifecycle_state(GraphRuntimeLifecycleState.INITIALIZING)
            _transition_lifecycle_state(GraphRuntimeLifecycleState.READY)
        _transition_lifecycle_state(GraphRuntimeLifecycleState.REBUILDING)


def complete_rebuild(*, succeeded: bool) -> None:
    """Finalize lifecycle state for rebuild completion.

    Calls outside REBUILDING are ignored with a warning because shutdown or
    cancellation cleanup can race with executor callbacks; callers should still
    treat the warning as evidence of an unexpected lifecycle ordering issue.
    """
    with graph_lock:
        if graph_state.lifecycle_state != GraphRuntimeLifecycleState.REBUILDING:
            logger.warning(
                "Ignoring complete_rebuild outside REBUILDING state: %s",
                graph_state.lifecycle_state,
            )
            return
        if succeeded:
            _transition_lifecycle_state(GraphRuntimeLifecycleState.READY)
            return
        _transition_lifecycle_state(GraphRuntimeLifecycleState.FAILED)


def begin_shutdown() -> None:
    """Transition lifecycle state to SHUTTING_DOWN then STOPPED."""
    with graph_lock:
        if graph_state.lifecycle_state == GraphRuntimeLifecycleState.STOPPED:
            return
        if graph_state.lifecycle_state != GraphRuntimeLifecycleState.SHUTTING_DOWN:
            _transition_lifecycle_state(GraphRuntimeLifecycleState.SHUTTING_DOWN)
        _transition_lifecycle_state(GraphRuntimeLifecycleState.STOPPED)


def _initialize_graph() -> AssetRelationshipGraph:
    """Initialize and return a graph without mutating lifecycle state."""
    graph, _startup_source = _initialize_graph_with_source()
    return graph


def _initialize_graph_with_source() -> tuple[AssetRelationshipGraph, AssetGraphSource]:
    """
    Initialize a graph and return the selected startup source.

    Precedence:
    1. custom graph factory;
    2. persisted graph when durable persistence is configured and populated;
    3. graph cache path;
    4. real-data fetcher;
    5. sample graph.

    Configured persistence failures raise RuntimeError.
    """
    if graph_state.graph_factory is not None:
        return graph_state.graph_factory(), "explicit_factory"

    settings = graph_lifecycle_providers.get_graph_lifecycle_settings()
    persisted_graph = graph_lifecycle_providers.load_persisted_graph_if_available(settings.asset_graph_database_url)
    if persisted_graph is not None:
        logger.info("Graph startup source: persisted_graph_store")

        # Initialize last_synced_job_id from DB if possible
        try:
            latest_job_id = _query_latest_successful_rebuild_job_id(settings)
            if latest_job_id:
                graph_state.last_synced_job_id = latest_job_id
        except Exception as exc:
            logger.warning(
                "Failed to initialize last_synced_job_id during graph startup " "(exception_type=%s)",
                type(exc).__name__,
            )

        return persisted_graph, "persisted_graph_store"

    cache_path = settings.graph_cache_path
    use_real_data = settings.use_real_data_fetcher

    if cache_path:
        graph = graph_lifecycle_providers.load_graph_from_cache_path(
            cache_path,
            enable_network=use_real_data,
        )
        return graph, "cache"

    if use_real_data:
        real_data_cache_path = settings.real_data_cache_path
        graph = graph_lifecycle_providers.load_graph_from_real_data_fetcher(
            real_data_cache_path,
        )
        return graph, "real_data"

    logger.info("Graph startup source: sample")
    return graph_lifecycle_providers.create_sample_graph(), "sample"


def sync_with_latest_rebuild() -> None:
    """Check database for newer successful rebuild and synchronize if found."""
    settings = graph_lifecycle_providers.get_graph_lifecycle_settings()
    if not settings.asset_graph_database_url:
        return

    # Don't sync while we're already rebuilding locally
    if get_runtime_lifecycle_state() == GraphRuntimeLifecycleState.REBUILDING:
        return
    if get_runtime_lifecycle_state() in (
        GraphRuntimeLifecycleState.SHUTTING_DOWN,
        GraphRuntimeLifecycleState.STOPPED,
    ):
        return

    try:
        from src.data.database import create_engine_from_url, create_session_factory
        from src.data.repository import AssetGraphRepository, session_scope

        latest_job_id = _query_latest_successful_rebuild_job_id(settings)
        if not latest_job_id:
            return

        with graph_lock:
            if graph_state.lifecycle_state in (
                GraphRuntimeLifecycleState.SHUTTING_DOWN,
                GraphRuntimeLifecycleState.STOPPED,
            ):
                return
            if latest_job_id == graph_state.last_synced_job_id:
                return
            expected_last_synced_job_id = graph_state.last_synced_job_id

        logger.info(
            "New successful rebuild detected (job_id: %s). Synchronizing...",
            latest_job_id,
        )

        resolved_url = graph_lifecycle_providers.resolve_durable_graph_persistence_url(
            settings.asset_graph_database_url
        )
        engine = create_engine_from_url(resolved_url)
        try:
            session_factory = create_session_factory(engine)
            with session_scope(session_factory) as session:
                repo = AssetGraphRepository(session)
                new_graph = repo.load_graph()
            from .metrics import update_graph_metrics

            if synchronize_runtime_graph(
                new_graph,
                job_id=latest_job_id,
                expected_last_synced_job_id=expected_last_synced_job_id,
            ):
                update_graph_metrics(
                    len(new_graph.assets),
                    sum(len(items) for items in new_graph.relationships.values()),
                )
        finally:
            engine.dispose()
    except Exception as exc:
        logger.warning(
            "Failed to sync with latest rebuild from database: %s",
            type(exc).__name__,
        )

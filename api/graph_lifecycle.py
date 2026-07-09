"""Graph lifecycle management for the Financial Asset Relationship API.

This module provides thread-safe initialization and management of the global
AssetRelationshipGraph instance used by the API.
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final

from src.logic.asset_graph import AssetRelationshipGraph
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

from . import graph_lifecycle_providers

UTC = timezone.utc


logger = logging.getLogger(__name__)


# Global graph instance with thread-safe initialization and configurable
# factory.


class GraphStartupSource(str, Enum):  # noqa: UP042
    """Explicit startup source origins for graph persistence lifecycle."""

    PERSISTED = "persisted"
    REAL_DATA = "real_data"
    SAMPLE_DATA = "sample_data"
    EMPTY_PERSISTENCE_FALLBACK = "empty_persistence_fallback"
    REBUILD = "rebuild"
    FAILED = "failed"
    CACHE = "cache"
    EXPLICIT_FACTORY = "explicit_factory"
    UNKNOWN = "unknown"


_PROVIDER_SOURCE_TO_STARTUP_SOURCE: Final[dict[str, GraphStartupSource]] = {
    "cache": GraphStartupSource.CACHE,
    "real_data": GraphStartupSource.REAL_DATA,
    "sample": GraphStartupSource.SAMPLE_DATA,
}


def _resolve_provider_source(raw_source: str) -> GraphStartupSource:
    """Map a provider-reported GraphRebuildSource string to a GraphStartupSource enum value.

    Handles vocabulary mismatch between the provider layer (which reports ``sample``)
    and the lifecycle enum (which uses ``sample_data``).
    """
    try:
        return _PROVIDER_SOURCE_TO_STARTUP_SOURCE[raw_source]
    except KeyError:
        return GraphStartupSource(raw_source)


@dataclass
class GraphStartupMetadata:
    """Metadata detailing the graph startup resolution."""

    source: GraphStartupSource
    persistence_enabled: bool
    persistence_loaded: bool
    persistence_saved: bool
    fallback_reason: str | None
    loaded_asset_count: int
    loaded_relationship_count: int
    startup_timestamp: datetime


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

        self.startup_metadata: GraphStartupMetadata | None = None
        self.lifecycle_state = GraphRuntimeLifecycleState.UNINITIALIZED
        self.last_synced_job_id: str | None = None

    def clear_graph_runtime_state(self) -> None:
        """Clear graph instance state that must not survive lifecycle resets."""
        self.graph = None
        self.startup_metadata = None
        self.last_synced_job_id = None


graph_state = _GraphState()
graph_lock = threading.Lock()


class _UnsetLastSyncedJobId:
    """Sentinel marker for omitted expected_last_synced_job_id."""


UNSET_LAST_SYNC: Final = _UnsetLastSyncedJobId()


def _settings_asset_graph_database_url(
    settings: graph_lifecycle_providers.GraphLifecycleSettings,
) -> str | None:
    """Return the durable graph database URL across old/new settings shapes."""
    return graph_lifecycle_providers.resolve_hosted_graph_database_url(settings)


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


def get_graph_with_startup_source() -> tuple[AssetRelationshipGraph, GraphStartupMetadata | None]:
    """
    Obtain the module-global AssetRelationshipGraph and its recorded startup source.

    This initializes the graph if necessary.

    If the global graph is uninitialized this function performs an atomic initialization under the module lock;
    on successful initialization the graph and its startup source are stored for future calls and an
    observability event is emitted.

    Returns:
        tuple[AssetRelationshipGraph, GraphStartupMetadata | None]: The active global graph and the metadata
            used to initialize it (or `None` if unknown).

    Raises:
        RuntimeError: If initialization completes but the global graph remains `None`.
        Exception: Propagates any exception raised during graph initialization.
    """
    with graph_lock:
        if graph_state.graph is None:
            _normalize_shutdown_state()
            _transition_lifecycle_state(GraphRuntimeLifecycleState.INITIALIZING)
            try:
                graph, startup_metadata = initialize_graph_runtime()
            except Exception:
                _transition_lifecycle_state(GraphRuntimeLifecycleState.FAILED)
                raise
            graph_state.graph = graph
            graph_state.startup_metadata = startup_metadata
            _transition_lifecycle_state(GraphRuntimeLifecycleState.READY)
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="graph_initialized",
                    message="Graph initialized successfully",
                    metadata={"startup_source": startup_metadata.source},
                ),
            )

        if graph_state.graph is None:
            raise RuntimeError("Global graph initialization failed; graph is None.")

        return graph_state.graph, graph_state.startup_metadata


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
        graph_state.startup_metadata = None
        graph_state.last_synced_job_id = None
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

    Returns:
        bool: True if the graph is successfully published to runtime and mirrored into legacy api.main.
        False if publishing is skipped because runtime is SHUTTING_DOWN/STOPPED or
        expected_last_synced_job_id no longer matches current sync state.
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
        graph_state.startup_metadata = None
        if job_id:
            graph_state.last_synced_job_id = job_id
        if not preserve_rebuild:
            _transition_lifecycle_state(GraphRuntimeLifecycleState.READY)

        api_main = sys.modules.get("api.main")
        if api_main is not None and hasattr(api_main, "graph"):
            api_main.graph = graph_instance  # type: ignore[attr-defined]
        return True


def _query_latest_successful_rebuild_job_id(
    settings: graph_lifecycle_providers.GraphLifecycleSettings,
) -> str | None:
    """Return the latest successful rebuild job id using durable persistence."""
    from src.data.database import create_engine_from_url, create_session_factory
    from src.data.repository import AssetGraphRepository, session_scope

    resolved_url = graph_lifecycle_providers.resolve_durable_graph_persistence_url(
        _settings_asset_graph_database_url(settings)
    )
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
        graph_state.startup_metadata = None
        graph_state.last_synced_job_id = None
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
        graph_state.startup_metadata = None
        graph_state.last_synced_job_id = None
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
    """
    Finalize the graph lifecycle after a rebuild attempt.

    If called when the runtime is not in the REBUILDING state, emits a warning event and returns without changing state.

    If `succeeded` is True transitions the lifecycle to READY; otherwise transitions it to FAILED.

    Parameters:
        succeeded (bool): Whether the rebuild succeeded; `True` transitions to READY, `False` transitions to FAILED.
    """
    with graph_lock:
        if graph_state.lifecycle_state != GraphRuntimeLifecycleState.REBUILDING:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="graph_rebuild_complete_invalid_state",
                    message=f"Ignoring complete_rebuild outside REBUILDING state: {graph_state.lifecycle_state}",
                    metadata={"lifecycle_state": str(graph_state.lifecycle_state)},
                ),
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
    graph, _startup_metadata = initialize_graph_runtime()
    return graph


def _create_metadata(
    source: GraphStartupSource,
    graph: AssetRelationshipGraph | None,
    **kwargs: Any,
) -> GraphStartupMetadata:
    """Create and populate a GraphStartupMetadata record for the initialized graph."""
    assets = getattr(graph, "assets", None) or {}
    relationships = getattr(graph, "relationships", None) or {}
    return GraphStartupMetadata(
        source=source,
        loaded_asset_count=len(assets),
        loaded_relationship_count=sum(len(edges) for edges in relationships.values()),
        startup_timestamp=datetime.now(UTC),
        persistence_enabled=kwargs.get("persistence_enabled", False),
        persistence_loaded=kwargs.get("persistence_loaded", False),
        persistence_saved=kwargs.get("persistence_saved", False),
        fallback_reason=kwargs.get("fallback_reason"),
    )


def _initialize_fallback_graph(
    settings: graph_lifecycle_providers.GraphLifecycleSettings,
    persistence_enabled: bool,
) -> tuple[AssetRelationshipGraph, GraphStartupMetadata]:
    """Initialize graph from fallback sources when persistence is unavailable or empty."""
    cache_path = getattr(settings, "graph_cache_path", None)
    use_real_data = bool(getattr(settings, "use_real_data_fetcher", False))

    source_id = GraphStartupSource.SAMPLE_DATA
    graph: AssetRelationshipGraph | None = None

    if cache_path:
        try:
            graph, _raw_source = graph_lifecycle_providers.load_graph_from_cache_path(
                cache_path,
                enable_network=use_real_data,
            )
            source_id = _resolve_provider_source(_raw_source)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="graph_startup_cache_load_failed",
                    message=f"Failed to load graph from cache path, falling back: {exc.__class__.__name__}",
                    metadata={"error": exc.__class__.__name__},
                ),
            )

    if graph is None and use_real_data:
        try:
            real_data_cache_path = getattr(settings, "real_data_cache_path", None)
            graph, _raw_source = graph_lifecycle_providers.load_graph_from_real_data_fetcher(
                real_data_cache_path,
            )
            source_id = _resolve_provider_source(_raw_source)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="graph_startup_real_data_fetch_failed",
                    message=f"Failed to fetch real data, falling back: {exc.__class__.__name__}",
                    metadata={"error": exc.__class__.__name__},
                ),
            )

    if graph is None:
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="graph_startup_source_detected",
                message="Graph startup source: sample",
                metadata={"source": "sample"},
            ),
        )
        graph = graph_lifecycle_providers.create_sample_graph()
        source_id = GraphStartupSource.SAMPLE_DATA

    # When persistence is enabled but the DB was empty, override the source
    # and skip saving back — the fallback graph should not be silently persisted.
    if persistence_enabled:
        source_id = GraphStartupSource.EMPTY_PERSISTENCE_FALLBACK

    # Do not save the fallback graph back to an empty persistence store.
    persistence_saved = False

    final_source = GraphStartupSource.EMPTY_PERSISTENCE_FALLBACK if persistence_enabled else source_id
    return graph, _create_metadata(
        source=final_source,
        graph=graph,
        persistence_enabled=persistence_enabled,
        persistence_saved=persistence_saved,
        fallback_reason="persistence_empty" if persistence_enabled else "persistence_disabled",
    )


def _is_persistence_enabled(db_url: str | None) -> bool:
    """Determine if database persistence is enabled and durable."""
    if db_url is None:
        return False
    try:
        graph_lifecycle_providers.resolve_durable_graph_persistence_url(db_url)
        return True
    except Exception:
        return False


def _try_initialize_last_synced_job_id(settings: graph_lifecycle_providers.GraphLifecycleSettings) -> None:
    """Attempt to initialize last_synced_job_id from database when loading persisted graph."""
    try:
        latest_job_id = _query_latest_successful_rebuild_job_id(settings)
        if latest_job_id:
            graph_state.last_synced_job_id = latest_job_id
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_startup_job_id_initialization_failed",
                message=(
                    "Failed to initialize last_synced_job_id during graph startup "
                    f"(exception_type={type(exc).__name__})"
                ),
                metadata={"error": type(exc).__name__},
            ),
        )


def _try_initialize_fallback_last_synced_job_id(db_url: str) -> None:
    """Attempt to query job history and initialize last_synced_job_id on empty persistence path."""
    try:
        from contextlib import ExitStack

        from src.data.database import create_engine_from_url
        from src.data.repository import AssetGraphRepository, session_scope

        resolved_url = graph_lifecycle_providers.resolve_durable_graph_persistence_url(db_url)
        with ExitStack() as stack:
            engine = create_engine_from_url(resolved_url)
            stack.callback(engine.dispose)
            session_factory = graph_lifecycle_providers.create_session_factory(engine)
            with session_scope(session_factory) as session:
                latest_job = AssetGraphRepository(session).get_latest_successful_rebuild_job()
                if latest_job is not None:
                    graph_state.last_synced_job_id = latest_job.job_id
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_startup_job_id_initialization_failed",
                message=(
                    "Failed to initialize last_synced_job_id during empty persistence fallback "
                    f"(exception_type={type(exc).__name__})"
                ),
                metadata={"error": type(exc).__name__},
            ),
        )


def initialize_graph_runtime() -> tuple[AssetRelationshipGraph, GraphStartupMetadata]:
    """
    Select and initialize an AssetRelationshipGraph and identify its startup source.

    The selection follows this precedence: explicit graph factory, persisted durable graph, cache file, real-data
    fetcher, then a generated sample graph. If a persisted graph is used, the function will attempt to initialize
    the module's `last_synced_job_id` from durable persistence.

    Returns:
        tuple[AssetRelationshipGraph, GraphStartupMetadata]: The initialized graph and its startup metadata.
    """
    settings = graph_lifecycle_providers.get_graph_lifecycle_settings()
    db_url = _settings_asset_graph_database_url(settings)
    persistence_enabled = _is_persistence_enabled(db_url)

    # 1. Explicit factory
    if graph_state.graph_factory is not None:
        factory_graph = graph_state.graph_factory()
        return factory_graph, _create_metadata(
            GraphStartupSource.EXPLICIT_FACTORY, factory_graph, persistence_enabled=persistence_enabled
        )

    # 2. Persisted graph
    persisted_graph = graph_lifecycle_providers.load_persisted_graph_if_available(db_url)

    if persisted_graph is not None:
        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="graph_startup_source_detected",
                message="Graph startup source: persisted_graph_store",
                metadata={"source": "persisted_graph_store"},
            ),
        )
        _try_initialize_last_synced_job_id(settings)
        return persisted_graph, _create_metadata(
            GraphStartupSource.PERSISTED,
            persisted_graph,
            persistence_enabled=persistence_enabled,
            persistence_loaded=True,
        )

    # persisted_graph is None → DB is empty (failure would have raised above).
    # When persistence is enabled, open a second session to query job history and
    # ensure session cleanup is always exercised on the empty-DB path.
    if persistence_enabled and db_url is not None:
        _try_initialize_fallback_last_synced_job_id(db_url)

    return _initialize_fallback_graph(settings, persistence_enabled)


def sync_with_latest_rebuild() -> None:
    """
    Check durable persistence for a newer successful rebuild.

    If found, this loads and synchronizes that graph into the running runtime.

    If the durable graph database is not configured or the runtime is rebuilding or shutting down, the function
    returns without action. When a newer rebuild job is detected it loads the persisted graph, attempts to
    publish it to the module runtime (and legacy `api.main.graph` if present), updates graph metrics on success,
    and emits observability events. Failures during the sync attempt are caught and emitted as a warning
    event; the function does not raise.
    """
    settings = graph_lifecycle_providers.get_graph_lifecycle_settings()
    if not _settings_asset_graph_database_url(settings):
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

        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="new_rebuild_detected",
                message=f"New successful rebuild detected (job_id: {latest_job_id}). Synchronizing...",
                metadata={"job_id": latest_job_id},
            ),
        )

        resolved_url = graph_lifecycle_providers.resolve_durable_graph_persistence_url(
            _settings_asset_graph_database_url(settings)
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
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_sync_failed",
                message=f"Failed to sync with latest rebuild from database: {type(exc).__name__}",
                metadata={"error": type(exc).__name__},
            ),
        )

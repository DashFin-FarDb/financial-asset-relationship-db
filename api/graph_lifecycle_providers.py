"""Boundary providers for graph lifecycle initialization."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from sqlalchemy.engine import make_url  # pylint: disable=import-error
from sqlalchemy.exc import ArgumentError  # pylint: disable=import-error

from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.repository import AssetGraphRepository
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

from .api_models import GraphRebuildSource

logger = logging.getLogger(__name__)


class GraphPersistenceNotConfiguredError(Exception):
    """Raised when the graph persistence database URL is not configured."""


class GraphPersistenceNonDurableError(Exception):
    """Raised when graph persistence is configured with a non-durable database."""


class GraphPersistenceInvalidUrlError(GraphPersistenceNotConfiguredError):
    """Raised when the graph persistence URL cannot be parsed."""


@dataclass(frozen=True)
class GraphLifecycleSettings:
    """Immutable settings controlling graph lifecycle behavior."""

    asset_graph_database_url: str | None = None
    graph_cache_path: str | None = None
    use_real_data_fetcher: bool = False
    real_data_cache_path: str | None = None


def get_graph_lifecycle_settings() -> GraphLifecycleSettings:
    """Retrieve and freeze current graph lifecycle settings."""
    settings = get_settings()
    return GraphLifecycleSettings(
        asset_graph_database_url=settings.asset_graph_database_url,
        graph_cache_path=settings.graph_cache_path,
        use_real_data_fetcher=settings.use_real_data_fetcher,
        real_data_cache_path=settings.real_data_cache_path,
    )


def clear_graph_lifecycle_settings_cache() -> None:
    """Clear cached settings used by graph lifecycle initialization."""
    get_settings.cache_clear()


def load_persisted_graph_if_available(
    database_url: str | None,
) -> AssetRelationshipGraph | None:
    """
    Attempt to load a persisted asset relationship graph from the configured durable database.

    If a database URL is provided, it attempts to create a session and load the graph
    using the AssetGraphRepository. In-memory SQLite URLs are treated as not available.
    Errors during loading are logged and re-raised as RuntimeError.

    Returns:
        AssetRelationshipGraph | None: The loaded graph, or None if persistence is
            not configured or points to an in-memory database.
    """
    if database_url is None:
        return None

    try:
        resolved_url = resolve_durable_graph_persistence_url(database_url)
    except GraphPersistenceNotConfiguredError:
        return None
    except GraphPersistenceNonDurableError:
        return None

    try:
        engine = create_engine_from_url(resolved_url)
        try:
            session_factory = create_session_factory(engine)
            from src.data.repository import session_scope

            with session_scope(session_factory) as session:
                repo = AssetGraphRepository(session)
                return repo.load_graph()
        finally:
            engine.dispose()
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="graph_persistence_load_failed",
                message=f"Failed to load persisted graph during startup: {exc.__class__.__name__}",
                metadata={"error": exc.__class__.__name__},
            ),
        )
        raise RuntimeError("Failed to load persisted graph during startup") from None


def load_graph_from_cache_path(
    cache_path: str,
    *,
    enable_network: bool,
) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """Load a graph through the real-data cache path."""
    from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error,import-outside-toplevel

    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=enable_network)
    graph, source = fetcher.create_real_database_with_source()
    return graph, cast(GraphRebuildSource, source)


def load_graph_from_real_data_fetcher(
    cache_path: str | None,
) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """Load a graph from the real-data fetcher with network access."""
    from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error,import-outside-toplevel

    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=True)
    graph, source = fetcher.create_real_database_with_source()
    return graph, cast(GraphRebuildSource, source)


def create_sample_graph() -> AssetRelationshipGraph:
    """Create a graph populated with the default sample dataset."""
    return create_sample_database()


def resolve_durable_graph_persistence_url(database_url: str | None) -> str:
    """
    Validate and return a durable database URL suitable for graph persistence.

    Returns:
        The resolved durable database URL.

    Raises:
        GraphPersistenceNotConfiguredError: If the provided URL is unset or blank.
        GraphPersistenceNonDurableError: If the resolved URL refers to an in-memory SQLite database.
        GraphPersistenceInvalidUrlError: If the provided URL cannot be parsed as a valid SQLAlchemy URL.
    """
    resolved_url = _resolve_persistence_database_url(database_url)
    if resolved_url is None:
        raise GraphPersistenceNotConfiguredError("Graph persistence is not configured.")

    # Validate URL format
    try:
        make_url(resolved_url)
    except ArgumentError:
        raise GraphPersistenceInvalidUrlError("Invalid database URL format.") from None

    if _is_in_memory_sqlite_url(resolved_url):
        raise GraphPersistenceNonDurableError("Graph persistence must use a durable database.")

    return resolved_url


def build_rebuild_graph(
    settings: GraphLifecycleSettings,
    *,
    on_checkpoint: Callable[[dict[str, Any]], None] | None = None,
    initial_checkpoint: dict[str, Any] | None = None,
) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """
    Select a rebuild source and construct a fresh asset relationship graph accordingly.

    The selection precedence is:
    1. If `settings.graph_cache_path` is set and the path exists, load from the cache and return source `"cache"`.
    2. Else if `settings.use_real_data_fetcher` is true, fetch real data and return source `"real_data"`.
    3. Otherwise, create and return the sample graph with source `"sample"`.

    Parameters:
        settings (GraphLifecycleSettings): Immutable settings that control cache paths
            and whether real-data fetching is enabled.
        on_checkpoint: Optional callback for progress persistence.
        initial_checkpoint: Optional state to resume from.

    Returns:
        tuple[AssetRelationshipGraph, GraphRebuildSource]: A tuple where the first element is the constructed graph
            and the second element is the rebuild source string: `"cache"`, `"real_data"`, or `"sample"`.
    """
    try:
        if settings.graph_cache_path and Path(settings.graph_cache_path).exists():
            graph, source = load_graph_from_cache_path(
                settings.graph_cache_path,
                enable_network=settings.use_real_data_fetcher,
            )
            return graph, source

        if settings.use_real_data_fetcher:
            from src.data.real_data_fetcher import RealDataFetcher
            from src.logic.reconciliation_engine import ReconciliationEngine, Severity

            fetcher = RealDataFetcher(cache_path=settings.real_data_cache_path, enable_network=True)
            assets, events, raw_source = fetcher.fetch_raw_data_with_source()
            source = cast(GraphRebuildSource, raw_source)

            # Use ReconciliationEngine to orchestrate the rebuild with checkpointing.
            # A no-op evaluator stub is provided since drift detection is not needed here.
            class _NoOpEvaluator:
                """Minimal stub satisfying ReconciliationEngine's evaluator protocol."""

                def evaluate_drift(self) -> tuple[str, Severity, dict[str, str | int | float | bool | None]]:
                    return "none", Severity.NONE, {}

            engine = ReconciliationEngine(_NoOpEvaluator())
            graph = engine.run_rebuild(
                assets=assets,
                regulatory_events=events,
                on_checkpoint=on_checkpoint,
                initial_checkpoint=initial_checkpoint,
            )

            if settings.real_data_cache_path:
                # Still persist to cache if configured
                fetcher._persist_cache(graph)  # pylint: disable=protected-access

            return (graph, source)

        return (create_sample_graph(), "sample")
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="graph_rebuild_build_failed",
                message=f"Failed to build rebuild graph: {exc.__class__.__name__}",
                metadata={"error": exc.__class__.__name__},
            ),
        )
        raise RuntimeError("Failed to build rebuild graph") from exc


def _resolve_persistence_database_url(database_url: str | None) -> str | None:
    """Normalize and resolve the database URL for persistence."""
    if database_url is None:
        return None
    url_str = database_url.strip()
    return url_str if url_str else None


def _is_in_memory_sqlite_url(url: str) -> bool:
    """Determine if a database URL refers to an in-memory SQLite database."""
    if not url.startswith("sqlite"):
        return False

    # Common patterns for in-memory SQLite
    in_memory_patterns = [
        ":memory:",
        "sqlite://",
        "sqlite:///",
        "sqlite:///:memory:",
    ]

    # Also handle sqlite:// (default is memory) and sqlite://?cache=shared
    # make_url helps parse complex SQLAlchemy URLs
    try:
        parsed_url = make_url(url)
        if parsed_url.database in (None, "", ":memory:"):
            return True
    except Exception:
        pass

    return any(pattern in url for pattern in in_memory_patterns)

"""Boundary providers for graph lifecycle initialization."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import select  # pylint: disable=import-error
from sqlalchemy.engine import Engine, make_url  # pylint: disable=import-error
from sqlalchemy.exc import ArgumentError  # pylint: disable=import-error
from sqlalchemy.orm import Session  # pylint: disable=import-error

from src.config.settings import get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import AssetORM
from src.data.repository import AssetGraphRepository
from src.data.sample_data import create_sample_database
from src.logic.asset_graph import AssetRelationshipGraph
from src.observability.facade import ObservabilityEvent, log_event

logger = logging.getLogger(__name__)

GraphRebuildSource = Literal["cache", "real_data", "sample"]
_GRAPH_PERSISTENCE_SAVE_ERROR_MESSAGE = "Failed to persist rebuilt graph."


@dataclass(frozen=True)
class GraphLifecycleSettings:
    """Immutable lifecycle-boundary settings projected from :class:`Settings`.

    Values are validated at load time on the root settings model; this dataclass
    must not re-validate or apply defensive fallbacks.
    """

    asset_graph_database_url: str | None = None
    coordination_database_url: str | None = None
    graph_cache_path: str | None = None
    real_data_cache_path: str | None = None
    use_real_data_fetcher: bool = False
    rebuild_lock_ttl_seconds: int = 300  # mirrored from Settings; env REBUILD_LOCK_TTL_SECONDS


class GraphPersistenceNotConfiguredError(RuntimeError):
    """Raised when durable graph persistence is not explicitly configured."""


class GraphPersistenceNonDurableError(RuntimeError):
    """Raised when graph persistence is configured with a non-durable target."""


class GraphPersistenceSaveError(RuntimeError):
    """Raised when a rebuilt graph could not be persisted."""


class GraphRebuildSourceError(RuntimeError):
    """Raised when a fresh rebuild graph could not be constructed."""


def get_graph_lifecycle_settings() -> GraphLifecycleSettings:
    """Create lifecycle settings from the application's settings."""
    settings = get_settings()
    return GraphLifecycleSettings(
        asset_graph_database_url=settings.asset_graph_database_url,
        coordination_database_url=settings.coordination_database_url,
        graph_cache_path=settings.graph_cache_path,
        real_data_cache_path=settings.real_data_cache_path,
        use_real_data_fetcher=settings.use_real_data_fetcher,
        rebuild_lock_ttl_seconds=settings.rebuild_lock_ttl_seconds,
    )


def clear_graph_lifecycle_settings_cache() -> None:
    """Clear cached settings used by graph lifecycle initialization."""
    get_settings.cache_clear()


def load_persisted_graph_if_available(
    database_url: str | None,
) -> AssetRelationshipGraph | None:
    """
    Attempt to load a persisted asset relationship graph from the configured durable database.

    If no durable URL is configured or the resolved URL refers to an in-memory SQLite database, no load is
    attempted and the function returns `None`.

    Parameters:
        database_url (str | None): Persistence database URL or `None`. Whitespace-only or empty strings
            are treated as unset.

    Returns:
        AssetRelationshipGraph | None: The persisted graph if one was successfully loaded; `None` if
            durable persistence is not configured or was skipped for an in-memory SQLite URL.

    Raises:
        RuntimeError: If an unexpected error occurs while attempting to load persisted data.
    """
    resolved_url = _resolve_persistence_database_url(database_url)
    if resolved_url is None:
        return None

    if _is_in_memory_sqlite_url(resolved_url):
        _log_in_memory_sqlite_persistence_skip()
        return None

    try:
        return _load_persisted_graph_from_configured_store(resolved_url)
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
    return cast(tuple[AssetRelationshipGraph, GraphRebuildSource], fetcher.create_real_database_with_source())


def load_graph_from_real_data_fetcher(
    cache_path: str | None,
) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """Load a graph from the real-data fetcher with network access."""
    from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error,import-outside-toplevel

    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=True)
    return cast(tuple[AssetRelationshipGraph, GraphRebuildSource], fetcher.create_real_database_with_source())


def create_sample_graph() -> AssetRelationshipGraph:
    """Create a graph populated with the default sample dataset."""
    return create_sample_database()


class GraphPersistenceInvalidUrlError(Exception):
    """Raised when the graph persistence URL cannot be parsed."""


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

                def evaluate_drift(self) -> tuple[str, Severity, dict[str, Any]]:
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
        raise GraphRebuildSourceError("Failed to build rebuild graph.") from None


def save_graph_to_persistence(
    database_url: str | None,
    graph: AssetRelationshipGraph,
    pre_commit_check: Callable[[], None] | None = None,
) -> None:
    """
    Persist an AssetRelationshipGraph to a durable database.

    Parameters:
        database_url: Explicit persistence database URL. None or blank is rejected.
        graph: Graph to persist.

    Raises:
        GraphPersistenceNotConfiguredError: If no persistence URL is configured.
        GraphPersistenceNonDurableError: If the configured URL points to a non-durable (in-memory) store.
        GraphPersistenceSaveError: If saving the graph or creating the persistence engine/session fails.
    """
    resolved_url = resolve_durable_graph_persistence_url(database_url)
    engine = _create_graph_persistence_engine(resolved_url)
    try:
        _save_graph_with_engine(engine, graph, pre_commit_check=pre_commit_check)
    finally:
        engine.dispose()


def _create_graph_persistence_engine(database_url: str) -> Engine:
    """
    Create a SQLAlchemy engine for graph persistence.

    Returns:
        engine (Engine): Engine configured for the provided database URL.

    Raises:
        GraphPersistenceSaveError: If the engine cannot be created for the given URL.
    """
    try:
        return create_engine_from_url(database_url)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="graph_persistence_engine_creation_failed",
                message=f"Failed to prepare graph persistence engine: {exc.__class__.__name__}",
                metadata={"error": exc.__class__.__name__},
            ),
        )
        raise GraphPersistenceSaveError(_GRAPH_PERSISTENCE_SAVE_ERROR_MESSAGE) from None


def _save_graph_with_engine(
    engine: Engine,
    graph: AssetRelationshipGraph,
    *,
    pre_commit_check: Callable[[], None] | None = None,
) -> None:
    """
    Persist an asset relationship graph using a short-lived database session.

    If provided, `pre_commit_check` is executed before the transaction is committed; any exception it raises
    prevents the commit and is propagated. The session is always closed when this function returns.

    Parameters:
        engine (Engine): Engine configured for the persistence store.
        graph (AssetRelationshipGraph): Graph to be persisted.
        pre_commit_check (Callable[[], None] | None): Optional callable run just before commit to validate state.

    Raises:
        GraphPersistenceSaveError: If creating the session or saving the graph fails.
    """
    try:
        session_factory = create_session_factory(engine)
        session = session_factory()
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="graph_persistence_session_creation_failed",
                message=f"Failed to prepare graph persistence session: {exc.__class__.__name__}",
                metadata={"error": exc.__class__.__name__},
            ),
        )
        raise GraphPersistenceSaveError(_GRAPH_PERSISTENCE_SAVE_ERROR_MESSAGE) from None

    try:
        _save_graph_with_session(session, graph, pre_commit_check=pre_commit_check)
    finally:
        session.close()


def _save_graph_with_session(
    session: Session,
    graph: AssetRelationshipGraph,
    *,
    pre_commit_check: Callable[[], None] | None = None,
) -> None:
    """
    Persist the given AssetRelationshipGraph using the provided SQLAlchemy session and commit the transaction.

    If `pre_commit_check` is provided it will be executed after the graph is saved and before the commit;
    an exception from that check will abort the commit.

    Parameters:
        session (Session): Active SQLAlchemy session used to persist the graph.
        graph (AssetRelationshipGraph): Graph to persist.
        pre_commit_check (Callable[[], None] | None): Optional callable invoked after saving and before commit;
            if it raises, the transaction is aborted.

    Raises:
        GraphPersistenceSaveError: If saving the graph, the pre-commit check, or committing the transaction fails.
    """
    pre_commit_error: Exception | None = None
    try:
        AssetGraphRepository(session).save_graph(graph)
        if pre_commit_check is not None:
            try:
                pre_commit_check()
            except Exception as e:
                pre_commit_error = e
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="graph_persistence_pre_commit_failed",
                        message=f"Pre-commit persistence safety check failed: {pre_commit_error.__class__.__name__}",
                        metadata={"error": pre_commit_error.__class__.__name__},
                    ),
                )
                raise
        session.commit()
    except Exception as exc:
        try:
            session.rollback()
        except Exception as rollback_exc:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="graph_persistence_rollback_failed",
                    message=f"Failed to roll back rebuilt graph persistence: {rollback_exc.__class__.__name__}",
                    metadata={"error": rollback_exc.__class__.__name__},
                ),
            )

        # If the failure originated in the pre-commit check, re-raise the original exception
        # to allow specialized upstream handling and avoid generic save error wrapping.
        if pre_commit_error is not None:
            raise pre_commit_error from None

        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="graph_persistence_save_failed",
                message=f"Failed to persist rebuilt graph: {exc.__class__.__name__}",
                metadata={"error": exc.__class__.__name__},
            ),
        )
        raise GraphPersistenceSaveError(_GRAPH_PERSISTENCE_SAVE_ERROR_MESSAGE) from None


def _resolve_persistence_database_url(database_url: str | None) -> str | None:
    """
    Resolve and normalize a persistence database URL.

    Returns:
        The trimmed URL string if non-empty, otherwise None.
    """
    resolved_url = (database_url or "").strip()
    return resolved_url or None


def _log_in_memory_sqlite_persistence_skip() -> None:
    """
    Emit an observability warning that startup persisted graph loading is skipped.

    This occurs because the configured database is an in-memory SQLite instance.
    Records an observability event named "graph_persistence_skip_in_memory".
    """
    log_event(
        logger,
        logging.WARNING,
        ObservabilityEvent(
            event="graph_persistence_skip_in_memory",
            message=(
                "ASSET_GRAPH_DATABASE_URL points to an in-memory SQLite database; "
                "startup persistence loading requires a file-based or network database. "
                "Skipping persisted graph load."
            ),
        ),
    )


def _load_persisted_graph_from_configured_store(
    database_url: str,
) -> AssetRelationshipGraph | None:
    """
    Load an AssetRelationshipGraph from the persistent store identified by database_url.

    If the persistent store contains no persisted graph rows, returns None.

    Parameters:
        database_url (str): Database connection URL for the persistent store.

    Returns:
        AssetRelationshipGraph | None: The loaded graph, or `None` when no persisted graph rows exist.
    """
    engine = create_engine_from_url(database_url)
    try:
        session_factory = create_session_factory(engine)
        session = session_factory()
        try:
            if not _has_persisted_graph_rows(session):
                return None
            return AssetGraphRepository(session).load_graph()
        finally:
            session.close()
    finally:
        engine.dispose()


def _has_persisted_graph_rows(session: Session) -> bool:
    """
    Determine whether the persistence store contains at least one persisted asset row.

    Returns:
        `True` if the store contains at least one persisted `AssetORM` row, `False` otherwise.
    """
    return session.execute(select(AssetORM.id).limit(1)).scalar_one_or_none() is not None


def _is_in_memory_sqlite_url(url: str) -> bool:
    """Return whether a SQLAlchemy URL points to in-memory SQLite."""
    try:
        parsed = make_url(url)
    except ArgumentError:
        return False

    if parsed.get_backend_name() != "sqlite":
        return False

    database = parsed.database or ""
    if database in {"", ":memory:"}:
        return True
    if database.startswith("file::memory:"):
        return True
    return database.startswith("file:") and _query_mode_is_memory(parsed.query.get("mode"))


def _query_mode_is_memory(mode: object) -> bool:
    """Return whether a parsed SQLAlchemy URL query mode requests memory."""
    return mode == "memory" or (isinstance(mode, tuple) and "memory" in mode)

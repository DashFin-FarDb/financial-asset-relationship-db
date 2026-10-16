"""Boundary providers for graph lifecycle initialization."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import select  # pylint: disable=import-error
from sqlalchemy.engine import Engine, make_url  # pylint: disable=import-error
from sqlalchemy.exc import ArgumentError  # pylint: disable=import-error
from sqlalchemy.orm import Session  # pylint: disable=import-error

from src.config.settings import DeploymentEnvironment, get_settings
from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import AssetORM, RebuildJobORM
from src.data.real_data_fetcher import DataAcquisitionIncompleteError
from src.data.relationship_assertion_db_models import RelationshipProjectionPublicationORM
from src.data.repository import AssetGraphRepository
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.reconciliation_engine import RebuildCancelledError
from src.logic.snapshot_attestation import CanonicalizationValidationError
from src.observability.facade import ObservabilityEvent, log_event

logger = logging.getLogger(__name__)


class SnapshotProvenanceClassification(str, Enum):
    """Internal classifications for persisted-graph provenance evaluation."""

    VERIFIED = "verified"
    CLEAN_INSTALLATION = "clean_installation"
    MISSING_PROVENANCE = "missing_provenance"
    INCONSISTENT_ATTESTATION = "inconsistent_attestation"
    CONTAMINATION = "contamination"
    DATABASE_UNAVAILABLE = "database_unavailable"


GraphRebuildSource = Literal["cache", "real_data"]
_GRAPH_PERSISTENCE_SAVE_ERROR_MESSAGE = "Failed to persist rebuilt graph."
HOSTED_FALLBACK_ENVIRONMENTS: frozenset[DeploymentEnvironment] = frozenset(
    {DeploymentEnvironment.PREVIEW, DeploymentEnvironment.STAGING}
)


@dataclass(frozen=True)
class GraphLifecycleSettings:
    """Immutable lifecycle-boundary settings projected from :class:`Settings`.

    Values are validated at load time on the root settings model; this dataclass
    must not re-validate or apply defensive fallbacks.
    """

    asset_graph_database_url: str | None = None
    database_url: str | None = None
    coordination_database_url: str | None = None
    env: DeploymentEnvironment = DeploymentEnvironment.DEVELOPMENT
    vercel_env: DeploymentEnvironment | None = None
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


class AuthoritativeGraphUnavailableError(RuntimeError):
    """Raised when no authoritative published graph is available."""


class GraphRebuildSourceError(RuntimeError):
    """Raised when a fresh rebuild graph could not be constructed."""


def get_graph_lifecycle_settings() -> GraphLifecycleSettings:
    """Create lifecycle settings from the application's settings."""
    settings = get_settings()
    return GraphLifecycleSettings(
        asset_graph_database_url=settings.asset_graph_database_url,
        database_url=settings.database_url,
        coordination_database_url=settings.coordination_database_url,
        env=settings.env,
        vercel_env=settings.vercel_env,
        graph_cache_path=settings.graph_cache_path,
        real_data_cache_path=settings.real_data_cache_path,
        use_real_data_fetcher=settings.use_real_data_fetcher,
        rebuild_lock_ttl_seconds=settings.rebuild_lock_ttl_seconds,
    )


def _settings_value(settings: object, field_name: str) -> str | None:
    """Read a string-like value from modern or legacy settings objects."""
    value = getattr(settings, field_name, None)
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return str(value)


def _settings_environment(settings: object, field_name: str) -> DeploymentEnvironment | None:
    """Read a deployment environment enum from modern or legacy settings objects."""
    value = getattr(settings, field_name, None)
    if value is None:
        return None
    if isinstance(value, DeploymentEnvironment):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        try:
            return DeploymentEnvironment(normalized) if normalized else None
        except ValueError:
            return None
    try:
        return DeploymentEnvironment(str(value).strip().lower())
    except ValueError:
        return None


def _is_hosted_fallback_environment(settings: object) -> bool:
    """Return whether hosted graph fallback should be allowed for this runtime."""
    env_name = _settings_environment(settings, "env")
    if env_name in HOSTED_FALLBACK_ENVIRONMENTS:
        return True

    return _settings_environment(settings, "vercel_env") in HOSTED_FALLBACK_ENVIRONMENTS


def resolve_hosted_graph_database_url(settings: object) -> str | None:
    """Resolve the hosted graph database URL, allowing a shared Supabase boundary in hosted environments.

    Preference order:
    1. `asset_graph_database_url` when explicitly configured.
    2. `database_url` as a hosted fallback when running in preview/staging.
    3. `None` when no hosted graph persistence should be assumed.
    """
    asset_graph_database_url = _settings_value(settings, "asset_graph_database_url")
    if asset_graph_database_url:
        return asset_graph_database_url

    if _is_hosted_fallback_environment(settings):
        return _settings_value(settings, "database_url")

    return None


def should_degrade_hosted_startup(settings: object) -> bool:
    """Return whether hosted fallback startup failures should be downgraded to degraded boot."""
    if _settings_value(settings, "asset_graph_database_url"):
        return False
    hosted_database_url = resolve_hosted_graph_database_url(settings)
    return _is_hosted_fallback_environment(settings) and bool(hosted_database_url and hosted_database_url.strip())


def clear_graph_lifecycle_settings_cache() -> None:
    """Clear cached settings used by graph lifecycle initialization."""
    get_settings.cache_clear()


def load_persisted_graph_if_available(
    database_url: str | None,
) -> AssetRelationshipGraph | None:
    """
    Attempt to load a persisted asset relationship graph from the configured durable database.

    If no durable URL is configured, the resolved URL refers to an in-memory SQLite database,
    or an error occurs while loading, the function returns ``None`` and the error is logged.

    Parameters:
        database_url (str | None): Persistence database URL or ``None``. Whitespace-only or
            empty strings are treated as unset.

    Returns:
        On unexpected load failures, the function logs the error and raises
        ``RuntimeError("Failed to load persisted graph during startup")``.
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
    cancel_event: threading.Event | None = None,
) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """Load a graph through the real-data cache path."""
    from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error,import-outside-toplevel

    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=enable_network)
    return cast(
        tuple[AssetRelationshipGraph, GraphRebuildSource],
        fetcher.create_real_database_with_source(cancel_event=cancel_event),
    )


def load_graph_from_real_data_fetcher(
    cache_path: str | None,
    cancel_event: threading.Event | None = None,
) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """Load a graph from the real-data fetcher with network access."""
    from src.data.real_data_fetcher import RealDataFetcher  # pylint: disable=import-error,import-outside-toplevel

    fetcher = RealDataFetcher(cache_path=cache_path, enable_network=True)
    return cast(
        tuple[AssetRelationshipGraph, GraphRebuildSource],
        fetcher.create_real_database_with_source(cancel_event=cancel_event),
    )


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
    cancel_event: threading.Event | None = None,
) -> tuple[AssetRelationshipGraph, GraphRebuildSource]:
    """
    Select a rebuild source and construct a fresh asset relationship graph accordingly.

    The selection precedence is:
    1. If `settings.graph_cache_path` is set and the path exists, load from the cache and return source `"cache"`.
    2. Else if `settings.use_real_data_fetcher` is true, fetch real data and return source `"real_data"`.
    3. Otherwise, fail closed by raising AuthoritativeGraphUnavailableError.

    Parameters:
        settings (GraphLifecycleSettings): Immutable settings that control cache paths
            and whether real-data fetching is enabled.
        on_checkpoint: Optional callback for progress persistence.
        initial_checkpoint: Optional state to resume from.
        cancel_event: Optional event to signal rebuild cancellation.

    Returns:
        tuple[AssetRelationshipGraph, GraphRebuildSource]: A tuple where the first element is the constructed graph
            and the second element is the rebuild source string: `"cache"` or `"real_data"`.

    Raises:
        AuthoritativeGraphUnavailableError: If neither cache nor real data is available.
        RebuildCancelledError: If rebuild execution is cancelled.
        GraphRebuildSourceError: If building the rebuild graph fails unexpectedly.
    """
    try:
        if settings.graph_cache_path and Path(settings.graph_cache_path).exists():
            if cancel_event and cancel_event.is_set():
                raise RebuildCancelledError("Rebuild cancelled before loading cache.")
            graph, source = load_graph_from_cache_path(
                settings.graph_cache_path,
                enable_network=settings.use_real_data_fetcher,
                cancel_event=cancel_event,
            )
            return graph, source

        if settings.use_real_data_fetcher:
            from src.data.real_data_fetcher import RealDataFetcher

            fetcher = RealDataFetcher(cache_path=settings.real_data_cache_path, enable_network=True)
            assets, events, raw_source = fetcher.fetch_raw_data_with_source(cancel_event=cancel_event)
            source = cast(GraphRebuildSource, raw_source)

            from src.logic.rebuild_executor import RebuildExecutor

            graph = RebuildExecutor().run_rebuild(
                assets=assets,
                regulatory_events=events,
                on_checkpoint=on_checkpoint,
                initial_checkpoint=initial_checkpoint,
                cancel_event=cancel_event,
            )

            if settings.real_data_cache_path:
                # Still persist to cache if configured
                fetcher._persist_cache(graph)  # pylint: disable=protected-access

            return (graph, source)

        raise AuthoritativeGraphUnavailableError("No valid rebuild source available.")
    except DataAcquisitionIncompleteError:
        raise AuthoritativeGraphUnavailableError("No complete authoritative rebuild source available.") from None
    except (RebuildCancelledError, AuthoritativeGraphUnavailableError):
        # Re-raise cancellation and authoritative graph unavailable errors directly
        raise
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


def stage_graph_snapshot(session: Session, graph: AssetRelationshipGraph) -> None:
    """Stage a graph snapshot in the caller-owned transaction without committing.

    GRAC publication uses this boundary so the read-model snapshot, candidate
    revision, rebuild success transition, and publication row commit together.
    """
    try:
        AssetGraphRepository(session).save_graph(graph)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="graph_persistence_stage_failed",
                message=f"Failed to stage rebuilt graph: {exc.__class__.__name__}",
                metadata={"error": exc.__class__.__name__},
            ),
        )
        raise GraphPersistenceSaveError(_GRAPH_PERSISTENCE_SAVE_ERROR_MESSAGE) from None


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


def _validate_publication_attestation_metadata(
    publication: RelationshipProjectionPublicationORM,
    job: RebuildJobORM,
) -> str | None:
    """Validate publication attestation digest and execution identity binding.

    Returns the expected snapshot_sha256 digest if valid, or None if validation fails.
    """
    expected_digest = publication.snapshot_sha256
    if not expected_digest or not expected_digest.strip():
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_provenance_evaluation",
                message="Missing attestation digest: publication lacks snapshot_sha256",
                metadata={
                    "classification": SnapshotProvenanceClassification.MISSING_PROVENANCE.value,
                    "publication_id": publication.id,
                    "rebuild_job_id": publication.rebuild_job_id,
                },
            ),
        )
        return None

    pub_exec_id = publication.execution_id
    job_exec_id = job.execution_id
    if not pub_exec_id or not pub_exec_id.strip() or not job_exec_id or not job_exec_id.strip():
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_provenance_evaluation",
                message="Missing execution identity on publication or rebuild job",
                metadata={
                    "classification": SnapshotProvenanceClassification.MISSING_PROVENANCE.value,
                    "publication_id": publication.id,
                    "job_id": job.job_id,
                    "publication_execution_id": pub_exec_id,
                    "job_execution_id": job_exec_id,
                },
            ),
        )
        return None

    if pub_exec_id != job_exec_id:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_provenance_evaluation",
                message="Inconsistent execution identity between publication and rebuild job",
                metadata={
                    "classification": SnapshotProvenanceClassification.INCONSISTENT_ATTESTATION.value,
                    "publication_id": publication.id,
                    "job_id": job.job_id,
                    "publication_execution_id": pub_exec_id,
                    "job_execution_id": job_exec_id,
                },
            ),
        )
        return None

    if job.snapshot_sha256 and job.snapshot_sha256 != expected_digest:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_provenance_evaluation",
                message="Inconsistent attestation digest between rebuild job and publication",
                metadata={
                    "classification": SnapshotProvenanceClassification.INCONSISTENT_ATTESTATION.value,
                    "publication_id": publication.id,
                    "job_id": job.job_id,
                },
            ),
        )
        return None

    return expected_digest


def _load_persisted_graph_from_configured_store(
    database_url: str,
) -> AssetRelationshipGraph | None:
    """Load an AssetRelationshipGraph from the persistent store identified by database_url.

    Validates that the persisted graph has a verifiable, immutable snapshot attestation
    bound to a succeeded rebuild job and publication.
    """
    try:
        raw_engine = create_engine_from_url(database_url)
        engine: Engine = (
            raw_engine.execution_options(isolation_level="REPEATABLE READ")
            if raw_engine.dialect.name == "postgresql"
            else raw_engine
        )
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_provenance_evaluation",
                message=f"Database engine creation failed during startup graph provenance check: {exc.__class__.__name__}",
                metadata={"classification": SnapshotProvenanceClassification.DATABASE_UNAVAILABLE.value},
            ),
        )
        raise

    try:
        session_factory = create_session_factory(engine)
        session = session_factory()
        if engine.dialect.name == "sqlite":
            session.connection().exec_driver_sql("BEGIN")
        try:
            # 1. Clean installation check
            has_assets = _has_persisted_graph_rows(session)
            has_publications = (
                session.execute(select(RelationshipProjectionPublicationORM.id).limit(1)).scalar_one_or_none()
                is not None
            )
            if not has_assets and not has_publications:
                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="graph_provenance_evaluation",
                        message="Clean installation detected; no persisted graph or publication",
                        metadata={"classification": SnapshotProvenanceClassification.CLEAN_INSTALLATION.value},
                    ),
                )
                return None

            # 2. Query latest publication linked to a succeeded rebuild job
            stmt = (
                select(RelationshipProjectionPublicationORM, RebuildJobORM)
                .join(RebuildJobORM, RebuildJobORM.job_id == RelationshipProjectionPublicationORM.rebuild_job_id)
                .where(RebuildJobORM.status == "succeeded")
                .order_by(
                    RelationshipProjectionPublicationORM.published_at.desc(),
                    RelationshipProjectionPublicationORM.id.desc(),
                )
                .limit(1)
            )
            row = session.execute(stmt).first()
            if row is None:
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="graph_provenance_evaluation",
                        message="Missing publication provenance: no publication found for a succeeded rebuild job",
                        metadata={"classification": SnapshotProvenanceClassification.MISSING_PROVENANCE.value},
                    ),
                )
                return None

            publication, job = row

            # 3. Check publication attestation metadata and execution identity binding
            expected_digest = _validate_publication_attestation_metadata(publication, job)
            if expected_digest is None:
                return None

            # 6. Load graph once from persisted rows and recompute canonical digest
            repo = AssetGraphRepository(session)
            try:
                graph, actual_digest = repo.load_graph_with_attestation_hash()
            except CanonicalizationValidationError as val_exc:
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="graph_provenance_evaluation",
                        message=f"Contaminated or invalid entity in persisted graph: {val_exc}",
                        metadata={"classification": SnapshotProvenanceClassification.CONTAMINATION.value},
                    ),
                )
                return None

            if actual_digest != expected_digest:
                log_event(
                    logger,
                    logging.WARNING,
                    ObservabilityEvent(
                        event="graph_provenance_evaluation",
                        message=f"Persisted graph attestation mismatch: computed {actual_digest} != expected {expected_digest}",
                        metadata={
                            "classification": SnapshotProvenanceClassification.INCONSISTENT_ATTESTATION.value,
                            "computed_hash": actual_digest,
                            "expected_hash": expected_digest,
                            "publication_id": publication.id,
                            "job_id": job.job_id,
                        },
                    ),
                )
                return None

            # 7. Verification succeeded - return the verified graph object directly
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="graph_provenance_evaluation",
                    message="Persisted graph provenance verified successfully",
                    metadata={
                        "classification": SnapshotProvenanceClassification.VERIFIED.value,
                        "publication_id": publication.id,
                        "job_id": job.job_id,
                        "snapshot_sha256": expected_digest,
                    },
                ),
            )
            return graph
        finally:
            session.close()
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_provenance_evaluation",
                message=f"Database error during startup graph provenance check: {exc.__class__.__name__}",
                metadata={
                    "classification": SnapshotProvenanceClassification.DATABASE_UNAVAILABLE.value,
                    "error": exc.__class__.__name__,
                },
            ),
        )
        raise
    finally:
        raw_engine.dispose()


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

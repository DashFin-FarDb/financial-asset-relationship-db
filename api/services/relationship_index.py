"""Governed relationship index loading and cache management."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from threading import Lock
from typing import Literal, TypeAlias, TypedDict
from weakref import WeakKeyDictionary

from fastapi import HTTPException, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.data.database import create_engine_from_url, create_session_factory
from src.data.relationship_assertion_db_models import (
    RelationshipAssertionORM,
)
from src.data.relationship_assertion_repository import PublishedProjectionRevision, RelationshipAssertionRepository
from src.data.relationship_projection_persistence import PersistedProjectionRevision
from src.data.repository import session_scope
from src.governance.relationship_assertion import ValidationError
from src.governance.relationship_assertion_contract import PredicatesDocument, PredicateSpec, load_contract_bundle
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.relationship_projection import GovernedScope, ProjectionEdge

from ..graph_lifecycle_providers import (
    GraphPersistenceInvalidUrlError,
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    resolve_hosted_graph_database_url,
)

_GRAC_CURRENT_PURPOSE = "financial_graph_current_view"
_GRAPH_PERSISTENCE_MISCONFIGURED_DETAIL = "Graph persistence database is misconfigured"
_GRAPH_PERSISTENCE_UNAVAILABLE_DETAIL = "Graph persistence database is unavailable"
_GRAPH_PUBLICATION_INCONSISTENT_DETAIL = "Graph publication metadata is inconsistent"
_IN_CLAUSE_CHUNK_SIZE = 400
_cache_generation_lock = Lock()
_persistence_runtime_lock = Lock()
_runtime_graph_bindings_lock = Lock()


class _CacheGeneration:
    """Mutable cache-generation state guarded by the cache-generation lock."""

    def __init__(self) -> None:
        self.value = 0


class _PersistenceRuntime:
    """Reusable URL-scoped engine and session factory for governance reads."""

    def __init__(self) -> None:
        self.url: str | None = None
        self.engine: Engine | None = None
        self.session_factory: sessionmaker[Session] | None = None


_cache_generation = _CacheGeneration()
_persistence_runtime = _PersistenceRuntime()
_runtime_graph_bindings: WeakKeyDictionary[AssetRelationshipGraph, str | None] = WeakKeyDictionary()


class GovernanceMetadata(TypedDict):
    """Strict governance fields attached to one published relationship edge."""

    assertion_id: str
    governance_status: Literal["governed"]
    revision_id: str
    scope_refs: list[str]


GovernedRelationshipIndex: TypeAlias = dict[tuple[str, str, str], GovernanceMetadata]
PublicationBinding: TypeAlias = tuple[str, str, str]
RelationshipKey: TypeAlias = tuple[str, str, str]


@dataclass(frozen=True)
class PublishedProjectionContext:
    """Publication/revision envelope bound to one governed graph snapshot."""

    publication_id: str
    revision_id: str
    rebuild_job_id: str
    execution_id: str
    published_at: datetime
    purpose: str
    effective_at: datetime
    known_at: datetime
    contract_version: str
    projector_version: str
    edge_set_hash: str
    projection_hash: str
    governed_scopes: tuple[GovernedScope, ...]


@dataclass(frozen=True)
class ProjectionEdgeBinding:
    """Persisted edge identity bound to one runtime key orientation."""

    projection_edge_id: str
    orientation: Literal["canonical", "reverse"]
    metadata: GovernanceMetadata


@dataclass(frozen=True)
class PublishedRelationshipSnapshot:
    """Publication envelope, runtime governance index, and projection-edge bindings."""

    publication: PublishedProjectionContext | None
    governance_index: GovernedRelationshipIndex
    projection_bindings: Mapping[RelationshipKey, ProjectionEdgeBinding]


def _current_cache_generation() -> int:
    """Return the current governed relationship index cache generation."""
    with _cache_generation_lock:
        return _cache_generation.value


@lru_cache(maxsize=1)
def _load_contract_predicates() -> PredicatesDocument:
    """Load validated predicates once from the immutable pinned contract bundle."""
    _contract, predicates, _transitions = load_contract_bundle()
    return predicates


def _resolve_governance_persistence_url() -> str:
    """Resolve the durable graph database used by governed relationship reads."""
    settings = get_graph_lifecycle_settings()
    hosted_url = resolve_hosted_graph_database_url(settings)
    return resolve_durable_graph_persistence_url(hosted_url)


def _session_factory_for_url(persistence_url: str) -> sessionmaker[Session]:
    """Reuse one engine/session factory until the configured URL changes."""
    with _persistence_runtime_lock:
        if _persistence_runtime.url == persistence_url and _persistence_runtime.session_factory is not None:
            return _persistence_runtime.session_factory

        engine = create_engine_from_url(persistence_url)
        session_factory = create_session_factory(engine)
        previous_engine = _persistence_runtime.engine

        _persistence_runtime.url = persistence_url
        _persistence_runtime.engine = engine
        _persistence_runtime.session_factory = session_factory
        _load_governed_relationship_snapshot.cache_clear()
        _load_bound_governed_relationship_snapshot.cache_clear()
        _load_governed_relationship_index.cache_clear()
        _load_bound_governed_relationship_index.cache_clear()

        if previous_engine is not None:
            previous_engine.dispose()
        return session_factory


def _governance_session_factory() -> sessionmaker[Session]:
    """Return the shared session factory for the current graph persistence URL."""
    return _session_factory_for_url(_resolve_governance_persistence_url())


def _reset_governance_persistence_runtime() -> None:
    """Dispose and clear the reusable persistence runtime for tests or reconfiguration."""
    with _persistence_runtime_lock:
        engine = _persistence_runtime.engine
        _persistence_runtime.url = None
        _persistence_runtime.engine = None
        _persistence_runtime.session_factory = None
        if engine is not None:
            engine.dispose()
    with _runtime_graph_bindings_lock:
        _runtime_graph_bindings.clear()
    _load_governed_relationship_snapshot.cache_clear()
    _load_bound_governed_relationship_snapshot.cache_clear()
    _load_governed_relationship_index.cache_clear()
    _load_bound_governed_relationship_index.cache_clear()


def _assertion_predicates_for_edges(
    session: Session,
    published: PersistedProjectionRevision,
) -> dict[str, str]:
    """Load the exact predicate owner for every assertion referenced by the revision."""
    assertion_ids = sorted({edge.assertion_id for edge in published.revision.edges})
    if not assertion_ids:
        return {}

    assertion_predicates: dict[str, str] = {}
    for start in range(0, len(assertion_ids), _IN_CLAUSE_CHUNK_SIZE):
        assertion_id_chunk = assertion_ids[start : start + _IN_CLAUSE_CHUNK_SIZE]
        rows = (
            session.execute(
                select(RelationshipAssertionORM.id, RelationshipAssertionORM.predicate_id)
                .where(RelationshipAssertionORM.id.in_(assertion_id_chunk))
                .order_by(RelationshipAssertionORM.id)
            )
            .tuples()
            .all()
        )
        for assertion_id, predicate_id in rows:
            assertion_predicates[assertion_id] = predicate_id

    missing = sorted(set(assertion_ids) - assertion_predicates.keys())
    if missing:
        raise ValidationError(f"published projection references missing assertions: {missing}")
    return assertion_predicates


def _predicate_id_for_edge(
    edge: ProjectionEdge,
    assertion_predicates: Mapping[str, str],
    governed_scope_ids: set[str],
) -> str:
    """Resolve the governed predicate identifier owned by one published edge."""
    predicate_id = assertion_predicates.get(edge.assertion_id)
    if predicate_id is None:
        raise ValidationError(f"published edge references unknown assertion: {edge.assertion_id}")
    if predicate_id not in governed_scope_ids:
        raise ValidationError(
            f"published edge assertion {edge.assertion_id} predicate {predicate_id} is outside governed scopes"
        )
    return predicate_id


def _scope_ref_for_edge(
    edge: ProjectionEdge,
    predicates_by_id: Mapping[str, PredicateSpec],
    assertion_predicates: Mapping[str, str],
    governed_scope_ids: set[str],
) -> str:
    """Resolve and validate the one governed predicate scope owned by an edge."""
    predicate_id = _predicate_id_for_edge(edge, assertion_predicates, governed_scope_ids)
    predicate = predicates_by_id.get(predicate_id)
    if predicate is None:
        raise ValidationError(f"published edge assertion uses unregistered predicate: {predicate_id}")
    if predicate.projection.edge_type != edge.edge_type:
        raise ValidationError(f"published edge type {edge.edge_type} does not match assertion predicate {predicate_id}")
    return predicate_id


def _add_governed_edge(
    index: GovernedRelationshipIndex,
    projection_bindings: dict[RelationshipKey, ProjectionEdgeBinding],
    projection_edge_id: str,
    edge: ProjectionEdge,
    metadata: GovernanceMetadata,
) -> None:
    """Add forward and, when governed as bidirectional, reverse index entries."""
    forward_key = (edge.source_id, edge.target_id, edge.edge_type)
    existing = index.get(forward_key)
    if existing is not None and existing["assertion_id"] != metadata["assertion_id"]:
        raise ValidationError(f"duplicate governance key {forward_key!r} with conflicting assertion provenance")
    index[forward_key] = metadata
    existing_binding = projection_bindings.get(forward_key)
    if existing_binding is not None and (
        existing_binding.projection_edge_id != projection_edge_id or existing_binding.orientation != "canonical"
    ):
        raise ValidationError(f"duplicate projection-edge binding for runtime key {forward_key!r}")
    projection_bindings[forward_key] = ProjectionEdgeBinding(
        projection_edge_id=projection_edge_id,
        orientation="canonical",
        metadata=metadata,
    )
    if edge.direction == "bidirectional":
        reverse_key = (edge.target_id, edge.source_id, edge.edge_type)
        existing = index.get(reverse_key)
        if existing is not None and existing["assertion_id"] != metadata["assertion_id"]:
            raise ValidationError(f"duplicate governance key {reverse_key!r} with conflicting assertion provenance")
        index[reverse_key] = metadata
        existing_binding = projection_bindings.get(reverse_key)
        if existing_binding is not None and (
            existing_binding.projection_edge_id != projection_edge_id or existing_binding.orientation != "reverse"
        ):
            raise ValidationError(f"duplicate projection-edge binding for runtime key {reverse_key!r}")
        projection_bindings[reverse_key] = ProjectionEdgeBinding(
            projection_edge_id=projection_edge_id,
            orientation="reverse",
            metadata=metadata,
        )


def _published_relationship_snapshot(
    published: PersistedProjectionRevision,
    publication: PublishedProjectionContext,
    predicates: PredicatesDocument,
    assertion_predicates: Mapping[str, str],
) -> PublishedRelationshipSnapshot:
    """Build exact assertion-owned governance metadata for a published revision."""
    governed_scope_ids = {scope.predicate_id for scope in published.revision.governed_scopes}
    predicates_by_id = {predicate.id: predicate for predicate in predicates.predicates}
    index: GovernedRelationshipIndex = {}
    projection_bindings: dict[RelationshipKey, ProjectionEdgeBinding] = {}
    if len(published.edge_ids) != len(published.revision.edges):
        raise ValidationError("edge_ids length must match revision.edges")
    try:
        for projection_edge_id, edge in zip(published.edge_ids, published.revision.edges, strict=True):
            predicate_id = _scope_ref_for_edge(
                edge,
                predicates_by_id,
                assertion_predicates,
                governed_scope_ids,
            )
            metadata: GovernanceMetadata = {
                "assertion_id": edge.assertion_id,
                "governance_status": "governed",
                "revision_id": published.revision_id,
                "scope_refs": [predicate_id],
            }
            _add_governed_edge(index, projection_bindings, projection_edge_id, edge, metadata)
    except ValueError as exc:
        raise ValidationError("edge_ids length must match revision.edges") from exc
    return PublishedRelationshipSnapshot(
        publication=publication,
        governance_index=index,
        projection_bindings=projection_bindings,
    )


def _build_published_relationship_index(
    session: Session,
    published: PersistedProjectionRevision,
    publication: PublishedProjectionContext,
) -> PublishedRelationshipSnapshot:
    """Build governed metadata and projection bindings for one immutable publication."""
    predicates = _load_contract_predicates()
    assertion_predicates = _assertion_predicates_for_edges(session, published)
    return _published_relationship_snapshot(published, publication, predicates, assertion_predicates)


def _published_projection_context(
    published: PublishedProjectionRevision,
) -> PublishedProjectionContext:
    """Map one publication record to the public snapshot envelope."""
    persisted = published.persisted
    revision = persisted.revision
    return PublishedProjectionContext(
        publication_id=published.publication_id,
        revision_id=persisted.revision_id,
        rebuild_job_id=published.rebuild_job_id,
        execution_id=published.execution_id,
        published_at=published.published_at,
        purpose=revision.purpose,
        effective_at=revision.effective_at,
        known_at=revision.known_at,
        contract_version=revision.contract_version,
        projector_version=revision.projector_version,
        edge_set_hash=revision.edge_set_hash,
        projection_hash=revision.projection_hash,
        governed_scopes=revision.governed_scopes,
    )


def _latest_published_projection_binding_from_persistence() -> PublicationBinding | None:
    """Return the shared latest ``(rebuild_job_id, revision_id, publication_id)`` version."""
    try:
        with session_scope(_governance_session_factory()) as session:
            repository = RelationshipAssertionRepository(session)
            return repository.latest_published_projection_binding(_GRAC_CURRENT_PURPOSE)
    except GraphPersistenceInvalidUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_MISCONFIGURED_DETAIL,
        ) from exc
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
        # Optional governance persistence with no durable backing: callers already
        # treat a missing publication binding as "omit optional governance metadata",
        # so surface the same signal here instead of failing closed with a 503.
        return None
    except (ValidationError, PydanticValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PUBLICATION_INCONSISTENT_DETAIL,
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_UNAVAILABLE_DETAIL,
        ) from exc


def _published_projection_binding_for_rebuild_job_from_persistence(
    rebuild_job_id: str,
) -> tuple[str, str] | None:
    """Return the successful publication bound to one rebuild job."""
    try:
        with session_scope(_governance_session_factory()) as session:
            repository = RelationshipAssertionRepository(session)
            return repository.published_projection_binding_for_rebuild_job(rebuild_job_id)
    except GraphPersistenceInvalidUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_MISCONFIGURED_DETAIL,
        ) from exc
    except (
        GraphPersistenceNotConfiguredError,
        GraphPersistenceNonDurableError,
    ):
        return None
    except (ValidationError, PydanticValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PUBLICATION_INCONSISTENT_DETAIL,
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_UNAVAILABLE_DETAIL,
        ) from exc


def _load_governed_relationship_snapshot_for_publication(
    revision_id: str,
    publication_id: str,
) -> PublishedRelationshipSnapshot:
    """Load governed metadata and bindings for one immutable publication."""
    try:
        with session_scope(_governance_session_factory()) as session:
            repository = RelationshipAssertionRepository(session)
            published = repository.get_published_projection(publication_id)
            if published is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=_GRAPH_PUBLICATION_INCONSISTENT_DETAIL,
                )
            if published.persisted.revision_id != revision_id:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=_GRAPH_PUBLICATION_INCONSISTENT_DETAIL,
                )
            publication = _published_projection_context(published)
            return _build_published_relationship_index(session, published.persisted, publication)
    except GraphPersistenceInvalidUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_MISCONFIGURED_DETAIL,
        ) from exc
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
        return PublishedRelationshipSnapshot(publication=None, governance_index={}, projection_bindings={})
    except (ValidationError, PydanticValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PUBLICATION_INCONSISTENT_DETAIL,
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_UNAVAILABLE_DETAIL,
        ) from exc


def _load_governed_relationship_snapshot_from_persistence() -> PublishedRelationshipSnapshot:
    """Load latest governed metadata for unmanaged/test graph instances."""
    try:
        with session_scope(_governance_session_factory()) as session:
            repository = RelationshipAssertionRepository(session)
            published = repository.latest_published_projection_record(_GRAC_CURRENT_PURPOSE)
            if published is None:
                return PublishedRelationshipSnapshot(publication=None, governance_index={}, projection_bindings={})
            publication = _published_projection_context(published)
            return _build_published_relationship_index(session, published.persisted, publication)
    except GraphPersistenceInvalidUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_MISCONFIGURED_DETAIL,
        ) from exc
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
        return PublishedRelationshipSnapshot(publication=None, governance_index={}, projection_bindings={})
    except (ValidationError, PydanticValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PUBLICATION_INCONSISTENT_DETAIL,
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_GRAPH_PERSISTENCE_UNAVAILABLE_DETAIL,
        ) from exc


def _load_governed_relationship_index_from_persistence() -> GovernedRelationshipIndex:
    """Backward-compatible unmanaged governance index loader."""
    return _load_governed_relationship_snapshot_from_persistence().governance_index


def _runtime_graph_publication_binding(graph: AssetRelationshipGraph) -> tuple[bool, str | None]:
    """Return whether a graph is lifecycle-managed and its bound rebuild job."""
    from .. import graph_lifecycle  # pylint: disable=import-outside-toplevel

    with graph_lifecycle.graph_lock:
        is_current = graph_lifecycle.graph_state.graph is graph
        current_job_id = graph_lifecycle.graph_state.last_synced_job_id if is_current else None

    if is_current:
        with _runtime_graph_bindings_lock:
            _runtime_graph_bindings[graph] = current_job_id
        return True, current_job_id

    with _runtime_graph_bindings_lock:
        if graph in _runtime_graph_bindings:
            return True, _runtime_graph_bindings[graph]
    return False, None


def register_runtime_graph_publication_binding(
    graph: AssetRelationshipGraph,
    rebuild_job_id: str | None,
) -> None:
    """Retain the publication binding captured with a lifecycle-managed graph."""
    with _runtime_graph_bindings_lock:
        _runtime_graph_bindings[graph] = rebuild_job_id


@lru_cache(maxsize=4)
def _load_governed_relationship_snapshot(
    _graph: AssetRelationshipGraph,
    _generation: int,
) -> PublishedRelationshipSnapshot:
    """Load latest governed metadata snapshot for one unmanaged graph and generation."""
    return _load_governed_relationship_snapshot_from_persistence()


@lru_cache(maxsize=8)
def _load_bound_governed_relationship_snapshot(
    revision_id: str,
    publication_id: str,
    _generation: int,
) -> PublishedRelationshipSnapshot:
    """Load one immutable publication snapshot and cache generation."""
    return _load_governed_relationship_snapshot_for_publication(revision_id, publication_id)


@lru_cache(maxsize=4)
def _load_governed_relationship_index(
    graph: AssetRelationshipGraph,
    generation: int,
) -> GovernedRelationshipIndex:
    """Backward-compatible index cache wrapper for existing tests/callers."""
    return _load_governed_relationship_snapshot(graph, generation).governance_index


@lru_cache(maxsize=8)
def _load_bound_governed_relationship_index(
    revision_id: str,
    publication_id: str,
    generation: int,
) -> GovernedRelationshipIndex:
    """Backward-compatible bound index cache wrapper for existing tests/callers."""
    return _load_bound_governed_relationship_snapshot(revision_id, publication_id, generation).governance_index


def load_governed_relationship_snapshot(graph: AssetRelationshipGraph) -> PublishedRelationshipSnapshot:
    """Return publication envelope, governed index, and persisted edge bindings for ``graph``."""
    managed, rebuild_job_id = _runtime_graph_publication_binding(graph)
    generation = _current_cache_generation()
    if not managed:
        return _load_governed_relationship_snapshot(graph, generation)

    if rebuild_job_id is None:
        try:
            _resolve_governance_persistence_url()
        except GraphPersistenceInvalidUrlError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_GRAPH_PERSISTENCE_MISCONFIGURED_DETAIL,
            ) from exc
        except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
            pass
        return PublishedRelationshipSnapshot(publication=None, governance_index={}, projection_bindings={})

    binding = _published_projection_binding_for_rebuild_job_from_persistence(rebuild_job_id)

    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph publication synchronization is pending",
        )

    revision_id, publication_id = binding

    return _load_bound_governed_relationship_snapshot(
        revision_id,
        publication_id,
        generation,
    )


def load_governed_relationship_index(graph: AssetRelationshipGraph) -> GovernedRelationshipIndex:
    """Return governance metadata consistent with the supplied graph snapshot.

    Lifecycle-managed graphs are bound to the rebuild job that produced them.
    Every read checks the shared latest publication version before consulting the
    expensive metadata cache. If this process has not synchronized that publication,
    the read fails closed instead of returning stale or misattributed provenance.
    Managed startup graphs with no governed publication binding omit optional
    governance metadata. Unmanaged graph objects retain the legacy path used by
    isolated tests and tools.
    """
    return load_governed_relationship_snapshot(graph).governance_index


def invalidate_governed_relationship_index_cache() -> None:
    """Advance the cache generation and clear entries after publication writes."""
    with _cache_generation_lock:
        _cache_generation.value += 1
        _load_governed_relationship_snapshot.cache_clear()
        _load_bound_governed_relationship_snapshot.cache_clear()
        _load_governed_relationship_index.cache_clear()
        _load_bound_governed_relationship_index.cache_clear()
